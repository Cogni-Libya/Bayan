package ai.bayan.android.engine

import android.app.Activity
import android.os.Bundle
import android.util.Log
import android.view.WindowManager
import android.widget.TextView
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonArray
import java.io.File
import java.nio.file.Files
import kotlin.concurrent.thread

/**
 * Debug builds only. Greedy against beam search on the phone, for parity with transformers and for timing:
 *
 *   files/decoding/bundle/        a model bundle (bayan_model.json, tokenizer.json, encoder.onnx, decoder.onnx)
 *   files/decoding/pieces.jsonl   {"k": …, "text": …} per sentence
 *   adb shell am start -n ai.bayan.android/ai.bayan.android.engine.DecodingBenchmarkActivity [--ei beams 4]
 *
 * Writes files/decoding/out.jsonl (per sentence and decoding: input ids, output, output ids for beam search, and
 * milliseconds) and files/decoding/done when finished. The screen stays on so the phone does not throttle the run.
 */
class DecodingBenchmarkActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        val status = TextView(this).apply { textSize = 18f; setPadding(48, 160, 48, 48) }
        setContentView(status)
        val beams = intent.getIntExtra("beams", 4)
        val root = File(filesDir, "decoding")
        File(root, "done").delete()
        thread(name = "decoding-benchmark") {
            val message = runCatching { run(root, beams) { runOnUiThread { status.text = it } } }
                .fold({ "done" }, { Log.e(TAG, "benchmark failed", it); "failed: $it" })
            File(root, "done").writeText(message)
            runOnUiThread { status.text = message }
        }
    }

    private fun run(root: File, beams: Int, progress: (String) -> Unit) {
        val bundle = File(root, "bundle")
        val rows = File(root, "pieces.jsonl").readLines().filter { it.isNotBlank() }.map { Json.parseToJsonElement(it).jsonObject }
        // Optimize the graphs once, in the bundle itself, so both variants load the saved optimized graphs.
        progress("optimizing the model")
        Seq2SeqEngine(bundle).close()
        File(root, "out.jsonl").bufferedWriter().use { out ->
            for (numBeams in listOf(1, beams)) {
                Seq2SeqEngine(variant(bundle, File(root, "beams$numBeams"), numBeams)).use { engine ->
                    engine.generate(rows.first()["text"]!!.jsonPrimitive.content)   // warm-up, not timed
                    for ((i, row) in rows.withIndex()) {
                        progress("$numBeams beam(s): ${i + 1} / ${rows.size}")
                        val text = row["text"]!!.jsonPrimitive.content
                        val ids = engine.inputIds(text)
                        val t = System.nanoTime()
                        val outIds = if (numBeams > 1) engine.beamTokens(ids) else null
                        val outText = if (outIds != null) engine.decode(outIds) else engine.generate(text)
                        val ms = (System.nanoTime() - t) / 1e6
                        out.write(buildJsonObject {
                            put("k", row["k"]!!.jsonPrimitive.int)
                            put("beams", numBeams)
                            putJsonArray("input_ids") { ids.forEach { add(JsonPrimitive(it)) } }
                            if (outIds != null) putJsonArray("output_ids") { outIds.forEach { add(JsonPrimitive(it)) } }
                            put("output", outText)
                            put("ms", ms)
                        }.toString())
                        out.newLine()
                        out.flush()
                    }
                }
            }
        }
    }

    /** [bundle] with `num_beams` set to [numBeams]: its own bayan_model.json, and links to the bundle's other files. */
    private fun variant(bundle: File, dir: File, numBeams: Int): File {
        dir.deleteRecursively(); dir.mkdirs()
        val spec = Json.parseToJsonElement(File(bundle, "bayan_model.json").readText()).jsonObject
        File(dir, "bayan_model.json").writeText(JsonObject(spec + ("num_beams" to JsonPrimitive(numBeams))).toString())
        for (name in listOf("tokenizer.json", "encoder.onnx", "decoder.onnx", "encoder.onnx.optimized", "decoder.onnx.optimized")) {
            if (File(bundle, name).exists()) Files.createSymbolicLink(File(dir, name).toPath(), File(bundle, name).toPath())
        }
        return dir
    }

    private companion object { const val TAG = "Bayan" }
}
