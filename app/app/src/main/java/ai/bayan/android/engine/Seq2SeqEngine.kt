package ai.bayan.android.engine

import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import java.io.Closeable
import java.io.File
import java.util.concurrent.Callable
import java.util.concurrent.Executors
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
) {
    companion object {
        private val json = Json { ignoreUnknownKeys = true }
        fun load(file: File): ModelSpec = json.decodeFromString(serializer(), file.readText())
    }
}

/**
 * Runs one of Bayan's simplification models (AraBART or AraT5v2, exported with Optimum and quantized to int8) with
 * ONNX Runtime on the device CPU. Greedy decoding with a key/value cache, and the same `no_repeat_ngram_size` the
 * models were evaluated with.
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

    /**
     * Simplifies one sentence. [isCancelled] is polled between decoding steps; [onPartial] receives the text decoded
     * so far after every token, so the caller can stream it.
     */
    fun generate(sentence: String, isCancelled: () -> Boolean = { false }, onPartial: ((String) -> Unit)? = null): String {
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

    private fun emptyPast(length: Int): OnnxTensor =
        OnnxTensor.createTensor(
            env, FloatBuffer.allocate(spec.num_heads * length * spec.head_dim),
            longArrayOf(1, spec.num_heads.toLong(), length.toLong(), spec.head_dim.toLong()),
        )

    override fun close() {
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
                setOptimizationLevel(OrtSession.SessionOptions.OptLevel.NO_OPT)
            }
            return env.createSession(file.path, options).also { log(file, "optimized", started) }
        }
        val saved = File(file.path + ".opt.tmp")
        val options = OrtSession.SessionOptions().apply {
            setIntraOpNumThreads(threads)
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
