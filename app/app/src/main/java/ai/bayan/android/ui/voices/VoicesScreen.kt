package ai.bayan.android.ui.voices

import android.Manifest
import android.content.Intent
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
import androidx.compose.material.icons.rounded.AutoStories
import androidx.compose.material.icons.rounded.Close
import androidx.compose.material.icons.rounded.DeleteOutline
import androidx.compose.material.icons.rounded.Download
import androidx.compose.material.icons.rounded.PlayArrow
import androidx.compose.material.icons.rounded.Refresh
import androidx.compose.material.icons.rounded.Settings
import androidx.compose.material.icons.rounded.Stop
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
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.material3.rememberTopAppBarState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
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
import ai.bayan.android.model.ModelState
import ai.bayan.android.speech.SpeechState
import ai.bayan.android.speech.VoiceCatalog
import ai.bayan.android.speech.VoiceEngine
import ai.bayan.android.speech.VoiceInfo
import ai.bayan.android.ui.appViewModel
import ai.bayan.android.ui.components.SectionHeader
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

class VoicesViewModel(private val app: AppContainer) : ViewModel() {
    val states = app.modelStore.states.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyMap())
    val settings = app.settings.settings.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), Settings())
    val speech = app.readAloud.state

    fun select(id: String) = viewModelScope.launch { app.settings.setVoice(id) }
    fun download(id: String) = viewModelScope.launch {
        app.settings.setVoice(id)
        app.modelStore.download(id, settings.value.wifiOnly)
    }
    fun cancel(id: String) = app.modelStore.cancelDownload(id)
    fun delete(id: String) = viewModelScope.launch {
        app.readAloud.stop()
        app.readAloud.releaseIfIdle()
        app.modelStore.delete(id)
    }
    fun autoRead(v: Boolean) = viewModelScope.launch { app.settings.setAutoRead(v) }
    fun preview(voice: VoiceInfo, sample: String) =
        if (app.readAloud.isSpeaking("preview:${voice.id}")) app.readAloud.stop()
        else app.readAloud.preview(voice, sample, settings.value.speechRate)
    override fun onCleared() = app.readAloud.stop()
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalMaterial3ExpressiveApi::class)
@Composable
fun VoicesScreen(onBack: () -> Unit, vm: VoicesViewModel = appViewModel { VoicesViewModel(it) }) {
    val settings by vm.settings.collectAsStateWithLifecycle()
    val states by vm.states.collectAsStateWithLifecycle()
    val speech by vm.speech.collectAsStateWithLifecycle()
    val context = LocalContext.current
    val haptics = LocalHapticFeedback.current
    val appBar = TopAppBarDefaults.exitUntilCollapsedScrollBehavior(rememberTopAppBarState())
    val sample = stringResource(R.string.voice_sample)
    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) {}

    Scaffold(
        modifier = Modifier.nestedScroll(appBar.nestedScrollConnection),
        topBar = {
            LargeFlexibleTopAppBar(
                title = { Text(stringResource(R.string.voices_title)) },
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Rounded.ArrowBack, stringResource(R.string.action_back)) } },
                scrollBehavior = appBar,
            )
        },
    ) { padding ->
        Box(Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.TopCenter) {
            Column(
                Modifier.widthIn(max = 720.dp).fillMaxWidth().verticalScroll(rememberScrollState()).padding(start = 16.dp, end = 16.dp, bottom = 24.dp),
                verticalArrangement = Arrangement.spacedBy(ListItemDefaults.SegmentedGap),
            ) {
                SectionHeader(stringResource(R.string.voices_section))
                VoiceCatalog.all.forEachIndexed { i, voice ->
                    val state = if (voice.engine == VoiceEngine.System) ModelState.Installed else states[voice.id] ?: ModelState.NotInstalled
                    val installed = state is ModelState.Installed
                    val selected = settings.voice == voice.id && installed
                    val previewing = (speech as? SpeechState.Speaking)?.key == "preview:${voice.id}"
                    SegmentedListItem(
                        selected = selected,
                        onClick = { if (installed) { haptics.performHapticFeedback(HapticFeedbackType.SegmentTick); vm.select(voice.id) } },
                        shapes = ListItemDefaults.segmentedShapes(i, VoiceCatalog.all.size),
                        leadingContent = { RadioButton(selected = selected, onClick = null, enabled = installed) },
                        overlineContent = if (voice.credit.isNotEmpty()) { { Text(voice.credit) } } else null,
                        supportingContent = {
                            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                Text(stringResource(voice.summary))
                                val status = when (state) {
                                    is ModelState.Downloading -> stringResource(
                                        R.string.models_downloading,
                                        Formatter.formatShortFileSize(context, state.downloadedBytes),
                                        Formatter.formatShortFileSize(context, voice.bytes),
                                    )
                                    ModelState.Queued -> stringResource(R.string.models_waiting)
                                    is ModelState.Failed -> stringResource(R.string.models_failed, state.reason ?: "")
                                    else -> if (voice.engine == VoiceEngine.System) null else Formatter.formatShortFileSize(context, voice.bytes)
                                }
                                if (status != null) {
                                    Text(
                                        status,
                                        style = MaterialTheme.typography.labelLarge,
                                        color = if (state is ModelState.Failed) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.primary,
                                    )
                                }
                            }
                        },
                        trailingContent = {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                when (state) {
                                    ModelState.Installed -> {
                                        FilledTonalIconButton(onClick = { vm.preview(voice, sample) }, shapes = IconButtonDefaults.shapes()) {
                                            Icon(if (previewing) Icons.Rounded.Stop else Icons.Rounded.PlayArrow, stringResource(R.string.voices_preview))
                                        }
                                        if (voice.engine == VoiceEngine.System) {
                                            IconButton(onClick = {
                                                runCatching { context.startActivity(Intent("com.android.settings.TTS_SETTINGS").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) }
                                            }) { Icon(Icons.Rounded.Settings, stringResource(R.string.settings_voice)) }
                                        } else {
                                            IconButton(onClick = { vm.delete(voice.id) }) { Icon(Icons.Rounded.DeleteOutline, stringResource(R.string.action_delete)) }
                                        }
                                    }
                                    ModelState.NotInstalled, is ModelState.Failed -> FilledTonalIconButton(
                                        onClick = {
                                            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) permission.launch(Manifest.permission.POST_NOTIFICATIONS)
                                            vm.download(voice.id)
                                        },
                                        shapes = IconButtonDefaults.shapes(),
                                    ) { Icon(if (state is ModelState.Failed) Icons.Rounded.Refresh else Icons.Rounded.Download, stringResource(R.string.voices_download)) }
                                    ModelState.Queued, is ModelState.Downloading -> Box(contentAlignment = Alignment.Center) {
                                        if (state is ModelState.Downloading && state.progress > 0f) CircularWavyProgressIndicator(progress = { state.progress }, Modifier.size(44.dp))
                                        else CircularWavyProgressIndicator(Modifier.size(44.dp))
                                        IconButton(onClick = { vm.cancel(voice.id) }) { Icon(Icons.Rounded.Close, stringResource(R.string.action_cancel), Modifier.size(18.dp)) }
                                    }
                                }
                            }
                        },
                    ) { Text(stringResource(voice.title)) }
                }

                SectionHeader(stringResource(R.string.voices_section_behaviour))
                SegmentedListItem(
                    checked = settings.autoRead,
                    onCheckedChange = vm::autoRead,
                    shapes = ListItemDefaults.segmentedShapes(0, 1),
                    leadingContent = { Icon(Icons.Rounded.AutoStories, null) },
                    supportingContent = { Text(stringResource(R.string.voices_auto_read_body)) },
                    trailingContent = { Switch(checked = settings.autoRead, onCheckedChange = null) },
                ) { Text(stringResource(R.string.voices_auto_read)) }
                Text(
                    stringResource(R.string.voices_note),
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(16.dp),
                )
            }
        }
    }
}
