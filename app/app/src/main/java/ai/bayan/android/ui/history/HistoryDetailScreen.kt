package ai.bayan.android.ui.history

import android.text.format.DateUtils
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.ArrowBack
import androidx.compose.material.icons.rounded.DeleteOutline
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExperimentalMaterial3ExpressiveApi
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MediumFlexibleTopAppBar
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.material3.rememberTopAppBarState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.input.nestedscroll.nestedScroll
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import ai.bayan.android.AppContainer
import ai.bayan.android.R
import ai.bayan.android.data.Settings
import ai.bayan.android.model.ModelCatalog
import ai.bayan.android.ui.appViewModel
import ai.bayan.android.ui.components.OriginalToggle
import ai.bayan.android.ui.components.ReaderActions
import ai.bayan.android.ui.components.ReaderText
import ai.bayan.android.ui.components.spokenRange
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

class HistoryDetailViewModel(private val app: AppContainer, private val id: Long) : ViewModel() {
    val item = app.history.items.map { list -> list.firstOrNull { it.id == id } }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), app.history.items.value.firstOrNull { it.id == id })
    val settings = app.settings.settings.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), Settings())
    fun delete() = viewModelScope.launch { app.readAloud.stop(); app.history.remove(id) }
    override fun onCleared() = app.readAloud.stop()
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalMaterial3ExpressiveApi::class)
@Composable
fun HistoryDetailScreen(id: Long, onBack: () -> Unit, vm: HistoryDetailViewModel = appViewModel { HistoryDetailViewModel(it, id) }) {
    val item by vm.item.collectAsStateWithLifecycle()
    val settings by vm.settings.collectAsStateWithLifecycle()
    val context = LocalContext.current
    var showOriginal by rememberSaveable { mutableStateOf(false) }
    val snackbar = remember { SnackbarHostState() }
    val scope = rememberCoroutineScope()
    val copied = stringResource(R.string.copied)
    val appBar = TopAppBarDefaults.exitUntilCollapsedScrollBehavior(rememberTopAppBarState())

    Scaffold(
        modifier = Modifier.nestedScroll(appBar.nestedScrollConnection),
        topBar = {
            MediumFlexibleTopAppBar(
                title = {
                    Text(item?.let { DateUtils.formatDateTime(context, it.createdAt, DateUtils.FORMAT_SHOW_DATE or DateUtils.FORMAT_SHOW_TIME) } ?: "")
                },
                subtitle = { item?.let { Text(stringResource(ModelCatalog.get(it.modelId).title)) } },
                navigationIcon = {
                    IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Rounded.ArrowBack, stringResource(R.string.action_back)) }
                },
                actions = {
                    IconButton(onClick = { vm.delete(); onBack() }) { Icon(Icons.Rounded.DeleteOutline, stringResource(R.string.action_delete)) }
                },
                scrollBehavior = appBar,
            )
        },
        snackbarHost = { SnackbarHost(snackbar) },
    ) { padding ->
        val current = item ?: return@Scaffold
        Box(Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.TopCenter) {
            Column(
                Modifier.widthIn(max = 720.dp).fillMaxWidth().verticalScroll(rememberScrollState()).padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                OriginalToggle(showOriginal, { showOriginal = it }, Modifier.fillMaxWidth())
                val key = "history:${current.id}:${if (showOriginal) "o" else "s"}"
                AnimatedContent(showOriginal, transitionSpec = { fadeIn() togetherWith fadeOut() }, label = "history-text") { original ->
                    ReaderText(
                        if (original) current.source else current.result,
                        settings.reader,
                        highlight = if (settings.highlightWhileReading) spokenRange(key) else null,
                    )
                }
                ReaderActions(
                    if (showOriginal) current.source else current.result,
                    key,
                    settings.speechRate,
                    onCopied = { scope.launch { snackbar.showSnackbar(copied) } },
                )
            }
        }
    }
}
