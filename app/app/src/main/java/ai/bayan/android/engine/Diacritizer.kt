package ai.bayan.android.engine

import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import java.io.Closeable
import java.nio.LongBuffer
import java.text.Normalizer
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive

/**
 * Adds tashkeel (the short vowels and other marks) to Arabic text with Libtashkeel (Musharraf Omer, MIT; the
 * diacritizer the team benchmarked and selected, #6, #23): a 4.8 MB character model that only adds marks and never
 * changes a letter. A port of text2tashkeel's Libtashkeel path (pure prediction, no hints), so it gives the same output
 * (DiacritizerTest). One sentence per call: the model was not made for padded batches.
 *
 * [model] is the ONNX file and [maps] its character and mark tables (`libtashkeel.maps.json`).
 */
class Diacritizer(model: ByteArray, maps: String) : Closeable {
    private val env = OrtEnvironment.getEnvironment()
    private val session: OrtSession = env.createSession(model, OrtSession.SessionOptions().apply {
        setIntraOpNumThreads(2)
        addConfigEntry("session.intra_op.allow_spinning", "0")
    })
    private val input: Map<Char, Long>
    private val noHint: Long
    private val target: Map<Int, String>
    private val padId: Int

    init {
        val m = Json.parseToJsonElement(maps).jsonObject
        input = m["input"]!!.jsonObject.entries.associate { (k, v) -> k.single() to v.jsonPrimitive.int.toLong() }
        noHint = m["hint"]!!.jsonObject[""]!!.jsonPrimitive.int.toLong()
        target = m["target"]!!.jsonObject.entries.associate { (k, v) -> v.jsonPrimitive.int to k }
        padId = input.getValue('_').toInt()
    }

    /** [text] with predicted tashkeel; any marks it already had are replaced. */
    fun diacritize(text: String): String {
        val bare = strip(text)
        // Characters the model knows go in (digits as '#'); the others are left out and put back as they were.
        val clean = StringBuilder()
        val removed = HashSet<Char>()
        for (c in bare) {
            when {
                c in input -> clean.append(c)
                c in NUMERALS -> clean.append('#')
                else -> removed += c
            }
        }
        if (clean.isEmpty()) return bare
        val n = clean.length
        val chars = OnnxTensor.createTensor(env, LongBuffer.wrap(LongArray(n) { input.getValue(clean[it]) }), longArrayOf(1, n.toLong()))
        val hints = OnnxTensor.createTensor(env, LongBuffer.wrap(LongArray(n) { noHint }), longArrayOf(1, n.toLong()))
        val lengths = OnnxTensor.createTensor(env, LongBuffer.wrap(longArrayOf(n.toLong())), longArrayOf(1))
        val marks = try {
            session.run(mapOf("char_inputs" to chars, "diac_inputs" to hints, "input_lengths" to lengths), setOf("predictions")).use { r ->
                val bytes = (r.get(0) as OnnxTensor).byteBuffer
                List(bytes.remaining()) { bytes.get(it).toInt() and 0xFF }.filter { it != padId }.map { target[it] ?: "" }
            }
        } finally {
            chars.close(); hints.close(); lengths.close()
        }
        val out = StringBuilder(bare.length * 2)
        var k = 0
        for (c in bare) {
            out.append(c)
            if (c !in removed) out.append(marks.getOrElse(k++) { "" })
        }
        return Normalizer.normalize(out, Normalizer.Form.NFC)
    }

    override fun close() {
        runCatching { session.close() }
    }

    companion object {
        private val NUMERALS = "0123456789٠١٢٣٤٥٦٧٨٩".toSet()

        /** Tashkeel removed: U+064B–U+0652 and the superscript alef U+0670, after NFC (as text2tashkeel does). */
        fun strip(text: String): String =
            Normalizer.normalize(text, Normalizer.Form.NFC).filterNot { it in 'ً'..'ْ' || it == 'ٰ' }
    }
}
