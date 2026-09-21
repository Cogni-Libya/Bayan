package ai.bayan.android.engine

/**
 * Simplification difficulty level.
 */
enum class SimplificationLevel {
    ELEMENTARY,
    STANDARD,
    ADVANCED
}

/**
 * Request payload for Arabic text simplification.
 */
data class SimplificationRequest(
    val originalText: String,
    val targetLevel: SimplificationLevel = SimplificationLevel.STANDARD,
    val preserveDiacritics: Boolean = false
)

/**
 * Result payload containing the simplified text and diagnostic metrics.
 */
data class SimplificationResult(
    val originalText: String,
    val simplifiedText: String,
    val level: SimplificationLevel = SimplificationLevel.STANDARD,
    val processingTimeMs: Long = 0L,
    val replacedWordsCount: Int = 0,
    val isModelOnDevice: Boolean = false,
    val isSuccess: Boolean = true,
    val errorMessage: String? = null
)

/**
 * Information metadata about the active simplification engine.
 */
data class EngineInfo(
    val name: String,
    val version: String,
    val status: String,
    val memoryFootprint: String,
    val isOnnxReady: Boolean
)

