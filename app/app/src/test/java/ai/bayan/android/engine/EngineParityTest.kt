package ai.bayan.android.engine

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assume.assumeTrue
import org.junit.Test
import java.io.File
import java.nio.file.Files

/**
 * The app's engine against transformers on the same model, CPU and ONNX Runtime version: beam search must give the
 * same tokens. Skipped unless BAYAN_PARITY points at a folder with `bundle/` (a model bundle) and `ref.jsonl` (lines
 * with "k", "input_ids" and "b4", transformers' num_beams=4 output, from the reference script in tools/).
 */
class EngineParityTest {
    @Test
    fun beamSearchMatchesTransformers() {
        val root = System.getenv("BAYAN_PARITY")?.let(::File)
        assumeTrue("BAYAN_PARITY not set", root != null && File(root, "ref.jsonl").isFile)
        val bundle = File(root!!, "bundle")
        val dir = File(root, "variant-beams4").apply { deleteRecursively(); mkdirs() }
        val spec = Json.parseToJsonElement(File(bundle, "bayan_model.json").readText()).jsonObject
        File(dir, "bayan_model.json").writeText(JsonObject(spec + ("num_beams" to JsonPrimitive(4))).toString())
        for (name in listOf("tokenizer.json", "encoder.onnx", "decoder.onnx")) Files.copy(File(bundle, name).toPath(), File(dir, name).toPath())

        val refs = File(root, "ref.jsonl").readLines().filter { it.isNotBlank() }.map { Json.parseToJsonElement(it).jsonObject }
        val mismatches = ArrayList<Int>()
        Seq2SeqEngine(dir, threads = 4).use { engine ->
            for (r in refs) {
                val input = r["input_ids"]!!.jsonArray.map { it.jsonPrimitive.int }.toIntArray()
                val want = r["b4"]!!.jsonArray.map { it.jsonPrimitive.int }
                val got = engine.beamTokens(input).toList()
                if (got != want) mismatches += r["k"]!!.jsonPrimitive.int
            }
        }
        File(root, "parity_mismatches.json").writeText(mismatches.toString())
        println("engine parity: ${refs.size - mismatches.size} of ${refs.size} identical to transformers; differ: $mismatches")
        assert(mismatches.isEmpty()) { "${mismatches.size} of ${refs.size} differ: $mismatches" }
    }
}
