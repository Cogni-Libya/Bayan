package ai.bayan.android.ui

import androidx.compose.runtime.Composable
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewmodel.compose.viewModel
import ai.bayan.android.AppContainer
import ai.bayan.android.ui.components.LocalAppContainer

/** A ViewModel built from the app's [AppContainer], scoped to the current screen. */
@Composable
inline fun <reified VM : ViewModel> appViewModel(crossinline create: (AppContainer) -> VM): VM {
    val app = LocalAppContainer.current
    return viewModel { create(app) }
}
