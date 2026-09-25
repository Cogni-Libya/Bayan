package ai.bayan.android.download

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import androidx.work.workDataOf
import ai.bayan.android.engine.DefaultModelStore
import ai.bayan.android.engine.ModelStoreProvider
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.withContext
import java.io.File
import java.io.FileOutputStream
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest

/**
 * Resumable background worker that streams AI model weights to disk,
 * supports HTTP Range requests to resume interrupted downloads,
 * computes streaming and post-download SHA-256 digests, and guarantees
 * atomic file rename only upon cryptographic integrity verification.
 */
class DownloadModelWorker(
    appContext: Context,
    params: WorkerParameters
) : CoroutineWorker(appContext, params) {

    companion object {
        const val WORK_NAME = "model-download"
        const val KEY_PROGRESS = "progress"
        const val KEY_URL = "download_url"
        const val KEY_EXPECTED_SHA256 = "expected_sha256"
        const val KEY_MODEL_DIR = "model_dir"
        const val KEY_TARGET_FILENAME = "target_filename"
        const val KEY_ERROR = "error"
        const val PART_EXTENSION = ".part"
    }

    override suspend fun doWork(): Result = withContext(Dispatchers.IO) {
        val modelStore = ModelStoreProvider.getInstance(applicationContext)

        val targetDir = inputData.getString(KEY_MODEL_DIR)?.let { File(it) } ?: modelStore.modelDir()
        if (!targetDir.exists()) {
            targetDir.mkdirs()
        }

        val targetFileName = inputData.getString(KEY_TARGET_FILENAME) ?: modelStore.getModelFile().name
        val targetFile = File(targetDir, targetFileName)
        val partFile = File(targetDir, "$targetFileName$PART_EXTENSION")

        val downloadUrl = inputData.getString(KEY_URL) ?: modelStore.getDownloadUrl()
        val expectedSha256 = inputData.getString(KEY_EXPECTED_SHA256) ?: modelStore.getExpectedSha256()

        // 1. If target file already exists and is valid, return success immediately
        if (targetFile.exists() && targetFile.length() > 0L) {
            val existingSha = DefaultModelStore.calculateSha256(targetFile)
            if (existingSha.equals(expectedSha256, ignoreCase = true)) {
                setProgressAsync(workDataOf(KEY_PROGRESS to 100))
                return@withContext Result.success()
            } else {
                targetFile.delete()
            }
        }

        val existingBytes = if (partFile.exists()) partFile.length() else 0L

        // 2. Open HTTP connection with Range header if partial file exists
        val url = URL(downloadUrl)
        val connection = (url.openConnection() as HttpURLConnection).apply {
            connectTimeout = 15_000
            readTimeout = 30_000
            instanceFollowRedirects = true
            if (existingBytes > 0L) {
                setRequestProperty("Range", "bytes=$existingBytes-")
            }
        }

        try {
            connection.connect()
            val responseCode = connection.responseCode
            val appendMode: Boolean
            val totalBytes: Long

            when (responseCode) {
                HttpURLConnection.HTTP_PARTIAL -> {
                    // HTTP 206: Server accepted Range request, append bytes
                    appendMode = true
                    val contentLength = connection.contentLengthLong
                    totalBytes = if (contentLength > 0L) existingBytes + contentLength else -1L
                }
                HttpURLConnection.HTTP_OK -> {
                    // HTTP 200: Server restarted or Range not supported, truncate/restart from byte 0
                    appendMode = false
                    totalBytes = connection.contentLengthLong
                }
                416 -> {
                    // HTTP 416 Range Not Satisfiable: Part file is out of range or corrupt, delete and retry fresh
                    if (partFile.exists()) {
                        partFile.delete()
                    }
                    return@withContext Result.retry()
                }
                else -> {
                    return@withContext Result.retry()
                }
            }

            var downloadedBytes = if (appendMode) existingBytes else 0L
            val inStreamDigest = if (!appendMode) MessageDigest.getInstance("SHA-256") else null

            connection.inputStream.use { input ->
                FileOutputStream(partFile, appendMode).use { output ->
                    val buffer = ByteArray(8192)
                    var bytesRead: Int
                    var lastReportedPercent = -1

                    while (input.read(buffer).also { bytesRead = it } != -1) {
                        coroutineContext.ensureActive()
                        if (isStopped) {
                            output.flush()
                            return@withContext Result.retry()
                        }

                        output.write(buffer, 0, bytesRead)
                        downloadedBytes += bytesRead
                        inStreamDigest?.update(buffer, 0, bytesRead)

                        if (totalBytes > 0L) {
                            val percent = ((downloadedBytes.toDouble() / totalBytes) * 100).toInt().coerceIn(0, 100)
                            if (percent != lastReportedPercent) {
                                setProgressAsync(workDataOf(KEY_PROGRESS to percent))
                                lastReportedPercent = percent
                            }
                        }
                    }
                    output.flush()
                }
            }

            // 3. Post-stream SHA-256 verification of the completed .part file
            val computedSha256 = DefaultModelStore.calculateSha256(partFile)
            val isValid = computedSha256.equals(expectedSha256, ignoreCase = true)

            if (isValid) {
                // Atomic rename only after checksum passes
                if (targetFile.exists()) {
                    targetFile.delete()
                }
                val renamed = partFile.renameTo(targetFile)
                if (!renamed) {
                    partFile.copyTo(targetFile, overwrite = true)
                    partFile.delete()
                }

                setProgressAsync(workDataOf(KEY_PROGRESS to 100))
                Result.success()
            } else {
                // Integrity violation: Immediately purge corrupted .part file
                if (partFile.exists()) {
                    partFile.delete()
                }
                Result.retry()
            }
        } catch (e: Exception) {
            Result.retry()
        } finally {
            connection.disconnect()
        }
    }
}
