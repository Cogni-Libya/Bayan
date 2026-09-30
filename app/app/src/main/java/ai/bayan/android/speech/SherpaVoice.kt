package ai.bayan.android.speech

import android.content.Context
import com.k2fsa.sherpa.onnx.OfflineTts
import com.k2fsa.sherpa.onnx.OfflineTtsConfig
import com.k2fsa.sherpa.onnx.OfflineTtsKokoroModelConfig
import com.k2fsa.sherpa.onnx.OfflineTtsModelConfig
import com.k2fsa.sherpa.onnx.OfflineTtsVitsModelConfig
import java.io.File
import java.io.Closeable

/** One loaded on-device voice. Generation blocks, so callers run it off the main thread. */
class SherpaVoice(val voice: VoiceInfo, dir: File, espeakData: File) : Closeable {
    private val tts: OfflineTts

    init {
        val model = File(dir, voice.modelFile).path
        val tokens = File(dir, "tokens.txt").path
        val modelConfig = when (voice.engine) {
            VoiceEngine.Kokoro -> OfflineTtsModelConfig(
                kokoro = OfflineTtsKokoroModelConfig(
                    model = model,
                    voices = File(dir, "voices.bin").path,
                    tokens = tokens,
                    dataDir = espeakData.path,
                    lang = "ar",
                ),
                numThreads = THREADS,
            )
            VoiceEngine.Piper -> OfflineTtsModelConfig(
                vits = OfflineTtsVitsModelConfig(model = model, tokens = tokens, dataDir = espeakData.path),
                numThreads = THREADS,
            )
            VoiceEngine.System -> error("The system voice does not run in sherpa-onnx")
        }
        tts = OfflineTts(null, OfflineTtsConfig(model = modelConfig, maxNumSentences = 1))
    }

    val sampleRate: Int get() = tts.sampleRate()

    fun generate(text: String, speed: Float): FloatArray = tts.generate(text, 0, speed).samples

    override fun close() = tts.release()

    companion object {
        private val THREADS = Runtime.getRuntime().availableProcessors().coerceIn(1, 2)
        private const val ESPEAK_VERSION = "ar-1"

        /**
         * espeak-ng's Arabic pronunciation data (1.1 MB), shipped in the APK and copied out once, because the native
         * phonemizer reads it from a folder.
         */
        fun espeakData(context: Context): File {
            val dir = File(context.filesDir, "espeak-ng-data")
            val marker = File(dir, ".version")
            if (marker.isFile && marker.readText() == ESPEAK_VERSION) return dir
            dir.deleteRecursively()
            fun copy(asset: String) {
                val children = context.assets.list(asset).orEmpty()
                if (children.isEmpty()) {
                    val target = File(context.filesDir, asset).apply { parentFile?.mkdirs() }
                    context.assets.open(asset).use { input -> target.outputStream().use { input.copyTo(it) } }
                } else children.forEach { copy("$asset/$it") }
            }
            copy("espeak-ng-data")
            marker.writeText(ESPEAK_VERSION)
            return dir
        }
    }
}
