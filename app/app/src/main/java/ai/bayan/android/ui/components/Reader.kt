package ai.bayan.android.ui.components

import android.content.ClipData
import android.content.Context
import android.content.Intent
import android.os.Build
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.animateContentSize
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.tween
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.gestures.awaitEachGesture
import androidx.compose.foundation.gestures.awaitFirstDown
import androidx.compose.foundation.relocation.BringIntoViewRequester
import androidx.compose.foundation.relocation.bringIntoViewRequester
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.VolumeUp
import androidx.compose.material.icons.rounded.Check
import androidx.compose.material.icons.rounded.ContentCopy
import androidx.compose.material.icons.rounded.RecordVoiceOver
import androidx.compose.material.icons.rounded.Share
import androidx.compose.material.icons.rounded.Stop
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.ButtonGroupDefaults
import androidx.compose.material3.ExperimentalMaterial3ExpressiveApi
import androidx.compose.material3.FilledIconToggleButton
import androidx.compose.material3.FilledTonalIconButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.ToggleButton
import androidx.compose.material3.ToggleButtonDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.input.pointer.PointerEventPass
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.ClipEntry
import androidx.compose.ui.platform.LocalClipboard
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import ai.bayan.android.AppContainer
import ai.bayan.android.R
import ai.bayan.android.data.ReaderStyle
import ai.bayan.android.speech.SpeechState
import ai.bayan.android.ui.theme.colors
import ai.bayan.android.ui.theme.textStyle
import kotlinx.coroutines.launch

val LocalAppContainer = staticCompositionLocalOf<AppContainer> { error("No AppContainer provided") }

/**
 * Simplified text on the reader's chosen surface, in their font, size and spacing.
 * [highlight] marks the word being read aloud.
 */
@Composable
fun ReaderText(
    text: String,
    style: ReaderStyle,
    modifier: Modifier = Modifier,
    highlight: IntRange? = null,
    placeholder: String? = null,
    reveal: Boolean = false,
    /** Keep the highlighted word, or while streaming the newest text, in view inside a scrolling parent. */
    follow: Boolean = false,
) {
    val colors = style.surface.colors()
    val requester = remember { BringIntoViewRequester() }
    var layout by remember { mutableStateOf<TextLayoutResult?>(null) }
    val density = LocalDensity.current
    // Touching the text hands scrolling to the reader; following resumes a few seconds later, on the next word.
    var touchedAt by remember { mutableStateOf(0L) }
    LaunchedEffect(follow, highlight?.first, if (highlight == null) text.length else -1, layout) {
        val l = layout ?: return@LaunchedEffect
        if (!follow || text.isEmpty()) return@LaunchedEffect
        if (System.currentTimeMillis() - touchedAt < FOLLOW_PAUSE_MS) return@LaunchedEffect
        val at = (highlight?.first ?: (text.length - 1)).coerceIn(0, l.layoutInput.text.length - 1)
        val line = l.getLineForOffset(at)
        val margin = with(density) { 48.dp.toPx() }
        requester.bringIntoView(Rect(0f, l.getLineTop(line) - margin, l.size.width.toFloat(), l.getLineBottom(line) + margin))
    }
    val background by animateColorAsState(colors.background, MaterialTheme.motionScheme.defaultEffectsSpec(), label = "reader")
    val frontier = rememberRevealFrontier(text, reveal)
    val annotated = remember(text, highlight, colors, frontier) { buildReaderText(text, colors.text, colors.highlight, highlight, frontier) }
    Surface(
        color = background,
        shape = MaterialTheme.shapes.extraLarge,
        modifier = modifier.fillMaxWidth().pointerInput(Unit) {
            awaitEachGesture {
                awaitFirstDown(requireUnconsumed = false, pass = PointerEventPass.Initial)
                touchedAt = System.currentTimeMillis()
            }
        },
    ) {
        SelectionContainer(Modifier.padding(horizontal = 24.dp, vertical = 20.dp).animateContentSize(MaterialTheme.motionScheme.defaultSpatialSpec())) {
            if (text.isEmpty() && placeholder != null) {
                Text(placeholder, style = style.textStyle(), color = colors.muted)
            } else {
                Text(
                    annotated,
                    style = style.textStyle(),
                    color = colors.text,
                    onTextLayout = { layout = it },
                    modifier = Modifier.bringIntoViewRequester(requester).semantics { liveRegion = LiveRegionMode.Polite },
                )
            }
        }
    }
}

private const val FOLLOW_PAUSE_MS = 5_000L

/** Characters this far behind the reveal frontier fade from clear to fully drawn. */
private const val REVEAL_BAND = 28f

/**
 * How far into [text] the reveal has reached. New text flows in word by word, like a streamed answer;
 * text that only grew keeps what is already shown. Without [reveal] everything is shown at once.
 */
@Composable
private fun rememberRevealFrontier(text: String, reveal: Boolean): Float {
    val frontier = remember { Animatable(if (reveal) 0f else Float.MAX_VALUE) }
    var shown by remember { mutableStateOf("") }
    LaunchedEffect(text, reveal) {
        if (!reveal) { frontier.snapTo(Float.MAX_VALUE); shown = text; return@LaunchedEffect }
        // A streamed text that was corrected mid-way resumes from the unchanged part; a different text starts over.
        if (frontier.value > text.length + REVEAL_BAND) frontier.snapTo(0f)
        else if (!text.startsWith(shown)) frontier.snapTo(minOf(frontier.value, text.commonPrefixWith(shown).length.toFloat()))
        shown = text
        val end = text.length + REVEAL_BAND
        val millis = ((end - frontier.value) * 12).toInt().coerceIn(300, 1800)
        frontier.animateTo(end, tween(millis, easing = LinearEasing))
    }
    return frontier.value
}

private fun buildReaderText(text: String, color: Color, highlightColor: Color, highlight: IntRange?, frontier: Float): AnnotatedString =
    buildAnnotatedString {
        append(text)
        if (highlight != null && !highlight.isEmpty() && highlight.last < text.length) {
            addStyle(SpanStyle(background = highlightColor), highlight.first, highlight.last + 1)
        }
        if (frontier >= text.length + REVEAL_BAND) return@buildAnnotatedString
        // Hidden text keeps its place (transparent), so the layout never jumps while it appears.
        val solid = (frontier - REVEAL_BAND).toInt().coerceIn(0, text.length)
        val visible = frontier.toInt().coerceIn(0, text.length)
        for (i in solid until visible) {
            addStyle(SpanStyle(color = color.copy(alpha = ((frontier - i) / REVEAL_BAND).coerceIn(0f, 1f))), i, i + 1)
        }
        if (visible < text.length) addStyle(SpanStyle(color = Color.Transparent), visible, text.length)
    }

/** Two connected toggle buttons that switch between the simplified text and the original. */
@OptIn(ExperimentalMaterial3ExpressiveApi::class)
@Composable
fun OriginalToggle(showOriginal: Boolean, onChange: (Boolean) -> Unit, modifier: Modifier = Modifier) {
    val haptics = LocalHapticFeedback.current
    Row(modifier, horizontalArrangement = Arrangement.spacedBy(ButtonGroupDefaults.ConnectedSpaceBetween)) {
        ToggleButton(
            checked = !showOriginal,
            onCheckedChange = { haptics.performHapticFeedback(HapticFeedbackType.SegmentTick); onChange(false) },
            shapes = ButtonGroupDefaults.connectedLeadingButtonShapes(),
            modifier = Modifier.weight(1f).semantics { role = Role.RadioButton },
        ) {
            if (!showOriginal) { Icon(Icons.Rounded.Check, null, Modifier.size(ToggleButtonDefaults.IconSize)); Spacer(Modifier.width(ToggleButtonDefaults.IconSpacing)) }
            Text(stringResource(R.string.result_simplified))
        }
        ToggleButton(
            checked = showOriginal,
            onCheckedChange = { haptics.performHapticFeedback(HapticFeedbackType.SegmentTick); onChange(true) },
            shapes = ButtonGroupDefaults.connectedTrailingButtonShapes(),
            modifier = Modifier.weight(1f).semantics { role = Role.RadioButton },
        ) {
            if (showOriginal) { Icon(Icons.Rounded.Check, null, Modifier.size(ToggleButtonDefaults.IconSize)); Spacer(Modifier.width(ToggleButtonDefaults.IconSpacing)) }
            Text(stringResource(R.string.result_original))
        }
    }
}

/**
 * Listen, copy and share. [speechKey] tells this text's highlight apart from others. While the text is still being
 * simplified ([complete] false), [text] is its finished sentences: listening starts on them and follows new ones as
 * they arrive; copy and share appear once the text is complete.
 */
@OptIn(ExperimentalMaterial3ExpressiveApi::class)
@Composable
fun ReaderActions(
    text: String,
    speechKey: String,
    speechRate: Float,
    modifier: Modifier = Modifier,
    onCopied: () -> Unit = {},
    complete: Boolean = true,
) {
    val app = LocalAppContainer.current
    val context = LocalContext.current
    val haptics = LocalHapticFeedback.current
    val speech by app.readAloud.state.collectAsStateWithLifecycle()
    val clipboard = LocalClipboard.current
    val scope = rememberCoroutineScope()
    LaunchedEffect(speechKey, text, complete) {
        if (app.readAloud.isSpeaking(speechKey)) app.readAloud.follow(speechKey, text, complete, speechRate)
    }
    Row(modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
        when (val s = speech) {
            SpeechState.MissingArabicVoice -> OutlinedButton(onClick = { context.startActivity(app.readAloud.installVoiceIntent()) }, shapes = ButtonDefaults.shapes()) {
                Icon(Icons.Rounded.RecordVoiceOver, null, Modifier.size(ButtonDefaults.IconSize))
                Spacer(Modifier.width(ButtonDefaults.IconSpacing))
                Text(stringResource(R.string.action_install_voice))
            }
            SpeechState.Unavailable -> Unit
            else -> {
                val speaking = s is SpeechState.Speaking && s.key == speechKey
                ToggleButton(
                    checked = speaking,
                    onCheckedChange = { on ->
                        haptics.performHapticFeedback(if (on) HapticFeedbackType.ToggleOn else HapticFeedbackType.ToggleOff)
                        if (on) { app.readAloud.stop(); app.readAloud.follow(speechKey, text, complete, speechRate) } else app.readAloud.stop()
                    },
                ) {
                    Icon(if (speaking) Icons.Rounded.Stop else Icons.AutoMirrored.Rounded.VolumeUp, null, Modifier.size(ToggleButtonDefaults.IconSize))
                    Spacer(Modifier.width(ToggleButtonDefaults.IconSpacing))
                    Text(stringResource(if (speaking) R.string.action_stop else R.string.action_listen))
                }
            }
        }
        Spacer(Modifier.weight(1f))
        if (!complete) return@Row
        FilledTonalIconButton(
            onClick = {
                scope.launch {
                    clipboard.setClipEntry(ClipEntry(ClipData.newPlainText(context.getString(R.string.app_name), text)))
                    haptics.performHapticFeedback(HapticFeedbackType.Confirm)
                    // Android 13+ confirms copies itself.
                    if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) onCopied()
                }
            },
            shapes = IconButtonDefaults.shapes(),
        ) { Icon(Icons.Rounded.ContentCopy, stringResource(R.string.action_copy)) }
        FilledTonalIconButton(onClick = { context.shareText(text) }, shapes = IconButtonDefaults.shapes()) {
            Icon(Icons.Rounded.Share, stringResource(R.string.action_share))
        }
    }
}

/** Keeps reading a text that is still growing, wherever its listen control happens to be shown. */
@Composable
fun FollowReading(key: String, text: String, complete: Boolean, rate: Float) {
    val app = LocalAppContainer.current
    LaunchedEffect(key, text, complete) {
        if (app.readAloud.isSpeaking(key)) app.readAloud.follow(key, text, complete, rate)
    }
}

/** Listen / stop as a single icon, for compact places such as the minimized panel. */
@OptIn(ExperimentalMaterial3ExpressiveApi::class)
@Composable
fun ListenIconToggle(text: String, key: String, rate: Float, complete: Boolean, modifier: Modifier = Modifier) {
    val app = LocalAppContainer.current
    val haptics = LocalHapticFeedback.current
    val speech by app.readAloud.state.collectAsStateWithLifecycle()
    val speaking = (speech as? SpeechState.Speaking)?.key == key
    FilledIconToggleButton(
        checked = speaking,
        onCheckedChange = { on ->
            haptics.performHapticFeedback(if (on) HapticFeedbackType.ToggleOn else HapticFeedbackType.ToggleOff)
            if (on) { app.readAloud.stop(); app.readAloud.follow(key, text, complete, rate) } else app.readAloud.stop()
        },
        enabled = text.isNotEmpty() && speech != SpeechState.Unavailable,
        shapes = IconButtonDefaults.toggleableShapes(),
        modifier = modifier,
    ) {
        Icon(
            if (speaking) Icons.Rounded.Stop else Icons.AutoMirrored.Rounded.VolumeUp,
            stringResource(if (speaking) R.string.action_stop else R.string.action_listen),
        )
    }
}

/** Starts reading a simplification as soon as its first sentence is ready, when the reader turned that on. */
@Composable
fun AutoRead(enabled: Boolean, key: String, text: String, rate: Float) {
    val app = LocalAppContainer.current
    LaunchedEffect(key, enabled, text.isNotEmpty()) {
        if (enabled && text.isNotEmpty() && !app.readAloud.isSpeaking(key)) app.readAloud.follow(key, text, false, rate)
    }
}

/** The word range being spoken in the text with [key], if any. */
@Composable
fun spokenRange(key: String): IntRange? {
    val app = LocalAppContainer.current
    val speech by app.readAloud.state.collectAsStateWithLifecycle()
    val s = speech as? SpeechState.Speaking ?: return null
    return if (s.key == key && s.end > s.start) s.start until s.end else null
}

fun Context.shareText(text: String) {
    val send = Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_TEXT, text)
    startActivity(Intent.createChooser(send, null))
}

/** A section title above a group of list items, as in the system Settings app. */
@Composable
fun SectionHeader(text: String, modifier: Modifier = Modifier) {
    Text(
        text,
        style = MaterialTheme.typography.titleSmall,
        color = MaterialTheme.colorScheme.primary,
        modifier = modifier.padding(start = 16.dp, end = 16.dp, top = 20.dp, bottom = 8.dp).semantics { heading() },
    )
}

/** Shown when the model kept the text as it was, so the reader knows nothing went wrong. */
@Composable
fun UnchangedNote(source: String, result: String) {
    if (source.trim() != result.trim()) return
    Text(
        stringResource(R.string.result_unchanged),
        style = MaterialTheme.typography.bodyMedium,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = Modifier.padding(horizontal = 8.dp),
    )
}
