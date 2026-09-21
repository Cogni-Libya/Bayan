package ai.bayan.android.engine

/**
 * Service locator / factory providing singleton instance of [TextSimplifier].
 *
 * Allows seamless switching between [MockTextSimplifier] and future ONNX-based simplifiers.
 */
object SimplifierProvider {

    @Volatile
    private var instance: TextSimplifier? = null

    /**
     * Obtains the active [TextSimplifier] instance.
     */
    fun getInstance(): TextSimplifier {
        return instance ?: synchronized(this) {
            instance ?: MockTextSimplifier().also { instance = it }
        }
    }

    /**
     * Injects a custom simplifier (useful for testing or switching to ONNX).
     */
    fun setInstance(simplifier: TextSimplifier) {
        synchronized(this) {
            instance = simplifier
        }
    }

    /**
     * Resets to default instance.
     */
    fun reset() {
        synchronized(this) {
            instance = null
        }
    }
}

