package ai.bayan.android.ui

import ai.bayan.android.model.ModelCatalog
import ai.bayan.android.AppContainer
import ai.bayan.android.engine.ModelNotInstalledException
import ai.bayan.android.engine.SimplifyEvent
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch

sealed interface SimplifyState {
    data object Idle : SimplifyState
    data object LoadingModel : SimplifyState
    /**
     * [partial] is the text simplified so far, streamed token by token; its first [committed] characters are finished
     * sentences. [run] identifies this simplification, so reading aloud can follow it from Running into Done.
     */
    data class Running(val source: String, val partial: String, val committed: Int, val done: Int, val total: Int, val run: Int) : SimplifyState
    data class Done(val source: String, val result: String, val modelId: String, val millis: Long, val run: Int) : SimplifyState
    data class NeedsModel(val modelId: String) : SimplifyState
    data class Failed(val message: String?) : SimplifyState
}

val SimplifyState.isBusy: Boolean get() = this is SimplifyState.LoadingModel || this is SimplifyState.Running

/** One simplification at a time with the active model; shared by the home screen and the "تبسيط" sheet. */
class SimplifySession(private val app: AppContainer, private val scope: CoroutineScope) {
    private val _state = MutableStateFlow<SimplifyState>(SimplifyState.Idle)
    val state: StateFlow<SimplifyState> = _state.asStateFlow()
    private var job: Job? = null
    private var runs = 0

    fun start(text: String, saveToHistory: Boolean = true) {
        val source = text.trim()
        if (source.isEmpty()) return
        job?.cancel()
        val run = ++runs
        job = scope.launch {
            val settings = app.settings.settings.first()
            val modelId = settings.activeModel
            val beams = if (settings.moreFaithful) ModelCatalog.get(modelId).beams else 1
            try {
                app.simplifier.simplify(source, modelId, beams).collect { event ->
                    _state.value = when (event) {
                        SimplifyEvent.LoadingModel -> SimplifyState.LoadingModel
                        is SimplifyEvent.Progress -> SimplifyState.Running(source, event.text, event.committed, event.done, event.total, run)
                        is SimplifyEvent.Finished -> SimplifyState.Done(source, event.text, event.modelId, event.millis, run)
                    }
                }
                val done = _state.value as? SimplifyState.Done
                if (saveToHistory && done != null) app.history.add(done.source, done.result, done.modelId)
            } catch (e: CancellationException) {
                throw e
            } catch (e: ModelNotInstalledException) {
                _state.value = SimplifyState.NeedsModel(e.modelId)
            } catch (e: Exception) {
                _state.value = SimplifyState.Failed(e.message)
            }
        }
    }

    fun cancel() {
        job?.cancel()
        job = null
        _state.value = SimplifyState.Idle
    }

    fun reset() = cancel()
}
