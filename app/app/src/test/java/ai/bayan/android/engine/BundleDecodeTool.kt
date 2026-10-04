package ai.bayan.android.engine

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assume.assumeTrue
import org.junit.Test
import java.io.File
import java.io.FileWriter

/**
 * Not a test: decodes many sentences with the app's engine on the JVM, to score a bundle the way the app runs it (its
 * own tokenizer and decoding). Skipped unless BAYAN_DECODE_BUNDLE (a bundle folder) and BAYAN_DECODE_IN (lines of
 * {"in": sentence}) are set; appends {"in", "out"} lines to BAYAN_DECODE_OUT.
 */
class BundleDecodeTool {
    @Test
    fun decode() {
        val bundle = System.getenv("BAYAN_DECODE_BUNDLE")?.let(::File)
        val input = System.getenv("BAYAN_DECODE_IN")?.let(::File)
        val output = System.getenv("BAYAN_DECODE_OUT")?.let(::File)
        assumeTrue("BAYAN_DECODE_* not set", bundle != null && input?.isFile == true && output != null)
        Seq2SeqEngine(bundle!!, threads = 4).use { engine ->
            FileWriter(output!!, Charsets.UTF_8, true).buffered().use { w ->
                for (line in input!!.readLines().filter { it.isNotBlank() }) {
                    val s = Json.parseToJsonElement(line).jsonObject["in"]!!.jsonPrimitive.content
                    w.write(buildJsonObject { put("in", JsonPrimitive(s)); put("out", JsonPrimitive(engine.generate(s).trim())) }.toString())
                    w.newLine(); w.flush()
                }
            }
        }
    }
}
