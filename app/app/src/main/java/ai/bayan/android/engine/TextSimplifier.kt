package ai.bayan.android.engine

/**
 * Common contract for Arabic text simplifier engines (Mock, Rule-based, or on-device ONNX AraT5v2).
 */
interface TextSimplifier {
    /**
     * Simplifies the provided Arabic text asynchronously.
     */
    suspend fun simplify(request: SimplificationRequest): SimplificationResult

    /**
     * Checks if the simplification model is ready for inference.
     */
    fun isModelReady(): Boolean

    /**
     * Returns diagnostic and status information about the active engine.
     */
    fun getEngineInfo(): EngineInfo
}

