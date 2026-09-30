package ai.bayan.android.ui.process

import ai.bayan.android.AppContainer
import ai.bayan.android.data.Settings
import ai.bayan.android.speech.SpeechState
import ai.bayan.android.ui.SimplifySession
import ai.bayan.android.ui.SimplifyState
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

/**
 * The "تبسيط" selection being simplified and read, kept for the life of the app rather than of the panel, so the
 * panel can be minimized back to the app the text came from while Bayan keeps reading, and reopened where it was.
 */
class OverlaySession(private val app: AppContainer, private val scope: CoroutineScope) {
    val simplify = SimplifySession(app, scope)

    /** The selection being worked on. */
    var text: String? = null
        private set

    private val _minimized = MutableStateFlow(false)
    /** True while the panel is closed but Bayan is still reading (controls live in the media notification). */
    val minimized: StateFlow<Boolean> = _minimized.asStateFlow()

    /** Where reading was last stopped, so play resumes from that sentence. */
    private var resumeAt = 0
    private val settings = app.settings.settings.stateIn(scope, SharingStarted.Eagerly, Settings())

    init {
        // Keep reading the simplified text as it streams in, whether or not the panel is on screen.
        scope.launch(Dispatchers.Main) {
            simplify.state.collect { st ->
                val (readable, complete) = readable(st) ?: return@collect
                val key = key(st)
                if (app.readAloud.isSpeaking(key)) app.readAloud.follow(key, readable, complete, rate())
            }
        }
        scope.launch(Dispatchers.Main) {
            app.readAloud.state.collect { s -> if (s is SpeechState.Speaking && s.key == key(simplify.state.value) && s.end > s.start) resumeAt = s.start }
        }
    }

    /** Simplifies [selection], unless it is the one already open (after rotating, or reopening from the notification). */
    fun open(selection: String) {
        if (selection == text) return
        text = selection
        resumeAt = 0
        app.readAloud.stop()
        simplify.start(selection)
        app.readAloud.warmUp()
    }

    fun setMinimized(value: Boolean) { _minimized.value = value }

    /** The reader said "Not now" to displaying over other apps; minimizing then uses the media controls alone. */
    var floatingDeclined = false

    val isReading: Boolean get() = app.readAloud.isSpeaking(key(simplify.state.value))

    /** Reading key of the simplified text in [state]; the panel shows the original under a different key. */
    fun key(state: SimplifyState, original: Boolean = false): String {
        val run = (state as? SimplifyState.Running)?.run ?: (state as? SimplifyState.Done)?.run ?: 0
        return "sheet:$run:${if (original) "o" else "s"}"
    }

    /** Plays from the sentence where reading stopped (or from the start). */
    fun play() {
        val st = simplify.state.value
        val (readable, complete) = readable(st) ?: return
        app.readAloud.stop()
        app.readAloud.follow(key(st), readable, complete, rate(), startAt = resumeAt)
    }

    fun pause() = app.readAloud.stop()

    fun close() {
        app.readAloud.stop()
        _minimized.value = false
        text = null
        simplify.reset()
    }

    /** The short excerpt shown in the media notification. */
    fun title(): String = "\u200F" + (readable(simplify.state.value)?.first ?: text.orEmpty()).take(80)  // RLM: right-to-left title

    private fun readable(st: SimplifyState): Pair<String, Boolean>? = when (st) {
        is SimplifyState.Running -> st.partial.take(st.committed) to false
        is SimplifyState.Done -> st.result to true
        else -> null
    }

    private fun rate(): Float = settings.value.speechRate
}
