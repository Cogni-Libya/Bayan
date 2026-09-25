package ai.bayan.android.test

import ai.bayan.android.engine.EngineInfo
import ai.bayan.android.engine.SimplificationRequest
import ai.bayan.android.engine.SimplificationResult
import ai.bayan.android.engine.TextSimplifier
import java.security.MessageDigest

/**
 * Common test fixtures and payload constants for Tier 4 Real-World Application Scenario testing.
 */
object E2ETestFixtures {

    /**
     * Deterministic 1024-byte binary payload for test model weights.
     */
    val TEST_PAYLOAD: ByteArray = ByteArray(1024) { (it % 251).toByte() }

    /**
     * SHA-256 hash of [TEST_PAYLOAD].
     */
    val TEST_PAYLOAD_SHA256: String = computeSha256(TEST_PAYLOAD)

    /**
     * Corrupted payload of same length.
     */
    val CORRUPTED_PAYLOAD: ByteArray = ByteArray(1024) { ((it + 13) % 241).toByte() }

    fun computeSha256(bytes: ByteArray): String {
        val digest = MessageDigest.getInstance("SHA-256")
        val hash = digest.digest(bytes)
        return hash.joinToString("") { "%02x".format(it) }
    }
}

/**
 * TextSimplifier implementation designed to simulate unexpected engine failures,
 * timeouts, or corrupted tensor exceptions for error resilience testing.
 */
class FailingTextSimplifier(
    var shouldThrowException: Boolean = false,
    var exceptionToThrow: Exception = IllegalStateException("Tensor runtime memory allocation failed"),
    var errorMessage: String = "فشل معالجة النص في محرك الذكاء الاصطناعي"
) : TextSimplifier {

    override suspend fun simplify(request: SimplificationRequest): SimplificationResult {
        if (shouldThrowException) {
            throw exceptionToThrow
        }
        return SimplificationResult(
            originalText = request.originalText,
            simplifiedText = "",
            isSuccess = false,
            errorMessage = errorMessage
        )
    }

    override fun isModelReady(): Boolean = true

    override fun getEngineInfo(): EngineInfo = EngineInfo(
        name = "FaultInjectionEngine",
        version = "1.0",
        status = "Error Simulation",
        memoryFootprint = "0MB",
        isOnnxReady = false
    )
}
