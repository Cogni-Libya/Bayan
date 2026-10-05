package ai.bayan.android.speech

import androidx.annotation.StringRes
import ai.bayan.android.R
import ai.bayan.android.model.Downloadable
import ai.bayan.android.model.ModelFile

enum class VoiceEngine { System, Kokoro, Piper }

/** A read-aloud voice. Everything except the system voice runs on-device with sherpa-onnx. */
data class VoiceInfo(
    override val id: String,
    @StringRes override val title: Int,
    @StringRes val summary: Int,
    val engine: VoiceEngine,
    override val files: List<ModelFile> = emptyList(),
    /** Where the voice comes from and under which licence, shown next to it. */
    val credit: String = "",
) : Downloadable {
    /** The ONNX model file (the first one listed). */
    val modelFile: String get() = files.first().name
}

private const val NABRA = "https://huggingface.co/marwanelamami/nabra-7m-distill-sherpa-onnx/resolve/main"
private fun piper(repo: String, file: String) = "https://huggingface.co/csukuangfj/$repo/resolve/main/$file"

object VoiceCatalog {
    const val SYSTEM_ID = "system"
    const val DEFAULT_ID = "tts-nabra"

    val system = VoiceInfo(SYSTEM_ID, R.string.voice_system_title, R.string.voice_system_summary, VoiceEngine.System)

    val downloadable = listOf(
        VoiceInfo(
            id = DEFAULT_ID,
            title = R.string.voice_nabra_title,
            summary = R.string.voice_nabra_summary,
            engine = VoiceEngine.Kokoro,
            files = listOf(
                ModelFile("model.int8.onnx", 8_718_233, "2ac2a824d0a653da119ce453889bec5e6658a93e340476a4f0121d60621920d7", "$NABRA/model.int8.onnx"),
                ModelFile("voices.bin", 522_240, "129d447a7c9bdce1d5b6cb5ecb789bbfd9f427b7775131a97dfa5638583b3b92", "$NABRA/voices.bin"),
                ModelFile("tokens.txt", 697, "5b43b8142c28b5c6f5d13d83caed696e3dabde376d5a0e9e67aceaf66f021da1", "$NABRA/tokens.txt"),
            ),
            credit = "Nabra-7M-Distill · Kokoro",
        ),
        VoiceInfo(
            id = "tts-miro",
            title = R.string.voice_miro_title,
            summary = R.string.voice_piper_summary,
            engine = VoiceEngine.Piper,
            files = listOf(
                ModelFile(
                    "ar_JO-SA_miro_V2-high.onnx", 18_566_247, "dd287270dc977952300b44ec090ec0d069816d389537ea73c1f975b7cda9c54e",
                    piper("vits-piper-ar_JO-SA_miro_V2-high-int8", "ar_JO-SA_miro_V2-high.onnx"),
                ),
                ModelFile(
                    "tokens.txt", 970, "40e77b7d2c9c95cab233b8645db58a29df3a091ffe485a658a02aab75ec04d5e",
                    piper("vits-piper-ar_JO-SA_miro_V2-high-int8", "tokens.txt"),
                ),
            ),
            credit = "Piper · OpenVoiceOS · CC BY-NC-ND 4.0",
        ),
        VoiceInfo(
            id = "tts-dii",
            title = R.string.voice_dii_title,
            summary = R.string.voice_piper_summary,
            engine = VoiceEngine.Piper,
            files = listOf(
                ModelFile(
                    "ar_JO-SA_dii-high.onnx", 18_566_251, "7a046bb15d26051d7001db4381e5092b94f15bba25f27ca9d17c1abde2fa11ca",
                    piper("vits-piper-ar_JO-SA_dii-high-int8", "ar_JO-SA_dii-high.onnx"),
                ),
                ModelFile(
                    "tokens.txt", 970, "40e77b7d2c9c95cab233b8645db58a29df3a091ffe485a658a02aab75ec04d5e",
                    piper("vits-piper-ar_JO-SA_dii-high-int8", "tokens.txt"),
                ),
            ),
            credit = "Piper · OpenVoiceOS · CC BY-NC-ND 4.0",
        ),
        VoiceInfo(
            id = "tts-kareem",
            title = R.string.voice_kareem_title,
            summary = R.string.voice_kareem_summary,
            engine = VoiceEngine.Piper,
            files = listOf(
                ModelFile(
                    "ar_JO-kareem-medium.onnx", 63_201_421, "f942091e1fdb7221b289256cc2238295b5472d326029532f79bb84836380fe53",
                    piper("vits-piper-ar_JO-kareem-medium", "ar_JO-kareem-medium.onnx"),
                ),
                ModelFile(
                    "tokens.txt", 954, "620e1aecf1a68fea3ba5850d137b0138fa2037c9b372dad13b95a2a215d0849a",
                    piper("vits-piper-ar_JO-kareem-medium", "tokens.txt"),
                ),
            ),
            credit = "Piper",
        ),
    )

    val all: List<VoiceInfo> = listOf(system) + downloadable

    fun get(id: String): VoiceInfo = all.firstOrNull { it.id == id } ?: system
}
