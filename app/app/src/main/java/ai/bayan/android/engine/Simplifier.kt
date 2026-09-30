package ai.bayan.android.engine

import ai.bayan.android.model.ModelStore
import android.util.Log
import java.io.File
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.buffer
import kotlinx.coroutines.flow.channelFlow
import kotlinx.coroutines.flow.flowOn
import kotlinx.coroutines.isActive
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext

sealed interface SimplifyEvent {
    data object LoadingModel : SimplifyEvent
    /**
     * [text] is everything simplified so far, including the sentence being decoded. Its first [committed] characters
     * are finished sentences that will not change; [done] of [total] sentences are finished.
     */
    data class Progress(val text: String, val committed: Int, val done: Int, val total: Int) : SimplifyEvent
    data class Finished(val text: String, val modelId: String, val millis: Long) : SimplifyEvent
}

class ModelNotInstalledException(val modelId: String) : IllegalStateException("Model $modelId is not installed")

/** Simplifies whole texts sentence by sentence with the active on-device model, streaming each token as it is decoded. */
class Simplifier(private val store: ModelStore) {
    private val lock = Mutex()
    private var engine: Seq2SeqEngine? = null
    private var engineDir: File? = null

    fun simplify(text: String, modelId: String): Flow<SimplifyEvent> = channelFlow {
        val dir = store.installedDir(modelId) ?: throw ModelNotInstalledException(modelId)
        val started = System.currentTimeMillis()
        lock.withLock {
            if (engineDir != dir) {
                send(SimplifyEvent.LoadingModel)
                release()
                val t = System.nanoTime()
                engine = withContext(Dispatchers.IO) { Seq2SeqEngine(dir) }
                engineDir = dir
                Log.i(TAG, "loaded $modelId in ${(System.nanoTime() - t) / 1_000_000} ms")
            }
            val e = engine!!
            val paragraphs = ArabicText.paragraphs(ArabicText.stripTashkeel(text))
            val total = paragraphs.sumOf { it.size }
            var done = 0
            val result = StringBuilder()
            send(SimplifyEvent.Progress("", 0, 0, total))
            for ((p, sentences) in paragraphs.withIndex()) {
                if (p > 0) result.append("\n\n")
                for ((s, sentence) in sentences.withIndex()) {
                    if (s > 0) result.append(' ')
                    val committed = result.length
                    val t = System.nanoTime()
                    var firstToken = 0L
                    val out = if (ArabicText.wordCount(sentence) < MIN_WORDS) {
                        sentence
                    } else {
                        e.generate(sentence, isCancelled = { !isActive }) { partial ->
                            if (firstToken == 0L) firstToken = System.nanoTime() - t
                            trySend(SimplifyEvent.Progress(result.toString() + partial, committed, done, total))
                        }
                    }
                    Log.i(TAG, "sentence ${done + 1}/$total: first token ${firstToken / 1_000_000} ms, whole ${(System.nanoTime() - t) / 1_000_000} ms")
                    if (!isActive) return@withLock
                    result.append(faithful(sentence, out))
                    done++
                    send(SimplifyEvent.Progress(result.toString(), result.length, done, total))
                }
            }
            send(SimplifyEvent.Finished(result.toString(), modelId, System.currentTimeMillis() - started))
        }
    }.buffer(Channel.CONFLATED).flowOn(Dispatchers.Default)

    /** The model's sentence, unless it drifted away from the source's meaning; then the source is kept as it was. */
    private fun faithful(sentence: String, out: String): String =
        if (out.isBlank() || ArabicText.retention(sentence, out) < MIN_RETENTION) sentence
        else ArabicText.fixPunctuation(sentence, out)

    /** Frees the model's memory when no simplification is running (e.g. when the system asks the app to trim memory). */
    fun releaseIfIdle() {
        if (!lock.tryLock()) return
        try { release() } finally { lock.unlock() }
    }

    private fun release() {
        engine?.close()
        engine = null
        engineDir = null
    }

    private companion object {
        const val TAG = "Bayan"
        /** Headings and fragments: the model was trained on sentences of 10+ words and invents text for shorter ones. */
        const val MIN_WORDS = 6
        const val MIN_RETENTION = 0.35f
    }
}
