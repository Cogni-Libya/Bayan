package ai.bayan.android.engine

import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import java.io.Closeable
import java.io.File
import java.util.concurrent.Callable
import java.util.concurrent.Executors
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.FloatBuffer
import java.nio.LongBuffer
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json

/** `bayan_model.json`: what the engine needs to know about an exported encoder-decoder model. */
@Serializable
data class ModelSpec(
    val id: String,
    val prefix: String,
    val decoder_start_token_id: Int,
    val eos_token_id: Int,
    val num_layers: Int,
    val num_heads: Int,
    val head_dim: Int,
    val max_input_tokens: Int = 256,
    val max_output_tokens: Int = 256,
    val no_repeat_ngram_size: Int = 3,
    /**
     * The decoding [Seq2SeqEngine.generate] uses when the caller does not choose: 1 is greedy decoding, streamed token
     * by token; more is beam search with that many beams (transformers' `generate(num_beams=…)`, where
     * `max_output_tokens` is its `max_length`), shown a sentence at a time.
     */
    val num_beams: Int = 1,
    val length_penalty: Float = 1f,
) {
    companion object {
        private val json = Json { ignoreUnknownKeys = true }
        fun load(file: File): ModelSpec = json.decodeFromString(serializer(), file.readText())
    }
}

/**
 * Runs one of Bayan's simplification models (AraBART or AraT5v2, exported with Optimum and quantized to int8) with
 * ONNX Runtime on the device CPU, with a key/value cache and the same `no_repeat_ngram_size` the models were evaluated
 * with. The model's `bayan_model.json` chooses the decoding: greedy (streamed) or beam search ([BeamSearch]).
 */
class Seq2SeqEngine(dir: File, threads: Int = defaultThreads()) : Closeable {
    val spec: ModelSpec = ModelSpec.load(File(dir, "bayan_model.json"))
    private val env = OrtEnvironment.getEnvironment()
    // The tokenizer and the two graphs load in parallel: a cold start costs the slowest of the three, not their sum.
    private val tokenizer: SentencePieceTokenizer
    private val encoder: OrtSession
    private val decoder: OrtSession

    init {
        val pool = Executors.newFixedThreadPool(3)
        try {
            val tok = pool.submit(Callable { SentencePieceTokenizer.load(File(dir, "tokenizer.json")) })
            val enc = pool.submit(Callable { open(File(dir, "encoder.onnx"), threads) })
            val dec = pool.submit(Callable { open(File(dir, "decoder.onnx"), threads) })
            tokenizer = tok.get(); encoder = enc.get(); decoder = dec.get()
        } finally {
            pool.shutdown()
        }
    }
    private val decoderInputs = decoder.inputNames
    /** Scores beams in parallel while the decoder is idle between steps; started by the first beam search. */
    private val beamPoolLazy = lazy { Executors.newFixedThreadPool(3) { Thread(it, "bayan-beams").apply { isDaemon = true } } }
    private val beamPool by beamPoolLazy

    /** The model's input for [sentence]: the prefix and the sentence, tokenized and cut to `max_input_tokens`. */
    internal fun inputIds(sentence: String): IntArray = tokenizer.encode(spec.prefix + sentence, spec.max_input_tokens)

    internal fun decode(ids: IntArray): String = tokenizer.decode(ids)

    /**
     * Simplifies one sentence with [beams] beams (1 = greedy). [isCancelled] is polled between decoding steps. With
     * greedy decoding [onPartial] receives the text decoded so far after every token, so the caller can stream it. Beam
     * search can still change earlier tokens until it finishes, so it never calls [onPartial]: the sentence is shown
     * when it is final.
     */
    fun generate(
        sentence: String,
        isCancelled: () -> Boolean = { false },
        beams: Int = spec.num_beams,
        onPartial: ((String) -> Unit)? = null,
    ): String {
        if (beams > 1) return tokenizer.decode(beamTokens(inputIds(sentence), beams, isCancelled))
        val ids = tokenizer.encode(spec.prefix + sentence, spec.max_input_tokens)
        val n = ids.size.toLong()
        val inputIds = OnnxTensor.createTensor(env, LongBuffer.wrap(ids.map { it.toLong() }.toLongArray()), longArrayOf(1, n))
        val mask = OnnxTensor.createTensor(env, LongBuffer.wrap(LongArray(ids.size) { 1L }), longArrayOf(1, n))
        val open = ArrayList<AutoCloseable>().apply { add(inputIds); add(mask) }
        try {
            val encoded = encoder.run(mapOf("input_ids" to inputIds, "attention_mask" to mask))
            open += encoded
            val hidden = encoded.get(0) as OnnxTensor

            val out = arrayListOf(spec.decoder_start_token_id)
            val past = HashMap<String, OnnxTensor>()   // past_key_values.* for the next step
            var encoderPast: Map<String, OnnxTensor>? = null
            var previous: OrtSession.Result? = null
            try {
                for (step in 0 until spec.max_output_tokens) {
                    if (isCancelled()) break
                    val feeds = HashMap<String, OnnxTensor>()
                    val stepTensors = ArrayList<OnnxTensor>()
                    fun own(t: OnnxTensor) = t.also { stepTensors += it }
                    feeds["input_ids"] = own(OnnxTensor.createTensor(env, LongBuffer.wrap(longArrayOf(out.last().toLong())), longArrayOf(1, 1)))
                    feeds["encoder_attention_mask"] = mask
                    feeds["encoder_hidden_states"] = hidden
                    if ("use_cache_branch" in decoderInputs) {
                        feeds["use_cache_branch"] = own(OnnxTensor.createTensor(env, booleanArrayOf(step > 0)))
                    }
                    for (layer in 0 until spec.num_layers) {
                        for (part in PARTS) {
                            val name = "past_key_values.$layer.$part"
                            feeds[name] = if (step == 0) {
                                own(emptyPast(if (part.startsWith("decoder")) 0 else 1))
                            } else if (part.startsWith("encoder")) {
                                encoderPast!!.getValue(name)
                            } else {
                                past.getValue(name)
                            }
                        }
                    }
                    val result = decoder.run(feeds)
                    stepTensors.forEach { it.close() }

                    val logits = (result.get("logits").get() as OnnxTensor).floatBuffer
                    val vocab = logits.limit()
                    for (b in bannedNextTokens(out, spec.no_repeat_ngram_size)) if (b in 0 until vocab) logits.put(b, Float.NEGATIVE_INFINITY)
                    var best = 0
                    var bestScore = Float.NEGATIVE_INFINITY
                    for (i in 0 until vocab) { val v = logits.get(i); if (v > bestScore) { bestScore = v; best = i } }
                    out += best
                    if (onPartial != null && best != spec.eos_token_id) onPartial(tokenizer.decode(out.toIntArray()))

                    past.clear()
                    for (entry in result) {
                        val key = entry.key
                        if (!key.startsWith("present.")) continue
                        val name = key.replaceFirst("present.", "past_key_values.")
                        if (".encoder." in name && step > 0) continue
                        past[name] = entry.value as OnnxTensor
                    }
                    if (step == 0) {
                        encoderPast = past.filterKeys { ".encoder." in it }
                        open += result   // the encoder cache lives in the first result for the whole sentence
                    } else {
                        previous?.close()
                        previous = result
                    }
                    if (best == spec.eos_token_id) break
                }
            } finally {
                previous?.close()
            }
            return tokenizer.decode(out.toIntArray())
        } finally {
            open.asReversed().forEach { runCatching { it.close() } }
        }
    }

    /**
     * Beam search ([BeamSearch]) over one tokenized input; returns the best sequence, start token first. Shaped
     * like transformers' `generate`: the encoder runs once at batch 1 and its output is repeated for every beam; every
     * decoder step, the first included, runs all beams as one batch (so the decoder's weights are read once per
     * step), and the self-attention cache is reordered to follow the beams whenever they swap parents. The
     * cross-attention cache, made at the first step, is the same for every beam and is never reordered.
     */
    internal fun beamTokens(ids: IntArray, beams: Int = spec.num_beams, isCancelled: () -> Boolean = { false }): IntArray {
        require(beams >= 2) { "beam search needs at least 2 beams" }
        val n = ids.size.toLong()
        val open = ArrayList<AutoCloseable>()
        fun <T : AutoCloseable> keep(t: T): T = t.also { open += it }
        try {
            val inputIds = keep(OnnxTensor.createTensor(env, LongBuffer.wrap(LongArray(ids.size) { ids[it].toLong() }), longArrayOf(1, n)))
            val mask = keep(OnnxTensor.createTensor(env, LongBuffer.wrap(LongArray(ids.size) { 1L }), longArrayOf(1, n)))
            val hidden = keep(encoder.run(mapOf("input_ids" to inputIds, "attention_mask" to mask))).get(0) as OnnxTensor
            val beamMask = keep(OnnxTensor.createTensor(env, LongBuffer.wrap(LongArray(beams * ids.size) { 1L }), longArrayOf(beams.toLong(), n)))
            val beamHidden = keep(tile(hidden, beams))

            val crossCache = HashMap<String, OnnxTensor>()   // past_key_values.*.encoder.*, held by the first result
            var selfCache = HashMap<String, OnnxTensor>()    // past_key_values.*.decoder.*, one row per beam
            var selfOwner: AutoCloseable? = null             // what holds selfCache when it must be freed: a later
                                                             // decoder result, or our reordered copies

            val search = BeamSearch(beams, spec.eos_token_id, spec.max_output_tokens, spec.no_repeat_ngram_size, spec.length_penalty, pool = beamPool)
            var steps = 0
            var runNanos = 0L
            var reorderNanos = 0L
            val started = System.nanoTime()
            val step = BeamSearch.Step { last, parents ->
                steps++
                val feeds = HashMap<String, OnnxTensor>()
                val stepTensors = ArrayList<OnnxTensor>()
                fun own(t: OnnxTensor) = t.also { stepTensors += it }
                val first = parents == null
                feeds["input_ids"] = own(OnnxTensor.createTensor(env, LongBuffer.wrap(LongArray(beams) { last[it].toLong() }), longArrayOf(beams.toLong(), 1)))
                feeds["encoder_attention_mask"] = beamMask
                feeds["encoder_hidden_states"] = beamHidden
                if ("use_cache_branch" in decoderInputs) feeds["use_cache_branch"] = own(OnnxTensor.createTensor(env, booleanArrayOf(!first)))
                if (!first && !parents!!.indices.all { parents[it] == it }) {
                    val t = System.nanoTime()
                    // Beams swapped parents: copy each beam's cache from the beam it continues.
                    val reordered = HashMap<String, OnnxTensor>()
                    val copies = ArrayList<OnnxTensor>()
                    for ((name, tensor) in selfCache) reordered[name] = gatherRows(tensor, parents).also { copies += it }
                    selfOwner?.close()
                    selfOwner = AutoCloseable { copies.forEach { it.close() } }
                    selfCache = reordered
                    reorderNanos += System.nanoTime() - t
                }
                for (layer in 0 until spec.num_layers) {
                    for (part in PARTS) {
                        val name = "past_key_values.$layer.$part"
                        feeds[name] = when {
                            first -> own(emptyPast(if (part.startsWith("decoder")) 0 else 1, beams))
                            part.startsWith("encoder") -> crossCache.getValue(name)
                            else -> selfCache.getValue(name)
                        }
                    }
                }
                val t = System.nanoTime()
                val result = try { decoder.run(feeds) } finally { stepTensors.forEach { it.close() } }
                runNanos += System.nanoTime() - t

                // One copy out of ONNX Runtime; the search then works in place on it.
                val flat = (result.get("logits").get() as OnnxTensor).floatBuffer
                    .let { if (it.hasArray() && it.arrayOffset() == 0 && it.capacity() == it.array().size) it.array() else FloatArray(it.remaining()).also { a -> it.get(a) } }

                val next = HashMap<String, OnnxTensor>()
                for (entry in result) {
                    if (!entry.key.startsWith("present.")) continue
                    val name = entry.key.replaceFirst("present.", "past_key_values.")
                    if (".encoder." in name) {
                        if (first) crossCache[name] = entry.value as OnnxTensor
                    } else {
                        next[name] = entry.value as OnnxTensor
                    }
                }
                selfOwner?.close()
                // The first result also holds the cross-attention cache, so it lives until the sentence is done.
                if (first) { keep(result); selfOwner = null } else selfOwner = result
                selfCache = next
                flat
            }
            try {
                return search.run(spec.decoder_start_token_id, step, isCancelled).also {
                    val total = (System.nanoTime() - started) / 1_000_000
                    android.util.Log.i("Bayan", "beam search: $steps steps in $total ms (decoder ${runNanos / 1_000_000}, cache ${reorderNanos / 1_000_000}, rest ${total - (runNanos + reorderNanos) / 1_000_000})")
                }
            } finally {
                selfOwner?.close()
            }
        } finally {
            open.asReversed().forEach { runCatching { it.close() } }
        }
    }

    /** [t] (batch 1) repeated [times] times along the batch axis: the encoder's output, once per beam. */
    private fun tile(t: OnnxTensor, times: Int): OnnxTensor {
        val shape = t.info.shape
        require(shape[0] == 1L) { "tile expects batch 1, got ${shape.toList()}" }
        val row = t.floatBuffer
        val size = row.remaining()
        val out = ByteBuffer.allocateDirect(size * times * 4).order(ByteOrder.nativeOrder()).asFloatBuffer()
        repeat(times) { row.rewind(); out.put(row) }
        out.rewind()
        return OnnxTensor.createTensor(env, out, shape.copyOf().also { it[0] = times.toLong() })
    }

    /** A copy of [t] whose row b is row [rows]`[b]` of [t] (the batch axis is the first). */
    private fun gatherRows(t: OnnxTensor, rows: IntArray): OnnxTensor {
        val shape = t.info.shape
        val src = t.floatBuffer
        val rowSize = src.remaining() / shape[0].toInt()
        val out = ByteBuffer.allocateDirect(src.remaining() * 4).order(ByteOrder.nativeOrder()).asFloatBuffer()
        for (r in rows) {
            src.limit((r + 1) * rowSize).position(r * rowSize)
            out.put(src)
        }
        out.rewind()
        return OnnxTensor.createTensor(env, out, shape)
    }

    private fun emptyPast(length: Int, batch: Int = 1): OnnxTensor =
        OnnxTensor.createTensor(
            env, FloatBuffer.allocate(batch * spec.num_heads * length * spec.head_dim),
            longArrayOf(batch.toLong(), spec.num_heads.toLong(), length.toLong(), spec.head_dim.toLong()),
        )

    override fun close() {
        if (beamPoolLazy.isInitialized()) runCatching { beamPool.shutdown() }
        runCatching { decoder.close() }
        runCatching { encoder.close() }
    }

    /**
     * Graph optimization is most of a cold start (seconds for AraT5v2). The first load on a device saves the
     * optimized graph in place of the original; later loads skip optimization. The saved graph is specific to this
     * device's CPU, which is fine because it never leaves it.
     */
    private fun open(file: File, threads: Int): OrtSession {
        val marker = File(file.path + ".optimized")
        val started = System.nanoTime()
        if (marker.isFile) {
            val options = OrtSession.SessionOptions().apply {
                setIntraOpNumThreads(threads)
                addConfigEntry("session.intra_op.allow_spinning", "0")
                setOptimizationLevel(OrtSession.SessionOptions.OptLevel.NO_OPT)
            }
            return env.createSession(file.path, options).also { log(file, "optimized", started) }
        }
        val saved = File(file.path + ".opt.tmp")
        val options = OrtSession.SessionOptions().apply {
            setIntraOpNumThreads(threads)
            // Worker threads sleep between steps instead of spinning: spinning holds the fast cores at full load and
            // starves the UI, so the overlay's light and the streaming text stutter.
            addConfigEntry("session.intra_op.allow_spinning", "0")
            setOptimizationLevel(OrtSession.SessionOptions.OptLevel.ALL_OPT)
            setOptimizedModelFilePath(saved.path)
        }
        val session = env.createSession(file.path, options)
        if (saved.length() > 0 && saved.renameTo(file)) marker.createNewFile() else saved.delete()
        log(file, "optimized now", started)
        return session
    }

    private fun log(file: File, how: String, started: Long) =
        android.util.Log.i("Bayan", "${file.parentFile?.name}/${file.name} ($how) in ${(System.nanoTime() - started) / 1_000_000} ms")

    companion object {
        private val PARTS = listOf("decoder.key", "decoder.value", "encoder.key", "encoder.value")

        fun defaultThreads(): Int = Runtime.getRuntime().availableProcessors().coerceIn(2, 4)

        /** Tokens that would repeat an n-gram already in [seq] (Hugging Face's `no_repeat_ngram_size`). */
        fun bannedNextTokens(seq: List<Int>, n: Int): Set<Int> {
            if (n <= 0 || seq.size < n) return emptySet()
            val tail = seq.subList(seq.size - (n - 1), seq.size)
            val banned = HashSet<Int>()
            for (i in 0..seq.size - n) {
                var match = true
                for (j in 0 until n - 1) if (seq[i + j] != tail[j]) { match = false; break }
                if (match) banned += seq[i + n - 1]
            }
            return banned
        }
    }
}
