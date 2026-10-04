package ai.bayan.android.model

import ai.bayan.android.R
import androidx.annotation.StringRes

/** One file of a download; [url] is where it comes from when it is not under the app's own model host. */
data class ModelFile(val name: String, val bytes: Long, val sha256: String, val url: String? = null)

/** Anything the app downloads into its model storage: simplification models and read-aloud voices. */
interface Downloadable {
    val id: String
    @get:StringRes val title: Int
    val files: List<ModelFile>
    val bytes: Long get() = files.sumOf { it.bytes }
}

/** A downloadable on-device simplification model: Bayan's model 2, fine-tuned on dyslexia-friendly Arabic. */
data class ModelInfo(
    override val id: String,
    @StringRes override val title: Int,
    @StringRes val summary: Int,
    val architecture: String,
    override val files: List<ModelFile>,
    /** SARI on the changed rows of our validation set (higher is better). */
    val sari: Double,
    /** Relative speed on the same hardware (AraBART = 1.0). */
    val relativeSpeed: Double,
) : Downloadable

object ModelCatalog {
    val models = listOf(
        ModelInfo(
            id = "arabart",
            title = R.string.model_arabart_title,
            summary = R.string.model_arabart_summary,
            architecture = "AraBART",
            files = listOf(
                ModelFile("bayan_model.json", 2_043, "34ea72a7e1ac522baa0a6a150acac50e5e3aec958835c9d7b36be91ae07c5dec"),
                ModelFile("tokenizer.json", 3_781_220, "e1987d2cf89237496f5f8b1ceea69295995b271d2fb3410b03a6e6d2b2ba9735"),
                ModelFile("encoder.onnx", 82_296_508, "44ab6721c7ac6b97bbd9137bf5efff323cd79011966f54ef53308fa469b92b85"),
                ModelFile("decoder.onnx", 136_076_585, "3e7e86f257630e34f416e80006b1e1fc48bdbb8cbb65db75bf9e316f1701f39c"),
            ),
            sari = 64.71,
            relativeSpeed = 1.0,
        ),
        ModelInfo(
            id = "arat5",
            title = R.string.model_arat5_title,
            summary = R.string.model_arat5_summary,
            architecture = "AraT5v2",
            files = listOf(
                ModelFile("bayan_model.json", 3_594, "7eb5fd1d4614689f907a9d660bf4812597084b311f82c27dee480245696764aa"),
                ModelFile("tokenizer.json", 15_315_056, "e2fdcfdda5b5d39ea007cdce1906e0eb206cdb89e4a735090cfa3e200c51d940"),
                ModelFile("encoder.onnx", 170_493_698, "f6d004cfb3cc6b8fbc96ba3ee95d16335a1de51f382ed2df76b6ac3385915d58"),
                ModelFile("decoder.onnx", 285_167_512, "ee3f026fcd88252dac4c44c4976775d75c87979e3821290d47941b2240b9602f"),
            ),
            sari = 66.58,
            relativeSpeed = 0.28,
        ),
        ModelInfo(
            // Model 3: AraT5v2 on corpus v1, int8, an option next to model 2. On BayanBench test, through the same text step,
            // it simplifies more than model 2 AraT5 (longest clause about 4 words shorter) but keeps the meaning less often.
            id = "model3",
            title = R.string.model_model3_title,
            summary = R.string.model_model3_summary,
            architecture = "AraT5v2",
            files = listOf(
                ModelFile("bayan_model.json", 3_589, "2a781e17148d6c25922bbd1e9ea5da211f5663dc69b8078f513bba276b8bdf69"),
                ModelFile("tokenizer.json", 15_315_056, "e2fdcfdda5b5d39ea007cdce1906e0eb206cdb89e4a735090cfa3e200c51d940"),
                ModelFile("encoder.onnx", 170_493_698, "21b0c2995001afe8069214473bc7ffa8f42695c3bc353f4110310c1e1a4dd738"),
                ModelFile("decoder.onnx", 285_167_512, "c3f1a1aff034c44e43e7ad6d1719be56854016932c4540fac22b53f80846caa1"),
            ),
            sari = 55.0,
            relativeSpeed = 0.28,
        ),
    )

    const val DEFAULT_ID = "arabart"

    fun get(id: String): ModelInfo = models.firstOrNull { it.id == id } ?: models.first()
}

/** Every download the app knows about, by id. */
object Downloads {
    val all: List<Downloadable> get() = ModelCatalog.models + ai.bayan.android.speech.VoiceCatalog.downloadable
    fun find(id: String): Downloadable? = all.firstOrNull { it.id == id }
}
