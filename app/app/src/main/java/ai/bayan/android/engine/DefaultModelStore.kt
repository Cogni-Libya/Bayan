package ai.bayan.android.engine

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.withContext
import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.io.InputStream
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest

/**
 * Default implementation of [ModelStore] that manages model files in internal app storage,
 * performs streaming SHA-256 integrity checks, and supports resumable downloads.
 */
class DefaultModelStore(
    private val context: Context,
    private val downloadUrl: String = DEFAULT_DOWNLOAD_URL,
    private val expectedSha256: String = DEFAULT_EXPECTED_SHA256,
    private val modelFileName: String = DEFAULT_MODEL_FILENAME,
    private val customModelDir: File? = null
) : ModelStore {

    companion object {
        const val DEFAULT_DOWNLOAD_URL =
            "https://huggingface.co/google/t5-efficient-tiny/resolve/main/pytorch_model.bin"
        const val DEFAULT_EXPECTED_SHA256 =
            "b840cd5afdcc806b8175fed5a8800a5aa8be1beb60aab8ab7f650728b122dac2"
        const val DEFAULT_MODEL_FILENAME = "pytorch_model.bin"
        const val PART_EXTENSION = ".part"

        /**
         * Computes the SHA-256 digest of a [File] using streaming chunks to avoid loading
         * large model weights entirely into memory.
         *
         * @param file The file to digest.
         * @return The lowercase hexadecimal SHA-256 string, or empty string if file does not exist.
         */
        fun calculateSha256(file: File): String {
            if (!file.exists() || !file.isFile) return ""
            return file.inputStream().use { input ->
                calculateSha256(input)
            }
        }

        /**
         * Computes the SHA-256 digest from an [InputStream] using streaming chunks.
         *
         * @param inputStream The stream to digest.
         * @return The lowercase hexadecimal SHA-256 string.
         */
        fun calculateSha256(inputStream: InputStream): String {
            val digest = MessageDigest.getInstance("SHA-256")
            val buffer = ByteArray(8192)
            var bytesRead: Int
            while (inputStream.read(buffer).also { bytesRead = it } != -1) {
                digest.update(buffer, 0, bytesRead)
            }
            return digest.digest().joinToString("") { "%02x".format(it) }
        }
    }

    override fun isReady(): Boolean {
        val modelFile = getModelFile()
        if (!modelFile.exists() || !modelFile.isFile || modelFile.length() == 0L) {
            return false
        }

        val actualSha256 = calculateSha256(modelFile)
        return if (actualSha256.equals(expectedSha256, ignoreCase = true)) {
            true
        } else {
            deleteCorruptedFiles()
            false
        }
    }

    override fun modelDir(): File {
        val dir = customModelDir ?: File(context.filesDir, "models")
        if (!dir.exists()) {
            dir.mkdirs()
        }
        return dir
    }

    override fun getModelFile(): File = File(modelDir(), modelFileName)

    override fun getPartFile(): File = File(modelDir(), "$modelFileName$PART_EXTENSION")

    override fun getExpectedSha256(): String = expectedSha256

    override fun getDownloadUrl(): String = downloadUrl

    override fun deleteCorruptedFiles() {
        val modelFile = getModelFile()
        if (modelFile.exists()) {
            modelFile.delete()
        }
        val partFile = getPartFile()
        if (partFile.exists()) {
            partFile.delete()
        }
    }

    override suspend fun download(onProgress: (Float) -> Unit): Unit = withContext(Dispatchers.IO) {
        if (isReady()) {
            onProgress(1.0f)
            return@withContext
        }

        val targetFile = getModelFile()
        val partFile = getPartFile()
        val existingBytes = if (partFile.exists()) partFile.length() else 0L

        val connection = (URL(downloadUrl).openConnection() as HttpURLConnection).apply {
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
                    appendMode = true
                    val contentLength = connection.contentLengthLong
                    totalBytes = if (contentLength > 0) existingBytes + contentLength else -1L
                }
                HttpURLConnection.HTTP_OK -> {
                    appendMode = false
                    totalBytes = connection.contentLengthLong
                }
                416 -> { // Range Not Satisfiable
                    partFile.delete()
                    throw IOException("HTTP 416 Range Not Satisfiable, deleted stale part file")
                }
                else -> {
                    throw IOException("Unexpected HTTP response code: $responseCode")
                }
            }

            var downloadedBytes = if (appendMode) existingBytes else 0L
            connection.inputStream.use { input ->
                FileOutputStream(partFile, appendMode).use { output ->
                    val buffer = ByteArray(8192)
                    var bytesRead: Int
                    var lastReportedFraction = -1f

                    while (input.read(buffer).also { bytesRead = it } != -1) {
                        coroutineContext.ensureActive()
                        output.write(buffer, 0, bytesRead)
                        downloadedBytes += bytesRead

                        if (totalBytes > 0) {
                            val fraction = (downloadedBytes.toFloat() / totalBytes).coerceIn(0f, 1f)
                            if (fraction - lastReportedFraction >= 0.01f || fraction == 1f) {
                                onProgress(fraction)
                                lastReportedFraction = fraction
                            }
                        }
                    }
                    output.flush()
                }
            }

            val actualSha256 = calculateSha256(partFile)
            if (actualSha256.equals(expectedSha256, ignoreCase = true)) {
                if (targetFile.exists()) {
                    targetFile.delete()
                }
                val renamed = partFile.renameTo(targetFile)
                if (!renamed) {
                    partFile.copyTo(targetFile, overwrite = true)
                    partFile.delete()
                }
                onProgress(1.0f)
            } else {
                deleteCorruptedFiles()
                throw IOException(
                    "Downloaded file checksum mismatch: expected $expectedSha256, got $actualSha256"
                )
            }
        } finally {
            connection.disconnect()
        }
    }
}
