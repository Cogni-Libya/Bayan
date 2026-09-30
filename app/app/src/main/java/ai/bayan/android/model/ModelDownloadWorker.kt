package ai.bayan.android.model

import ai.bayan.android.BayanApp
import ai.bayan.android.BuildConfig
import ai.bayan.android.R
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.content.pm.ServiceInfo
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.work.CoroutineWorker
import androidx.work.ForegroundInfo
import androidx.work.WorkerParameters
import androidx.work.workDataOf
import java.io.File
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.withContext

/** Downloads a model's files with resume support, verifies their SHA-256, then moves them into place. */
class ModelDownloadWorker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        val model = Downloads.find(inputData.getString(KEY_MODEL) ?: return Result.failure()) ?: return Result.failure()
        val store = (applicationContext as BayanApp).container.modelStore
        val target = store.dirOf(model.id)
        val staging = File(target.parentFile, ".${model.id}.part").apply { mkdirs() }
        setForeground(foregroundInfo(model, 0))
        return try {
            var done = 0L
            for (file in model.files) {
                val dest = File(staging, file.name)
                download(file.url ?: "${BuildConfig.MODEL_BASE_URL}/${model.id}/${file.name}", dest, file) { bytes ->
                    val total = done + bytes
                    val progress = total.toFloat() / model.bytes
                    setProgress(workDataOf(KEY_PROGRESS to progress, KEY_BYTES to total))
                    setForeground(foregroundInfo(model, (progress * 100).toInt()))
                }
                if (sha256(dest) != file.sha256) { dest.delete(); throw IOException("Checksum mismatch for ${file.name}") }
                done += file.bytes
            }
            target.deleteRecursively()
            if (!staging.renameTo(target)) throw IOException("Could not move the model into place")
            store.markChanged()
            Result.success()
        } catch (e: Exception) {
            if (runAttemptCount < 3 && e is IOException && e.message?.startsWith("Checksum") != true) Result.retry()
            else Result.failure(workDataOf(KEY_ERROR to (e.message ?: e.javaClass.simpleName)))
        }
    }

    private suspend fun download(url: String, dest: File, file: ModelFile, onProgress: suspend (Long) -> Unit) =
        withContext(Dispatchers.IO) {
            if (dest.length() == file.bytes) { onProgress(file.bytes); return@withContext }
            val conn = (URL(url).openConnection() as HttpURLConnection).apply {
                connectTimeout = 20_000; readTimeout = 30_000; instanceFollowRedirects = true
                if (dest.length() in 1 until file.bytes) setRequestProperty("Range", "bytes=${dest.length()}-")
            }
            try {
                val resumed = conn.responseCode == HttpURLConnection.HTTP_PARTIAL
                if (conn.responseCode !in 200..299) throw IOException("HTTP ${conn.responseCode} for ${file.name}")
                var written = if (resumed) dest.length() else 0L
                java.io.FileOutputStream(dest, resumed).use { out ->
                    conn.inputStream.use { input ->
                        val buf = ByteArray(1 shl 16)
                        var lastReport = 0L
                        while (true) {
                            ensureActive()
                            val n = input.read(buf)
                            if (n < 0) break
                            out.write(buf, 0, n)
                            written += n
                            if (written - lastReport > 2_000_000) { lastReport = written; onProgress(written) }
                        }
                    }
                }
                onProgress(written)
            } finally {
                conn.disconnect()
            }
        }

    private fun sha256(file: File): String {
        val md = MessageDigest.getInstance("SHA-256")
        file.inputStream().use { input ->
            val buf = ByteArray(1 shl 16)
            while (true) { val n = input.read(buf); if (n < 0) break; md.update(buf, 0, n) }
        }
        return md.digest().joinToString("") { "%02x".format(it) }
    }

    private fun foregroundInfo(model: Downloadable, percent: Int): ForegroundInfo {
        val nm = applicationContext.getSystemService(NotificationManager::class.java)
        if (nm.getNotificationChannel(CHANNEL) == null) {
            nm.createNotificationChannel(
                NotificationChannel(CHANNEL, applicationContext.getString(R.string.notification_channel_downloads), NotificationManager.IMPORTANCE_LOW),
            )
        }
        val notification = NotificationCompat.Builder(applicationContext, CHANNEL)
            .setSmallIcon(R.drawable.ic_stat_bayan)
            .setContentTitle(applicationContext.getString(R.string.notification_downloading, applicationContext.getString(model.title)))
            .setProgress(100, percent, percent == 0)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .build()
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            ForegroundInfo(NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC)
        } else {
            ForegroundInfo(NOTIFICATION_ID, notification)
        }
    }

    companion object {
        const val TAG = "model-download"
        const val KEY_MODEL = "model"
        const val KEY_PROGRESS = "progress"
        const val KEY_BYTES = "bytes"
        const val KEY_ERROR = "error"
        private const val CHANNEL = "downloads"
        private const val NOTIFICATION_ID = 42
    }
}
