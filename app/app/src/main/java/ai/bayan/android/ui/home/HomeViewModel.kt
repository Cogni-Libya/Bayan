package ai.bayan.android.ui.home

import androidx.compose.foundation.text.input.TextFieldState
import androidx.compose.foundation.text.input.clearText
import androidx.compose.foundation.text.input.setTextAndPlaceCursorAtEnd
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import ai.bayan.android.AppContainer
import ai.bayan.android.data.Settings
import ai.bayan.android.model.ModelCatalog
import ai.bayan.android.model.ModelInfo
import ai.bayan.android.model.ModelState
import ai.bayan.android.ui.SimplifySession
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn

data class ActiveModel(val info: ModelInfo, val state: ModelState)

class HomeViewModel(private val app: AppContainer) : ViewModel() {
    val input = TextFieldState()
    val session = SimplifySession(app, viewModelScope)

    val settings: StateFlow<Settings> =
        app.settings.settings.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), Settings())

    val activeModel: StateFlow<ActiveModel?> =
        combine(app.settings.settings, app.modelStore.states) { s, states ->
            val info = ModelCatalog.get(s.activeModel)
            ActiveModel(info, states[info.id] ?: ModelState.NotInstalled)
        }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), null)

    fun simplify() {
        app.readAloud.stop()
        session.start(input.text.toString())
        app.readAloud.warmUp()
    }

    fun receive(text: String) {
        input.setTextAndPlaceCursorAtEnd(text)
        simplify()
    }

    fun clear() {
        app.readAloud.stop()
        input.clearText()
        session.reset()
    }

    fun cancel() = session.cancel()

    override fun onCleared() {
        app.readAloud.stop()
    }
}
