package ai.bayan.android.data

import android.content.Context
import java.io.File
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.serialization.Serializable
import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.json.Json

@Serializable
data class HistoryItem(
    val id: Long,
    val source: String,
    val result: String,
    val modelId: String,
    val createdAt: Long,
)

/** The last simplifications, kept only on this device. */
class HistoryRepository(context: Context) {
    private val file = File(context.filesDir, "history.json")
    private val json = Json { ignoreUnknownKeys = true }
    private val lock = Mutex()
    private val _items = MutableStateFlow<List<HistoryItem>>(emptyList())
    val items: StateFlow<List<HistoryItem>> = _items.asStateFlow()

    suspend fun load() = withContext(Dispatchers.IO) {
        _items.value = runCatching { json.decodeFromString(ListSerializer(HistoryItem.serializer()), file.readText()) }
            .getOrDefault(emptyList())
    }

    suspend fun add(source: String, result: String, modelId: String) = update { list ->
        val now = System.currentTimeMillis()
        (listOf(HistoryItem(now, source, result, modelId, now)) + list.filterNot { it.source == source }).take(MAX)
    }

    suspend fun remove(id: Long) = update { list -> list.filterNot { it.id == id } }

    /** Puts back an item removed by mistake, in its original place. */
    suspend fun restore(item: HistoryItem) = update { list ->
        (list.filterNot { it.id == item.id } + item).sortedByDescending { it.createdAt }.take(MAX)
    }

    suspend fun clear() = update { emptyList() }

    private suspend fun update(change: (List<HistoryItem>) -> List<HistoryItem>) = lock.withLock {
        val next = change(_items.value)
        _items.value = next
        withContext(Dispatchers.IO) { file.writeText(json.encodeToString(ListSerializer(HistoryItem.serializer()), next)) }
    }

    companion object { private const val MAX = 50 }
}
