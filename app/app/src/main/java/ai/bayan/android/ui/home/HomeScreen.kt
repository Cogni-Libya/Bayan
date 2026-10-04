package ai.bayan.android.ui.home

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.animateContentSize
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.scaleIn
import androidx.compose.animation.scaleOut
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.input.TextFieldLineLimits
import androidx.compose.foundation.text.input.setTextAndPlaceCursorAtEnd
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.AutoAwesome
import androidx.compose.material.icons.rounded.Close
import androidx.compose.material.icons.rounded.ContentPaste
import androidx.compose.material.icons.rounded.Download
import androidx.compose.material.icons.rounded.ErrorOutline
import androidx.compose.material.icons.rounded.Stop
import androidx.compose.material.icons.rounded.TouchApp
import androidx.compose.material3.AssistChip
import androidx.compose.material3.AssistChipDefaults
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExperimentalMaterial3ExpressiveApi
import androidx.compose.material3.ExtendedFloatingActionButton
import androidx.compose.material3.FloatingActionButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LargeFlexibleTopAppBar
import androidx.compose.material3.LinearWavyProgressIndicator
import androidx.compose.material3.LoadingIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedCard
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextField
import androidx.compose.material3.TextFieldDefaults
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.material3.rememberTopAppBarState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.input.nestedscroll.nestedScroll
import androidx.compose.ui.platform.LocalClipboard
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import ai.bayan.android.R
import ai.bayan.android.data.Settings
import ai.bayan.android.model.ModelCatalog
import ai.bayan.android.model.ModelState
import ai.bayan.android.ui.SimplifyState
import ai.bayan.android.ui.appViewModel
import ai.bayan.android.ui.components.AutoRead
import ai.bayan.android.ui.components.OriginalToggle
import ai.bayan.android.ui.components.ReaderActions
import ai.bayan.android.ui.components.ReaderText
import ai.bayan.android.ui.components.UnchangedNote
import ai.bayan.android.ui.components.isUnchanged
import ai.bayan.android.ui.components.spokenRange
import ai.bayan.android.ui.isBusy
import ai.bayan.android.ui.theme.ContentDirection
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class, ExperimentalMaterial3ExpressiveApi::class)
@Composable
fun HomeScreen(
    onOpenModels: () -> Unit,
    sharedText: String?,
    onSharedTextConsumed: () -> Unit,
    vm: HomeViewModel = appViewModel { HomeViewModel(it) },
) {
    val settings by vm.settings.collectAsStateWithLifecycle()
    val active by vm.activeModel.collectAsStateWithLifecycle()
    val state by vm.session.state.collectAsStateWithLifecycle()
    val snackbar = remember { SnackbarHostState() }
    val scope = rememberCoroutineScope()
    val copied = stringResource(R.string.copied)
    val focus = LocalFocusManager.current
    val haptics = LocalHapticFeedback.current
    val scroll = rememberScrollState()
    val appBar = TopAppBarDefaults.exitUntilCollapsedScrollBehavior(rememberTopAppBarState())
    val installed = active?.state is ModelState.Installed

    LaunchedEffect(sharedText) {
        if (sharedText != null) { vm.receive(sharedText); onSharedTextConsumed() }
    }
    LaunchedEffect(state::class) {
        when (state) {
            // Bring the result into view as soon as it starts arriving.
            is SimplifyState.LoadingModel, is SimplifyState.Running -> { focus.clearFocus(); scroll.animateScrollTo(scroll.maxValue) }
            is SimplifyState.Done -> haptics.performHapticFeedback(HapticFeedbackType.Confirm)
            is SimplifyState.Failed -> haptics.performHapticFeedback(HapticFeedbackType.Reject)
            else -> Unit
        }
    }

    Scaffold(
        modifier = Modifier.nestedScroll(appBar.nestedScrollConnection),
        topBar = {
            LargeFlexibleTopAppBar(
                title = { Text(stringResource(R.string.app_name)) },
                subtitle = active?.let { { Text(stringResource(it.info.title)) } },
                scrollBehavior = appBar,
            )
        },
        floatingActionButton = {
            // Only when there is something new to simplify, so it never sits on top of a result.
            val lastSource = (state as? SimplifyState.Done)?.source
            val showFab = state.isBusy || (installed && vm.input.text.isNotBlank() && vm.input.text.trim() != lastSource)
            AnimatedVisibility(
                visible = showFab,
                enter = scaleIn(MaterialTheme.motionScheme.fastSpatialSpec()) + fadeIn(),
                exit = scaleOut(MaterialTheme.motionScheme.fastSpatialSpec()) + fadeOut(),
                modifier = Modifier.imePadding(),
            ) {
                val busy = state.isBusy
                ExtendedFloatingActionButton(
                    onClick = { if (busy) vm.cancel() else vm.simplify() },
                    icon = { Icon(if (busy) Icons.Rounded.Stop else Icons.Rounded.AutoAwesome, null) },
                    text = { Text(stringResource(if (busy) R.string.action_stop_simplifying else R.string.action_simplify)) },
                    containerColor = if (busy) MaterialTheme.colorScheme.secondaryContainer else FloatingActionButtonDefaults.containerColor,
                )
            }
        },
        snackbarHost = { SnackbarHost(snackbar) },
    ) { padding ->
        Box(Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.TopCenter) {
            Column(
                Modifier
                    .widthIn(max = 720.dp)
                    .fillMaxWidth()
                    .imePadding()
                    .verticalScroll(scroll)
                    .padding(start = 16.dp, end = 16.dp, top = 8.dp, bottom = 112.dp),
                verticalArrangement = Arrangement.spacedBy(16.dp),
            ) {
                val needsModel = (active != null && !installed) || state is SimplifyState.NeedsModel
                if (needsModel) {
                    NoticeCard(
                        icon = Icons.Rounded.Download,
                        title = stringResource(R.string.home_needs_model_title),
                        body = stringResource(R.string.home_needs_model_body),
                        action = stringResource(R.string.home_needs_model_action),
                        onAction = onOpenModels,
                    )
                }

                InputArea(vm, enabled = !state.isBusy, compact = state is SimplifyState.Done || state is SimplifyState.Running)

                ResultArea(state, settings, onCopied = { scope.launch { snackbar.showSnackbar(copied) } })

                if (state is SimplifyState.Idle && vm.input.text.isEmpty()) {
                    OutlinedCard(shape = MaterialTheme.shapes.extraLarge) {
                        Row(Modifier.padding(20.dp), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                            Icon(Icons.Rounded.TouchApp, null, tint = MaterialTheme.colorScheme.primary)
                            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                Text(stringResource(R.string.home_tip_title), style = MaterialTheme.typography.titleMedium)
                                Text(
                                    stringResource(R.string.home_tip_body),
                                    style = MaterialTheme.typography.bodyMedium,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun InputArea(vm: HomeViewModel, enabled: Boolean, compact: Boolean) {
    val clipboard = LocalClipboard.current
    val scope = rememberCoroutineScope()
    val text = vm.input.text
    // With a result below it the input shrinks to a few lines; tapping it to edit opens it up again.
    var focused by remember { mutableStateOf(false) }
    val small = compact && !focused
    val container = MaterialTheme.colorScheme.surfaceContainerHigh
    Surface(color = container, shape = MaterialTheme.shapes.extraLarge) {
        Column {
            TextField(
                state = vm.input,
                enabled = enabled,
                modifier = Modifier
                    .fillMaxWidth()
                    .then(if (small) Modifier else Modifier.heightIn(min = 180.dp))
                    .onFocusChanged { focused = it.isFocused }
                    .animateContentSize(MaterialTheme.motionScheme.defaultSpatialSpec()),
                textStyle = MaterialTheme.typography.titleLarge.merge(ContentDirection),
                placeholder = { Text(stringResource(R.string.home_input_placeholder), style = MaterialTheme.typography.titleLarge) },
                lineLimits = if (small) TextFieldLineLimits.MultiLine(1, 3) else TextFieldLineLimits.MultiLine(4, 10),
                colors = TextFieldDefaults.colors(
                    focusedContainerColor = Color.Transparent,
                    unfocusedContainerColor = Color.Transparent,
                    disabledContainerColor = Color.Transparent,
                    focusedIndicatorColor = Color.Transparent,
                    unfocusedIndicatorColor = Color.Transparent,
                    disabledIndicatorColor = Color.Transparent,
                ),
            )
            Row(Modifier.fillMaxWidth().padding(start = 12.dp, end = 4.dp, bottom = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                if (text.isEmpty()) {
                    AssistChip(
                        enabled = enabled,
                        onClick = {
                            scope.launch {
                                val clip = clipboard.getClipEntry()?.clipData
                                val pasted = clip?.takeIf { it.itemCount > 0 }?.getItemAt(0)?.text?.toString()
                                if (!pasted.isNullOrBlank()) vm.input.setTextAndPlaceCursorAtEnd(pasted)
                            }
                        },
                        label = { Text(stringResource(R.string.action_paste)) },
                        leadingIcon = { Icon(Icons.Rounded.ContentPaste, null, Modifier.size(AssistChipDefaults.IconSize)) },
                    )
                } else {
                    val words = text.trim().split(Regex("\\s+")).count { it.isNotEmpty() }
                    Text(
                        pluralStringResource(R.plurals.word_count, words, words),
                        style = MaterialTheme.typography.labelLarge,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Spacer(Modifier.weight(1f))
                if (text.isNotEmpty()) {
                    IconButton(onClick = vm::clear, enabled = enabled) { Icon(Icons.Rounded.Close, stringResource(R.string.action_clear)) }
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3ExpressiveApi::class)
@Composable
private fun ResultArea(state: SimplifyState, settings: Settings, onCopied: () -> Unit) {
    when (state) {
        SimplifyState.Idle, is SimplifyState.NeedsModel -> Unit
        SimplifyState.LoadingModel -> Row(
            Modifier.fillMaxWidth().padding(vertical = 8.dp),
            horizontalArrangement = Arrangement.Center,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            LoadingIndicator()
            Spacer(Modifier.width(12.dp))
            Text(stringResource(R.string.home_loading_model), style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        is SimplifyState.Running -> Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            LinearWavyProgressIndicator(
                progress = { if (state.total == 0) 0f else (state.done + 0.5f) / state.total },
                modifier = Modifier.fillMaxWidth(),
            )
            Text(
                stringResource(R.string.home_progress, (state.done + 1).coerceAtMost(state.total), state.total),
                style = MaterialTheme.typography.labelLarge,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            val key = "home:${state.run}:s"
            val committed = state.partial.take(state.committed)
            ReaderText(
                state.partial,
                settings.reader,
                placeholder = stringResource(R.string.home_result_placeholder),
                reveal = true,
                highlight = if (settings.highlightWhileReading) spokenRange(key) else null,
            )
            AutoRead(settings.autoRead, key, committed, settings.speechRate)
            if (committed.isNotEmpty()) ReaderActions(committed, key, settings.speechRate, complete = false)
        }
        is SimplifyState.Done -> DoneResult(state, settings, onCopied)
        is SimplifyState.Failed -> NoticeCard(
            icon = Icons.Rounded.ErrorOutline,
            title = stringResource(R.string.home_failed_title),
            body = state.message ?: stringResource(R.string.home_failed_body),
            error = true,
        )
    }
}

@Composable
private fun DoneResult(state: SimplifyState.Done, settings: Settings, onCopied: () -> Unit) {
    var showOriginal by rememberSaveable(state.result) { mutableStateOf(false) }
    val key = "home:${state.run}:${if (showOriginal) "o" else "s"}"
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        if (!isUnchanged(state.source, state.result)) OriginalToggle(showOriginal, { showOriginal = it }, Modifier.fillMaxWidth())
        // Actions come first, as in Translate: visible without scrolling however long the text is.
        ReaderActions(if (showOriginal) state.source else state.result, key, settings.speechRate, onCopied = onCopied)
        AnimatedContent(showOriginal, transitionSpec = { fadeIn() togetherWith fadeOut() }, label = "result") { original ->
            ReaderText(
                if (original) state.source else state.result,
                settings.reader,
                highlight = if (settings.highlightWhileReading) spokenRange(key) else null,
                reveal = !original,
                follow = true,
            )
        }
        UnchangedNote(state.source, state.result)
        Text(
            stringResource(R.string.result_meta, stringResource(ModelCatalog.get(state.modelId).title), state.millis / 1000.0),
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(horizontal = 8.dp),
        )
    }
}

@Composable
fun NoticeCard(
    icon: ImageVector,
    title: String,
    body: String,
    modifier: Modifier = Modifier,
    action: String? = null,
    onAction: () -> Unit = {},
    error: Boolean = false,
) {
    val colors = if (error) {
        CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer, contentColor = MaterialTheme.colorScheme.onErrorContainer)
    } else {
        CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.secondaryContainer, contentColor = MaterialTheme.colorScheme.onSecondaryContainer)
    }
    Card(colors = colors, shape = MaterialTheme.shapes.extraLarge, modifier = modifier.fillMaxWidth()) {
        Row(Modifier.padding(20.dp), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
            Icon(icon, null)
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(title, style = MaterialTheme.typography.titleMedium)
                Text(body, style = MaterialTheme.typography.bodyMedium)
                if (action != null) {
                    Button(onClick = onAction, shapes = ButtonDefaults.shapes(), modifier = Modifier.padding(top = 12.dp)) { Text(action) }
                }
            }
        }
    }
}
