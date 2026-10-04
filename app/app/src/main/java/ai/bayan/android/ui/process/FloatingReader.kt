package ai.bayan.android.ui.process

import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectVerticalDragGestures
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Close
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LocalContentColor
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawWithContent
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.runtime.setValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.animation.core.animateDpAsState
import androidx.compose.ui.unit.Dp
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.ui.graphics.BlendMode
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.CompositingStrategy
import androidx.compose.ui.graphics.graphicsLayer
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import ai.bayan.android.AppContainer
import ai.bayan.android.R
import ai.bayan.android.data.Settings
import ai.bayan.android.speech.SpeechState
import ai.bayan.android.ui.SimplifyState
import ai.bayan.android.ui.components.ListenIconToggle
import ai.bayan.android.ui.components.LocalAppContainer
import ai.bayan.android.ui.components.spokenRange
import ai.bayan.android.ui.theme.BayanTheme

/**
 * The minimized "تبسيط" panel, floating over the app the text came from: the very pill the panel folds into (same
 * size and place, and the same content, so the hand-over is invisible). See [ReadingPill].
 */
@Composable
fun FloatingReader(container: AppContainer, move: (Float) -> Unit, onExpand: () -> Unit, onClose: () -> Unit) {
    val settings by container.settings.settings.collectAsStateWithLifecycle(Settings())
    CompositionLocalProvider(LocalAppContainer provides container) {
        BayanTheme(settings.themeMode) {
            val screen = LocalConfiguration.current.screenWidthDp.dp
            // Its shadow grows in once it has taken over from the panel's pill (which has none).
            var up by remember { mutableStateOf(false) }
            LaunchedEffect(Unit) { up = true }
            val elevation by animateDpAsState(if (up) 14.dp else 0.dp, tween(500, delayMillis = 120), label = "elevation")
            Box(Modifier.padding(start = 16.dp, end = 16.dp, top = 16.dp, bottom = 12.dp)) {
                ReadingPill(
                    onExpand, onClose,
                    Modifier
                        .width(minOf(screen - 24.dp, 640.dp) * PILL_FRACTION)
                        .height(PILL_HEIGHT)
                        .pointerInput(Unit) { detectVerticalDragGestures { change, dy -> change.consume(); move(dy) } },
                    elevation = elevation,
                )
            }
        }
    }
}

/**
 * The reading pill: the line being read with the spoken word lit, listen / stop and close. A tap on the line unfolds
 * it into the full panel. While Bayan reads, a thread of the theme's light runs slowly round its edge. Drawn both by
 * the panel as it folds (and as it unfolds again) and by the floating window, so the two are indistinguishable.
 */
@Composable
fun ReadingPill(onExpand: () -> Unit, onClose: () -> Unit, modifier: Modifier = Modifier, contentAlpha: () -> Float = { 1f }, elevation: Dp = 14.dp) {
    val container = LocalAppContainer.current
    val settings by container.settings.settings.collectAsStateWithLifecycle(Settings())
    val state by container.overlay.simplify.state.collectAsStateWithLifecycle()
    val key = container.overlay.key(state)
    val (shown, readable, complete) = when (val st = state) {
        is SimplifyState.Running -> Triple(st.partial, st.partial.take(st.committed), false)
        is SimplifyState.Done -> Triple(st.result, st.result, true)
        else -> Triple("", "", false)
    }
    val speech by container.readAloud.state.collectAsStateWithLifecycle()
    val reading = (speech as? SpeechState.Speaking)?.key == key
    val spoken = spokenRange(key)
    val colours = edgeLightColours()
    val accent = MaterialTheme.colorScheme.primary

    // The light round the edge: a slow turn while reading, a faint still line otherwise.
    val turn by rememberInfiniteTransition(label = "pill").animateFloat(0f, 1f, infiniteRepeatable(tween(7000, easing = LinearEasing), RepeatMode.Restart), label = "turn")
    val glow by animateFloatAsState(if (reading) 0.85f else 0.3f, tween(600), label = "glow")

    Row(
        modifier
            .then(if (elevation > 0.dp) Modifier.shadow(elevation, CircleShape, ambientColor = accent, spotColor = accent) else Modifier)
            .clip(CircleShape)
            .background(MaterialTheme.colorScheme.surfaceContainerLow)
            .drawWithContent {
                drawContent()
                val stroke = 1.5.dp.toPx()
                val brush = sweepBrush(colours + colours.first(), Offset(size.width / 2f, size.height / 2f), if (reading) turn * 360f else 0f)
                drawRoundRect(
                    brush, topLeft = Offset(stroke / 2f, stroke / 2f),
                    size = size.copy(width = size.width - stroke, height = size.height - stroke),
                    cornerRadius = CornerRadius(size.height / 2f), alpha = glow * contentAlpha(), style = Stroke(stroke),
                )
            },
        verticalAlignment = Alignment.CenterVertically,
    ) {
        CompositionLocalProvider(LocalContentColor provides MaterialTheme.colorScheme.onSurface) {
            val settle = Modifier.graphicsLayer { val a = contentAlpha(); alpha = a; scaleX = 0.92f + 0.08f * a; scaleY = scaleX }
            ListenIconToggle(readable, key, settings.speechRate, complete, settle.padding(start = 7.dp))
            Box(
                Modifier
                    .weight(1f)
                    .fillMaxHeight()
                    .clickable(onClick = onExpand)
                    .padding(horizontal = 10.dp)
                    .graphicsLayer { alpha = contentAlpha(); compositingStrategy = CompositingStrategy.Offscreen }
                    .drawWithContent {
                        // the line runs on past the pill's edge (its end, on the left) and fades out there
                        drawContent()
                        val fade = 28.dp.toPx()
                        drawRect(
                            Brush.horizontalGradient(0f to Color.Transparent, 1f to Color.Black, startX = 0f, endX = fade),
                            size = size.copy(width = fade), blendMode = BlendMode.DstIn,
                        )
                    },
                contentAlignment = Alignment.CenterEnd,
            ) {
                val (line, lit) = readingWindow(shown, spoken)
                if (line.isEmpty()) ThinkingLines(Modifier.padding(vertical = 4.dp), lines = 1)
                // Arabic runs right to left: the line starts at the right and overflows to the left, where it fades.
                CompositionLocalProvider(LocalLayoutDirection provides LayoutDirection.Rtl) {
                    Text(
                        buildAnnotatedString {
                            append(line)
                            if (lit != null) addStyle(SpanStyle(color = accent), lit.first, lit.last + 1)
                        },
                        maxLines = 1,
                        softWrap = false,
                        overflow = TextOverflow.Clip,
                        textAlign = TextAlign.Start,
                        style = MaterialTheme.typography.bodyLarge,
                        modifier = Modifier.fillMaxWidth(),
                    )
                }
            }
            IconButton(onClick = onClose, modifier = settle.padding(end = 4.dp)) {
                Icon(Icons.Rounded.Close, stringResource(R.string.action_close))
            }
        }
    }
}

/** The pill's share of the panel's width, and its height: the panel folds into exactly this pill. */
const val PILL_FRACTION = 0.78f
val PILL_HEIGHT = 58.dp

/**
 * The part of [text] the pill shows: from a little before the spoken word (at a word boundary), so the word being read
 * is always in sight; before reading starts, the opening words. Returns the line and where the spoken word sits in it.
 */
private fun readingWindow(text: String, spoken: IntRange?): Pair<String, IntRange?> {
    val flat = text.replace('\n', ' ')
    if (spoken == null || spoken.first >= flat.length) return flat.trim() to null
    var start = (spoken.first - 24).coerceAtLeast(0)
    if (start > 0) start = flat.indexOf(' ', start).let { if (it in 0 until spoken.first) it + 1 else spoken.first }
    val line = flat.substring(start)
    val lit = (spoken.first - start) until (spoken.last + 1 - start).coerceAtMost(line.length)
    return line to lit
}
