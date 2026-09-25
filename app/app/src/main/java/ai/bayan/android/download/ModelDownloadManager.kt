package ai.bayan.android.download

import android.content.Context
import androidx.lifecycle.LiveData
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.Data
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequest
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkInfo
import androidx.work.WorkManager
import kotlinx.coroutines.flow.Flow
import java.util.concurrent.TimeUnit

/**
 * Manager helper for scheduling, monitoring, and controlling background AI model downloads.
 * Uses WorkManager to manage unique, resumable, and constrained work requests.
 */
class ModelDownloadManager(private val context: Context) {

    companion object {
        const val WORK_NAME = DownloadModelWorker.WORK_NAME
        const val BACKOFF_DELAY_SECONDS = 15L

        @Volatile
        private var instance: ModelDownloadManager? = null

        fun getInstance(context: Context): ModelDownloadManager {
            return instance ?: synchronized(this) {
                instance ?: ModelDownloadManager(context.applicationContext).also { instance = it }
            }
        }

        /**
         * Convenience static method to enqueue model download with context and Wi-Fi constraint.
         */
        fun enqueueModelDownload(
            context: Context,
            wifiOnly: Boolean = false,
            downloadUrl: String? = null,
            expectedSha256: String? = null,
            modelDir: String? = null
        ): OneTimeWorkRequest {
            return getInstance(context).enqueueDownload(
                wifiOnly = wifiOnly,
                downloadUrl = downloadUrl,
                expectedSha256 = expectedSha256,
                modelDir = modelDir
            )
        }
    }

    /**
     * Builds and configures a [OneTimeWorkRequest] for downloading the model.
     *
     * @param wifiOnly If true, restricts download to unmetered network (Wi-Fi); otherwise any connected network.
     * @param downloadUrl Optional custom download URL override.
     * @param expectedSha256 Optional custom SHA-256 checksum override.
     * @param modelDir Optional custom directory path override.
     */
    fun buildDownloadRequest(
        wifiOnly: Boolean = false,
        downloadUrl: String? = null,
        expectedSha256: String? = null,
        modelDir: String? = null
    ): OneTimeWorkRequest {
        val networkType = if (wifiOnly) NetworkType.UNMETERED else NetworkType.CONNECTED
        val constraints = Constraints.Builder()
            .setRequiredNetworkType(networkType)
            .build()

        val inputDataBuilder = Data.Builder()
        downloadUrl?.let { inputDataBuilder.putString(DownloadModelWorker.KEY_URL, it) }
        expectedSha256?.let { inputDataBuilder.putString(DownloadModelWorker.KEY_EXPECTED_SHA256, it) }
        modelDir?.let { inputDataBuilder.putString(DownloadModelWorker.KEY_MODEL_DIR, it) }

        return OneTimeWorkRequestBuilder<DownloadModelWorker>()
            .setConstraints(constraints)
            .setBackoffCriteria(
                BackoffPolicy.EXPONENTIAL,
                BACKOFF_DELAY_SECONDS,
                TimeUnit.SECONDS
            )
            .setInputData(inputDataBuilder.build())
            .addTag(WORK_NAME)
            .build()
    }

    /**
     * Enqueues unique work "model-download" using [ExistingWorkPolicy.KEEP].
     *
     * @param wifiOnly If true, requires unmetered Wi-Fi connection.
     * @param downloadUrl Optional custom download URL override.
     * @param expectedSha256 Optional custom SHA-256 checksum override.
     * @param modelDir Optional custom directory path override.
     * @return The enqueued [OneTimeWorkRequest].
     */
    fun enqueueDownload(
        wifiOnly: Boolean = false,
        downloadUrl: String? = null,
        expectedSha256: String? = null,
        modelDir: String? = null
    ): OneTimeWorkRequest {
        val request = buildDownloadRequest(wifiOnly, downloadUrl, expectedSha256, modelDir)
        WorkManager.getInstance(context).enqueueUniqueWork(
            WORK_NAME,
            ExistingWorkPolicy.KEEP,
            request
        )
        return request
    }

    /**
     * Convenience alias for [enqueueDownload].
     */
    fun enqueue(wifiOnly: Boolean = false): OneTimeWorkRequest = enqueueDownload(wifiOnly)

    /**
     * Alias matching [enqueueModelDownload] naming convention.
     */
    fun enqueueModelDownload(wifiOnly: Boolean = false): OneTimeWorkRequest = enqueueDownload(wifiOnly)

    /**
     * Returns a [LiveData] of the list of [WorkInfo] for the unique model download work.
     */
    fun getWorkInfosLiveData(): LiveData<List<WorkInfo>> {
        return WorkManager.getInstance(context).getWorkInfosForUniqueWorkLiveData(WORK_NAME)
    }

    /**
     * Alias for [getWorkInfosLiveData].
     */
    fun getWorkInfoLiveData(): LiveData<List<WorkInfo>> = getWorkInfosLiveData()

    /**
     * Returns a [Flow] of the list of [WorkInfo] for the unique model download work.
     */
    fun getWorkInfosFlow(): Flow<List<WorkInfo>> {
        return WorkManager.getInstance(context).getWorkInfosForUniqueWorkFlow(WORK_NAME)
    }

    /**
     * Alias for [getWorkInfosFlow].
     */
    fun getWorkInfoFlow(): Flow<List<WorkInfo>> = getWorkInfosFlow()

    /**
     * Cancels the active model download work request.
     */
    fun cancelDownload() {
        WorkManager.getInstance(context).cancelUniqueWork(WORK_NAME)
    }
}
