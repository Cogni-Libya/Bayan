package ai.bayan.android.ui.models

import android.Manifest
import android.net.Uri
import android.os.Build
import android.text.format.Formatter
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.ArrowBack
import androidx.compose.material.icons.rounded.Close
import androidx.compose.material.icons.rounded.DeleteOutline
import androidx.compose.material.icons.rounded.Download
import androidx.compose.material.icons.rounded.FileOpen
import androidx.compose.material.icons.rounded.Lock
import androidx.compose.material.icons.rounded.Refresh
import androidx.compose.material.icons.rounded.Wifi
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.CircularWavyProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExperimentalMaterial3ExpressiveApi
import androidx.compose.material3.FilledTonalIconButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.IconButtonDefaults
import androidx.compose.material3.LargeFlexibleTopAppBar
import androidx.compose.material3.ListItemDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SegmentedListItem
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
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
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.input.nestedscroll.nestedScroll
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import ai.bayan.android.AppContainer
import ai.bayan.android.R
import ai.bayan.android.data.Settings
import ai.bayan.android.model.ModelCatalog
import ai.bayan.android.model.ModelInfo
import ai.bayan.android.model.ModelState
import ai.bayan.android.ui.appViewModel
import ai.bayan.android.ui.components.SectionHeader
import kotlin.math.roundToInt
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

class ModelsViewModel(private val app: AppContainer) : ViewModel() {
    val states = app.modelStore.states.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyMap())
    val settings = app.settings.settings.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), Settings())

    fun download(id: String) = viewModelScope.launch {
        // A model the user downloads is the one they want to use.
        if (states.value[settings.value.activeModel] !is ModelState.Installed) app.settings.setActiveModel(id)
        app.modelStore.download(id, settings.value.wifiOnly)
        // The default read-aloud voice is small (9 MB), so it comes along with the first model.
        val voice = ai.bayan.android.speech.VoiceCatalog.DEFAULT_ID
        if (states.value[voice] == null || states.value[voice] is ModelState.NotInstalled) app.modelStore.download(voice, settings.value.wifiOnly)
    }
    fun cancel(id: String) = app.modelStore.cancelDownload(id)
    fun activate(id: String) = viewModelScope.launch { app.settings.setActiveModel(id) }
    fun delete(id: String) = viewModelScope.launch { app.simplifier.releaseIfIdle(); app.modelStore.delete(id) }
    fun setWifiOnly(v: Boolean) = viewModelScope.launch { app.settings.setWifiOnly(v) }

    /** Installs a model from a .zip and makes it the active one; returns an error message or null. */
    suspend fun import(uri: Uri): String? = runCatching {
        val id = app.modelStore.importZip(uri)
        app.settings.setActiveModel(id)
    }.exceptionOrNull()?.let { it.message ?: it.javaClass.simpleName }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalMaterial3ExpressiveApi::class)
@Composable
fun ModelsScreen(onBack: () -> Unit, vm: ModelsViewModel = appViewModel { ModelsViewModel(it) }) {
    val settings by vm.settings.collectAsStateWithLifecycle()
    val appBar = TopAppBarDefaults.exitUntilCollapsedScrollBehavior(rememberTopAppBarState())
    val snackbar = remember { SnackbarHostState() }
    val scope = rememberCoroutineScope()
    val imported = stringResource(R.string.models_imported)
    val importFailed = stringResource(R.string.models_import_failed)
    val pickZip = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) scope.launch {
            val error = vm.import(uri)
            snackbar.showSnackbar(if (error == null) imported else "$importFailed $error")
        }
    }

    Scaffold(
        modifier = Modifier.nestedScroll(appBar.nestedScrollConnection),
        topBar = {
            LargeFlexibleTopAppBar(
                title = { Text(stringResource(R.string.models_title)) },
                navigationIcon = {
                    IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Rounded.ArrowBack, stringResource(R.string.action_back)) }
                },
                scrollBehavior = appBar,
            )
        },
        snackbarHost = { SnackbarHost(snackbar) },
    ) { padding ->
        Box(Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.TopCenter) {
            Column(
                Modifier.widthIn(max = 720.dp).fillMaxWidth().verticalScroll(rememberScrollState()).padding(start = 16.dp, end = 16.dp, bottom = 24.dp),
                verticalArrangement = Arrangement.spacedBy(ListItemDefaults.SegmentedGap),
            ) {
                ModelList(vm)
                SectionHeader(stringResource(R.string.models_download_options))
                SegmentedListItem(
                    checked = settings.wifiOnly,
                    onCheckedChange = vm::setWifiOnly,
                    shapes = ListItemDefaults.segmentedShapes(0, 2),
                    leadingContent = { Icon(Icons.Rounded.Wifi, null) },
                    supportingContent = { Text(stringResource(R.string.models_wifi_only_body)) },
                    trailingContent = { Switch(checked = settings.wifiOnly, onCheckedChange = null) },
                ) { Text(stringResource(R.string.models_wifi_only)) }
                SegmentedListItem(
                    onClick = { pickZip.launch(arrayOf("application/zip", "application/octet-stream")) },
                    shapes = ListItemDefaults.segmentedShapes(1, 2),
                    leadingContent = { Icon(Icons.Rounded.FileOpen, null) },
                    supportingContent = { Text(stringResource(R.string.models_import_body)) },
                ) { Text(stringResource(R.string.models_import)) }
                Row(Modifier.padding(horizontal = 16.dp, vertical = 16.dp)) {
                    Icon(Icons.Rounded.Lock, null, Modifier.size(18.dp), tint = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text(
                        stringResource(R.string.models_privacy),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(start = 12.dp),
                    )
                }
            }
        }
    }
}

/** The models as a single-choice list: the radio button picks the one in use, the trailing action installs or removes. */
@OptIn(ExperimentalMaterial3ExpressiveApi::class)
@Composable
fun ModelList(vm: ModelsViewModel) {
    val states by vm.states.collectAsStateWithLifecycle()
    val settings by vm.settings.collectAsStateWithLifecycle()
    val haptics = LocalHapticFeedback.current
    Column(verticalArrangement = Arrangement.spacedBy(ListItemDefaults.SegmentedGap)) {
        SectionHeader(stringResource(R.string.models_section))
        ModelCatalog.models.forEachIndexed { i, model ->
            val state = states[model.id] ?: ModelState.NotInstalled
            val installed = state is ModelState.Installed
            val selected = settings.activeModel == model.id && installed
            SegmentedListItem(
                selected = selected,
                onClick = { if (installed) { haptics.performHapticFeedback(HapticFeedbackType.SegmentTick); vm.activate(model.id) } },
                shapes = ListItemDefaults.segmentedShapes(i, ModelCatalog.models.size),
                leadingContent = { RadioButton(selected = selected, onClick = null, enabled = installed) },
                overlineContent = { Text(model.architecture) },
                supportingContent = { ModelDetails(model, state) },
                trailingContent = { ModelAction(model, state, onDownload = { vm.download(model.id) }, onCancel = { vm.cancel(model.id) }, onDelete = { vm.delete(model.id) }) },
            ) { Text(stringResource(model.title)) }
        }
    }
}

@Composable
private fun ModelDetails(model: ModelInfo, state: ModelState) {
    val context = LocalContext.current
    val size = Formatter.formatShortFileSize(context, model.bytes)
    val speed = if (model.relativeSpeed >= 0.9) stringResource(R.string.models_speed_fast)
    else stringResource(R.string.models_speed_slower, (1 / model.relativeSpeed).roundToInt())
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(stringResource(model.summary))
        val status = when (state) {
            is ModelState.Downloading -> stringResource(R.string.models_downloading, Formatter.formatShortFileSize(context, state.downloadedBytes), size)
            ModelState.Queued -> stringResource(R.string.models_waiting)
            is ModelState.Failed -> stringResource(R.string.models_failed, state.reason ?: "")
            else -> stringResource(R.string.models_facts, size, speed, model.sari)
        }
        Text(
            status,
            style = MaterialTheme.typography.labelLarge,
            color = if (state is ModelState.Failed) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.primary,
        )
    }
}

@OptIn(ExperimentalMaterial3ExpressiveApi::class)
@Composable
private fun ModelAction(model: ModelInfo, state: ModelState, onDownload: () -> Unit, onCancel: () -> Unit, onDelete: () -> Unit) {
    val context = LocalContext.current
    var confirmDelete by rememberSaveable { mutableStateOf(false) }
    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { onDownload() }
    val download = {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) permission.launch(Manifest.permission.POST_NOTIFICATIONS) else onDownload()
    }
    when (state) {
        ModelState.NotInstalled -> FilledTonalIconButton(onClick = download, shapes = IconButtonDefaults.shapes()) {
            Icon(Icons.Rounded.Download, stringResource(R.string.models_download, Formatter.formatShortFileSize(context, model.bytes)))
        }
        is ModelState.Failed -> FilledTonalIconButton(onClick = download, shapes = IconButtonDefaults.shapes()) {
            Icon(Icons.Rounded.Refresh, stringResource(R.string.action_retry))
        }
        ModelState.Queued, is ModelState.Downloading -> Box(contentAlignment = Alignment.Center) {
            if (state is ModelState.Downloading && state.progress > 0f) CircularWavyProgressIndicator(progress = { state.progress }, Modifier.size(44.dp))
            else CircularWavyProgressIndicator(Modifier.size(44.dp))
            IconButton(onClick = onCancel) { Icon(Icons.Rounded.Close, stringResource(R.string.action_cancel), Modifier.size(18.dp)) }
        }
        ModelState.Installed -> IconButton(onClick = { confirmDelete = true }) {
            Icon(Icons.Rounded.DeleteOutline, stringResource(R.string.action_delete))
        }
    }
    if (confirmDelete) {
        AlertDialog(
            onDismissRequest = { confirmDelete = false },
            icon = { Icon(Icons.Rounded.DeleteOutline, null) },
            title = { Text(stringResource(R.string.models_delete_title, stringResource(model.title))) },
            text = { Text(stringResource(R.string.models_delete_body, Formatter.formatShortFileSize(context, model.bytes))) },
            confirmButton = { TextButton(onClick = { onDelete(); confirmDelete = false }) { Text(stringResource(R.string.action_delete)) } },
            dismissButton = { TextButton(onClick = { confirmDelete = false }) { Text(stringResource(R.string.action_cancel)) } },
        )
    }
}
