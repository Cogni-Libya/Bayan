package ai.bayan.android.model

import android.content.Context
import android.net.Uri
import androidx.work.Constraints
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkInfo
import androidx.work.WorkManager
import androidx.work.workDataOf
import java.io.File
import java.util.zip.ZipInputStream
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.withContext

sealed interface ModelState {
    data object NotInstalled : ModelState
    data object Queued : ModelState
    data class Downloading(val progress: Float, val downloadedBytes: Long) : ModelState
    data object Installed : ModelState
    data class Failed(val reason: String?) : ModelState
}

/**
 * Where the models live on the device: app-specific storage (no permission needed, removed with the app).
 * Downloads run in [ModelDownloadWorker] so they survive the app going to the background.
 */
class ModelStore(private val context: Context) {
    private val root: File = (context.getExternalFilesDir("models") ?: File(context.filesDir, "models")).apply { mkdirs() }
    private val workManager = WorkManager.getInstance(context)
    private val installedVersion = MutableStateFlow(0)

    fun dirOf(id: String): File = File(root, id)

    /** The download's folder if all of its files are in place. */
    fun installedDir(id: String): File? {
        val names = Downloads.find(id)?.files?.map { it.name } ?: REQUIRED
        return dirOf(id).takeIf { dir -> names.all { File(dir, it).isFile } }
    }

    fun installedBytes(id: String): Long = dirOf(id).listFiles()?.sumOf { it.length() } ?: 0L

    val states: Flow<Map<String, ModelState>> = combine(
        workManager.getWorkInfosByTagFlow(ModelDownloadWorker.TAG),
        installedVersion,
    ) { infos, _ ->
        Downloads.all.associate { model ->
            val mine = infos.filter { it.tags.contains(model.id) }
            val info = mine.firstOrNull { !it.state.isFinished } ?: mine.lastOrNull { it.state == WorkInfo.State.FAILED }
            model.id to when {
                info?.state == WorkInfo.State.RUNNING -> ModelState.Downloading(
                    info.progress.getFloat(ModelDownloadWorker.KEY_PROGRESS, 0f),
                    info.progress.getLong(ModelDownloadWorker.KEY_BYTES, 0L),
                )
                info?.state == WorkInfo.State.ENQUEUED || info?.state == WorkInfo.State.BLOCKED -> ModelState.Queued
                installedDir(model.id) != null -> ModelState.Installed
                info?.state == WorkInfo.State.FAILED -> ModelState.Failed(info.outputData.getString(ModelDownloadWorker.KEY_ERROR))
                else -> ModelState.NotInstalled
            }
        }
    }

    fun download(id: String, wifiOnly: Boolean) {
        val request = OneTimeWorkRequestBuilder<ModelDownloadWorker>()
            .setInputData(workDataOf(ModelDownloadWorker.KEY_MODEL to id))
            .setConstraints(
                Constraints.Builder()
                    .setRequiredNetworkType(if (wifiOnly) NetworkType.UNMETERED else NetworkType.CONNECTED)
                    .setRequiresStorageNotLow(true)
                    .build(),
            )
            .addTag(ModelDownloadWorker.TAG)
            .addTag(id)
            .build()
        workManager.enqueueUniqueWork("download-$id", ExistingWorkPolicy.KEEP, request)
    }

    fun cancelDownload(id: String) {
        workManager.cancelUniqueWork("download-$id")
        workManager.pruneWork()
    }

    suspend fun delete(id: String) = withContext(Dispatchers.IO) {
        dirOf(id).deleteRecursively()
        installedVersion.value++
    }

    /** Installs a model shared as a .zip of its folder; returns the model id. */
    suspend fun importZip(uri: Uri): String = withContext(Dispatchers.IO) {
        val staging = File(root, ".import").apply { deleteRecursively(); mkdirs() }
        context.contentResolver.openInputStream(uri).use { input ->
            ZipInputStream(requireNotNull(input) { "Cannot open file" }).use { zip ->
                generateSequence { zip.nextEntry }.filter { !it.isDirectory }.forEach { entry ->
                    val name = entry.name.substringAfterLast('/')
                    if (name in REQUIRED) File(staging, name).outputStream().use { zip.copyTo(it) }
                }
            }
        }
        require(REQUIRED.all { File(staging, it).isFile }) { "The file is not a Bayan model" }
        val id = Regex("\"id\"\\s*:\\s*\"([a-z0-9_]+)\"").find(File(staging, "bayan_model.json").readText())?.groupValues?.get(1)
            ?: error("The model has no id")
        dirOf(id).deleteRecursively()
        check(staging.renameTo(dirOf(id))) { "Could not install the model" }
        installedVersion.value++
        id
    }

    internal fun markChanged() { installedVersion.value++ }

    companion object {
        val REQUIRED = listOf("bayan_model.json", "tokenizer.json", "encoder.onnx", "decoder.onnx")
    }
}
