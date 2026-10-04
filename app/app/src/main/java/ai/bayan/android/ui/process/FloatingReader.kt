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
import androidx.compose.ui.draw.drawBehind
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
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.graphics.ShaderBrush
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.spring
import androidx.compose.foundation.layout.wrapContentWidth
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.ui.text.TextLayoutResult
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
            // It takes over from the panel's pill, which already has its edge of light; only the shadow (which the
            // panel's pill has not) grows in.
            var up by remember { mutableStateOf(false) }
            LaunchedEffect(Unit) { up = true }
            val elevation by animateDpAsState(if (up) 6.dp else 0.dp, tween(300), label = "elevation")
            val flash = remember { androidx.compose.animation.core.Animatable(0f) }
            LaunchedEffect(Unit) { flash.animateTo(1f, tween(950, easing = androidx.compose.animation.core.FastOutSlowInEasing)) }
            Box(Modifier.padding(start = 16.dp, end = 16.dp, top = 16.dp, bottom = 12.dp)) {
                ReadingPill(
                    onExpand, onClose,
                    Modifier
                        .width(minOf(screen - 24.dp, 640.dp) * PILL_FRACTION)
                        .height(PILL_HEIGHT)
                        .pointerInput(Unit) { detectVerticalDragGestures { change, dy -> change.consume(); move(dy) } },
                    elevation = elevation,
                    chrome = { 1f },
                    flash = { flash.value },
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
fun ReadingPill(onExpand: () -> Unit, onClose: () -> Unit, modifier: Modifier = Modifier, contentAlpha: () -> Float = { 1f }, elevation: Dp = 6.dp, chrome: () -> Float = { 1f }, edgeLight: () -> Float = chrome, flash: () -> Float = { 1f }) {
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
    val surface = MaterialTheme.colorScheme.surfaceContainerLow
    val spark = androidx.compose.ui.graphics.lerp(colours[0], Color.White, 0.45f)

    // The light round the edge: a slow turn while reading, a faint still line otherwise.
    val turn by rememberInfiniteTransition(label = "pill").animateFloat(0f, 1f, infiniteRepeatable(tween(7000, easing = LinearEasing), RepeatMode.Restart), label = "turn")
    val glow by animateFloatAsState(if (reading) 0.85f else 0.3f, tween(600), label = "glow")

    // Pressed, the pill squeezes a little under the finger (and springs back), instead of a ripple.
    val press = remember { MutableInteractionSource() }
    val pressed by press.collectIsPressedAsState()
    val squeeze by animateFloatAsState(if (pressed) 0.94f else 1f, spring(dampingRatio = 0.5f, stiffness = Spring.StiffnessMedium), label = "squeeze")
    Row(
        modifier
            .graphicsLayer { scaleX = squeeze; scaleY = squeeze }
            .then(if (elevation > 0.dp) Modifier.shadow(elevation, CircleShape) else Modifier)
            .clip(CircleShape)
            .drawBehind { drawRect(surface, alpha = chrome()) }
            .drawWithContent {
                drawContent()
                val stroke = 1.5.dp.toPx()
                val brush = sweepBrush(colours + colours.first(), Offset(size.width / 2f, size.height / 2f), if (reading) turn * 360f else 0f)
                drawRoundRect(
                    brush, topLeft = Offset(stroke / 2f, stroke / 2f),
                    size = size.copy(width = size.width - stroke, height = size.height - stroke),
                    cornerRadius = CornerRadius(size.height / 2f), alpha = glow * edgeLight(), style = Stroke(stroke),
                )
                // Landing: one bright arc of the theme's light runs round the edge, sealing the pill, then is gone.
                val f = flash()
                if (f < 1f) {
                    val c = Offset(size.width / 2f, size.height / 2f)
                    val sweep = android.graphics.SweepGradient(
                        c.x, c.y,
                        intArrayOf(android.graphics.Color.TRANSPARENT, spark.toArgb(), android.graphics.Color.TRANSPARENT, android.graphics.Color.TRANSPARENT),
                        floatArrayOf(0f, 0.07f, 0.16f, 1f),
                    ).apply { setLocalMatrix(android.graphics.Matrix().apply { postRotate(-90f + 400f * f, c.x, c.y) }) }
                    val wide = 2.5.dp.toPx()
                    drawRoundRect(
                        ShaderBrush(sweep), topLeft = Offset(wide / 2f, wide / 2f),
                        size = size.copy(width = size.width - wide, height = size.height - wide),
                        cornerRadius = CornerRadius(size.height / 2f), alpha = kotlin.math.sin(Math.PI * f).toFloat(), style = Stroke(wide),
                    )
                }
            },
        verticalAlignment = Alignment.CenterVertically,
    ) {
        CompositionLocalProvider(LocalContentColor provides MaterialTheme.colorScheme.onSurface) {
            val settle = Modifier.graphicsLayer { val a = contentAlpha(); alpha = a; scaleX = 0.92f + 0.08f * a; scaleY = scaleX }
            ListenIconToggle(readable, key, settings.speechRate, complete, settle.padding(start = 7.dp))
            ReadingLine(shown, spoken, accent, onExpand, contentAlpha, press, Modifier.weight(1f).fillMaxHeight())
            IconButton(onClick = onClose, modifier = settle.padding(end = 4.dp)) {
                Icon(Icons.Rounded.Close, stringResource(R.string.action_close))
            }
        }
    }
}

/**
 * The pill's line, as a teleprompter: the whole text on one line that glides (a soft spring) so the word being spoken
 * stays in view, lit; before reading starts, its opening words. Arabic runs right to left, so the text starts at the
 * right edge and moves right as reading goes on; both edges fade into the pill.
 */
@Composable
private fun ReadingLine(text: String, spoken: IntRange?, accent: Color, onExpand: () -> Unit, contentAlpha: () -> Float, press: MutableInteractionSource, modifier: Modifier) {
    val line = remember(text) { text.replace('\n', ' ').trim() }
    var layout by remember { mutableStateOf<TextLayoutResult?>(null) }
    var boxWidth by remember { mutableFloatStateOf(0f) }
    // How far the strip has moved right, so the spoken word sits about two fifths in from the right edge.
    // Between two spoken words (or with reading paused) it holds its place; a new text starts from the beginning.
    var held by remember(line) { mutableFloatStateOf(0f) }
    val target = run {
        val l = layout ?: return@run held
        val r = spoken?.takeIf { it.first < line.length } ?: return@run held
        val wordRight = l.getHorizontalPosition(r.first, usePrimaryDirection = true)       // in the text's own coordinates
        val textLeftInBox = boxWidth - l.size.width                                          // the text is right-aligned
        (boxWidth * 0.6f - (textLeftInBox + wordRight)).coerceIn(0f, (l.size.width - boxWidth * 0.6f).coerceAtLeast(0f))
            .also { held = it }
    }
    // Its first place is taken at once (so a pill taking over from another shows the same words); later moves glide.
    val shift = remember { androidx.compose.animation.core.Animatable(0f) }
    var placed by remember { mutableStateOf(false) }
    LaunchedEffect(target, layout != null, boxWidth > 0f) {
        if (layout == null || boxWidth <= 0f) return@LaunchedEffect
        if (!placed) { shift.snapTo(target); placed = true }
        else shift.animateTo(target, spring(dampingRatio = 1f, stiffness = Spring.StiffnessLow))
    }
    val density = LocalDensity.current
    Box(
        modifier
            .clickable(interactionSource = press, indication = null, onClick = onExpand)
            .padding(horizontal = 10.dp)
            .onSizeChanged { boxWidth = it.width.toFloat() }
            .clipToBounds()
            .graphicsLayer { alpha = contentAlpha(); compositingStrategy = CompositingStrategy.Offscreen }
            .drawWithContent {
                drawContent()
                val fade = with(density) { 28.dp.toPx() }
                // the strip runs on past the left edge (where it continues) and, once it has moved, past the right
                drawRect(Brush.horizontalGradient(0f to Color.Transparent, 1f to Color.Black, startX = 0f, endX = fade), size = size.copy(width = fade), blendMode = BlendMode.DstIn)
                val right = (shift.value / fade).coerceIn(0f, 1f)
                if (right > 0f) drawRect(
                    Brush.horizontalGradient(0f to Color.Black, 1f to Color.Black.copy(alpha = 1f - right), startX = size.width - fade, endX = size.width),
                    topLeft = Offset(size.width - fade, 0f), size = size.copy(width = fade), blendMode = BlendMode.DstIn,
                )
            },
        contentAlignment = Alignment.CenterEnd,
    ) {
        if (line.isEmpty()) ThinkingLines(Modifier.padding(vertical = 4.dp), lines = 1)
        CompositionLocalProvider(LocalLayoutDirection provides LayoutDirection.Rtl) {
            Text(
                buildAnnotatedString {
                    append(line)
                    if (spoken != null && spoken.last < line.length) addStyle(SpanStyle(color = accent), spoken.first, spoken.last + 1)
                },
                maxLines = 1,
                softWrap = false,
                style = MaterialTheme.typography.bodyLarge,
                onTextLayout = { layout = it },
                modifier = Modifier
                    .wrapContentWidth(Alignment.Start, unbounded = true)
                    .graphicsLayer { translationX = shift.value },
            )
        }
    }
}

/** The pill's share of the panel's width, and its height: the panel folds into exactly this pill. */
const val PILL_FRACTION = 0.78f
val PILL_HEIGHT = 58.dp

