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

/**
 * Simplifies whole texts sentence by sentence with the active on-device model: greedy models stream each token as it
 * is decoded, beam-search models show each sentence when it is final.
 */
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
            val steps = ArabicText.plan(text, MIN_WORDS)
            val openEnded = ArabicText.isOpenEnded(text)
            val lastSentence = steps.indexOfLast { it is ArabicText.Step.Sentence }
            val total = steps.count { it is ArabicText.Step.Sentence }
            var done = 0
            val result = StringBuilder()
            send(SimplifyEvent.Progress("", 0, 0, total))
            for ((k, step) in steps.withIndex()) {
                val prev = steps.getOrNull(k - 1)
                if (prev != null) result.append(if (prev.paragraph != step.paragraph) "\n" else " ")
                when (step) {
                    is ArabicText.Step.Protected -> result.append(step.text) // scripture and set poetry: never rewritten
                    is ArabicText.Step.Bullet -> result.append(step.marker)
                    is ArabicText.Step.Sentence -> {
                        val committed = result.length
                        val t = System.nanoTime()
                        var firstToken = 0L
                        var out = if (!step.toModel) step.text else {
                            val raw = e.generate(step.input, isCancelled = { !isActive }) { partial ->
                                if (firstToken == 0L) firstToken = System.nanoTime() - t
                                trySend(SimplifyEvent.Progress(result.toString() + ArabicText.matchDigitStyle(step.text, partial), committed, done, total))
                            }
                            shown(step, raw)
                        }
                        if (k == lastSentence && openEnded) out = ArabicText.keepOpenEnding(step.text, out)
                        val whole = (System.nanoTime() - t) / 1_000_000
                        Log.i(TAG, if (e.streams) "sentence ${done + 1}/$total: first token ${firstToken / 1_000_000} ms, whole $whole ms"
                                   else "sentence ${done + 1}/$total: ${e.spec.num_beams} beams, $whole ms")
                        if (!isActive) return@withLock
                        result.append(out)
                        done++
                    }
                }
                send(SimplifyEvent.Progress(result.toString(), result.length, done, total))
            }
            send(SimplifyEvent.Finished(result.toString(), modelId, System.currentTimeMillis() - started))
        }
    }.buffer(Channel.CONFLATED).flowOn(Dispatchers.Default)

    /** The model's sentence, unless a guard stops it (ArabicText.fallback); then the source sentence is kept. */
    private fun shown(step: ArabicText.Step.Sentence, raw: String): String {
        val reason = ArabicText.fallback(step.input, raw, MIN_RETENTION)
        if (reason != null) {
            Log.i(TAG, "kept the source sentence: $reason")
            return step.text
        }
        return ArabicText.matchDigitStyle(step.text, ArabicText.fixPunctuation(step.input, raw))
    }

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
