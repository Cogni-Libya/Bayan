package ai.bayan.android.engine

import java.io.File

/**
 * Interface contract defining local AI model management, integrity checking,
 * and downloading capabilities for the Bayan simplification engine.
 */
interface ModelStore {
    /**
     * Checks if the required model file exists in [modelDir] and passes SHA-256 integrity verification.
     * If the file is present but corrupted, it is automatically purged and false is returned.
     *
     * @return true if the model file is present and verified, false otherwise.
     */
    fun isReady(): Boolean

    /**
     * Downloads the required model weights asynchronously, streaming progress updates.
     *
     * @param onProgress Callback receiving progress fraction between 0.0f and 1.0f.
     */
    suspend fun download(onProgress: (Float) -> Unit)

    /**
     * Returns the dedicated directory on local storage where model files are stored.
     */
    fun modelDir(): File

    /**
     * Returns the target model file.
     */
    fun getModelFile(): File

    /**
     * Returns the temporary partial download file (.part).
     */
    fun getPartFile(): File

    /**
     * Returns the expected SHA-256 checksum for the model file.
     */
    fun getExpectedSha256(): String

    /**
     * Returns the remote URL for downloading the model.
     */
    fun getDownloadUrl(): String

    /**
     * Removes both the partial (.part) and final model files if corrupted or invalid.
     */
    fun deleteCorruptedFiles()
}
