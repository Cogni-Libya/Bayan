package ai.bayan.android.ui.process

import android.graphics.Matrix
import android.graphics.SweepGradient
import android.os.Build
import android.view.RoundedCorner
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.BlendMode
import androidx.compose.ui.graphics.BlurEffect
import androidx.compose.ui.graphics.CompositingStrategy
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathMeasure
import androidx.compose.ui.graphics.ShaderBrush
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.TileMode
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.unit.dp
import androidx.core.graphics.ColorUtils

/**
 * The light's colours: a few neighbouring hues around the phone's Material You colour and a pale highlight that
 * travels with them. Restraint is what makes the system assistant's glow look expensive; a rainbow looks cheap.
 */
@Composable
fun glowColors(): List<Color> {
    val primary = MaterialTheme.colorScheme.primary
    return remember(primary) {
        val hsl = FloatArray(3)
        ColorUtils.colorToHSL(primary.toArgb(), hsl)
        fun tone(shift: Float, s: Float, l: Float) = Color(ColorUtils.HSLToColor(floatArrayOf((hsl[0] + shift + 360f) % 360f, s, l)))
        // One hue, pastel, with a pale highlight drifting through it: calm, like light rather than paint.
        listOf(
            tone(-14f, 0.5f, 0.74f),
            tone(0f, 0.55f, 0.78f),
            tone(0f, 0.3f, 0.93f),
            tone(12f, 0.45f, 0.8f),
            tone(-14f, 0.5f, 0.74f),
        )
    }
}

/** The screen's own corner radius (Android 12+), so the edge light follows the display's curve. */
@Composable
private fun screenCornerRadius(): Float {
    val view = LocalView.current
    val fallback = with(LocalDensity.current) { 36.dp.toPx() }
    if (Build.VERSION.SDK_INT < Build.VERSION_CODES.S) return fallback
    val corner = view.rootWindowInsets?.getRoundedCorner(RoundedCorner.POSITION_TOP_LEFT)
    return corner?.radius?.toFloat()?.takeIf { it > 0 } ?: fallback
}

private fun sweepBrush(colors: List<Color>, center: Offset, angle: Float): ShaderBrush {
    val shader = SweepGradient(center.x, center.y, colors.map { it.toArgb() }.toIntArray(), null)
    shader.setLocalMatrix(Matrix().apply { postRotate(angle, center.x, center.y) })
    return ShaderBrush(shader)
}

/** The screen's outline as one path that starts and ends at the bottom centre, so it can be drawn growing up both sides. */
private fun edgePath(size: Size, radius: Float, inset: Float): Path = Path().apply {
    val l = inset; val t = inset; val r = size.width - inset; val b = size.height - inset
    val rr = (radius - inset).coerceAtLeast(0f)
    moveTo(size.width / 2, b)
    lineTo(r - rr, b)
    arcTo(Rect(r - 2 * rr, b - 2 * rr, r, b), 90f, -90f, false)
    lineTo(r, t + rr)
    arcTo(Rect(r - 2 * rr, t, r, t + 2 * rr), 0f, -90f, false)
    lineTo(l + rr, t)
    arcTo(Rect(l, t, l + 2 * rr, t + 2 * rr), 270f, -90f, false)
    lineTo(l, b - rr)
    arcTo(Rect(l, b - 2 * rr, l + 2 * rr, b), 180f, -90f, false)
    close()
}

/** Light is strongest at the bottom, where the panel is, and fades toward the top of the screen. */
private fun DrawScope.fadeTowardTop(top: Float = 0.25f) = drawRect(
    Brush.verticalGradient(0f to Color.Black.copy(alpha = top), 0.55f to Color.Black.copy(alpha = 0.6f), 1f to Color.Black),
    blendMode = BlendMode.DstIn,
)

/**
 * Iridescent tones for the light's leading edge and its travelling highlight: the phone's Material You hue and
 * its neighbours, saturated, with a pale highlight. Bright enough to read as light on any wallpaper or app.
 */
@Composable
private fun iridescentColors(): List<Color> {
    val primary = MaterialTheme.colorScheme.primary
    val tertiary = MaterialTheme.colorScheme.tertiary
    return remember(primary, tertiary) {
        val p = FloatArray(3).also { ColorUtils.colorToHSL(primary.toArgb(), it) }
        val t = FloatArray(3).also { ColorUtils.colorToHSL(tertiary.toArgb(), it) }
        fun tone(h: Float, s: Float, l: Float) = Color(ColorUtils.HSLToColor(floatArrayOf((h + 360f) % 360f, s, l)))
        listOf(
            tone(p[0] - 30f, 0.85f, 0.64f),
            tone(p[0], 0.9f, 0.66f),
            Color(0xFFFFF8F0),
            tone(t[0], 0.85f, 0.64f),
            tone(p[0] + 40f, 0.85f, 0.62f),
            tone(p[0] - 30f, 0.85f, 0.64f),
        )
    }
}

/** The part of the closed outline between [from] and [to] (in path lengths), wrapping past the start. */
private fun segment(measure: PathMeasure, length: Float, from: Float, to: Float): Path {
    val out = Path()
    val a = ((from % length) + length) % length
    val b = a + (to - from)
    if (b <= length) {
        measure.getSegment(a, b, out, true)
    } else {
        measure.getSegment(a, length, out, true)
        val rest = Path(); measure.getSegment(0f, b - length, rest, true); out.addPath(rest)
    }
    return out
}

private fun smoothstep(e0: Float, e1: Float, x: Float): Float {
    val t = ((x - e0) / (e1 - e0)).coerceIn(0f, 1f)
    return t * t * (3 - 2 * t)
}

/**
 * The light of the overlay, after the system assistant's:
 * - on opening ([reveal] 0 → 1), two lights rise from the bottom centre up both edges of the screen and meet at the
 *   top; each has an iridescent head and leaves a soft glow along the edge behind it;
 * - while Bayan works ([working]), the edge glow breathes, a highlight travels round the screen, and a warm haze
 *   lies behind the panel ([aurora]); [edge] scales the whole frame (the activity dims it to a calm glow once the
 *   text is ready);
 * - [border]: the same light, finer, round the panel at [panel].
 * Each part is drawn as a stack of the same shape at growing width and blur: crisp line, inner glow, outer halo.
 * With animations off (Settings ▸ Accessibility ▸ Remove animations) the light is still, and fully revealed.
 */
@Composable
fun OverlayGlow(reveal: Float, edge: Float, aurora: Float, border: Float, panel: Rect?, working: Boolean, modifier: Modifier = Modifier) {
    val soft = glowColors()
    val bright = iridescentColors()
    val context = LocalView.current.context
    val still = remember {
        android.provider.Settings.Global.getFloat(context.contentResolver, android.provider.Settings.Global.ANIMATOR_DURATION_SCALE, 1f) == 0f
    }
    val transition = rememberInfiniteTransition(label = "glow")
    val travel by transition.animateFloat(0f, 1f, infiniteRepeatable(tween(3600, easing = LinearEasing)), label = "travel")
    val angle by transition.animateFloat(0f, 360f, infiniteRepeatable(tween(9000, easing = LinearEasing)), label = "angle")
    val breathe by transition.animateFloat(0.78f, 1f, infiniteRepeatable(tween(2400), RepeatMode.Reverse), label = "breathe")
    val radius = screenCornerRadius()
    val density = LocalDensity.current
    val panelRadius = with(density) { 32.dp.toPx() }
    val blurs = Build.VERSION.SDK_INT >= Build.VERSION_CODES.S
    val shown = if (still) 1f else reveal
    val pulse = if (working && !still) breathe else 1f
    val shimmer = if (working && !still) 1f else 0f
    val comet = if (still) 0f else 1f - smoothstep(0.82f, 1f, reveal)

    @Composable
    fun Layer(blur: Float, lineWidth: Float, panelWidth: Float, edgeAlpha: Float, headAlpha: Float, panelAlpha: Float, horizon: Boolean = false) {
        val blurPx = with(density) { blur.dp.toPx() }
        Canvas(
            Modifier
                .fillMaxSize()
                .graphicsLayer {
                    compositingStrategy = CompositingStrategy.Offscreen
                    if (blurs && blur > 0f) renderEffect = BlurEffect(blurPx, blurPx, TileMode.Decal)
                },
        ) {
            val width = with(density) { lineWidth.dp.toPx() }
            if (horizon && aurora > 0f) {
                val drift = 0.16f * kotlin.math.sin(Math.toRadians(angle.toDouble())).toFloat()
                drawRect(
                    Brush.radialGradient(
                        listOf(bright[1].copy(alpha = 0.42f), bright[3].copy(alpha = 0.2f), soft[1].copy(alpha = 0.08f), Color.Transparent),
                        center = Offset(size.width * (0.5f + drift), size.height * 1.04f),
                        radius = size.width * 1.05f,
                    ),
                    alpha = (aurora * pulse).coerceAtMost(1f),
                )
            }
            if (edge > 0f && width > 0f && shown > 0f) {
                val path = edgePath(size, radius, width / 2)
                val measure = PathMeasure().apply { setPath(path, false) }
                val length = measure.length
                val half = length / 2
                val stroke = Stroke(width = width, cap = StrokeCap.Round)
                val frame = Brush.verticalGradient(listOf(soft[1].copy(alpha = 0.55f), soft[3], bright[1]))
                // The glow left behind the rising lights, then the whole frame.
                if (shown >= 1f) drawPath(path, frame, alpha = (edge * edgeAlpha * pulse).coerceAtMost(1f), style = stroke)
                else {
                    val h = half * shown
                    drawPath(segment(measure, length, 0f, h), frame, alpha = edge * edgeAlpha, style = stroke)
                    drawPath(segment(measure, length, length - h, length), frame, alpha = edge * edgeAlpha, style = stroke)
                }
                val iridescent = sweepBrush(bright, center, angle)
                // The two rising heads.
                if (comet > 0f && headAlpha > 0f) {
                    val h = half * shown
                    val head = length * 0.14f
                    drawPath(segment(measure, length, h - head, h), iridescent, alpha = (comet * headAlpha).coerceAtMost(1f), style = stroke)
                    drawPath(segment(measure, length, length - h, length - h + head), iridescent, alpha = (comet * headAlpha).coerceAtMost(1f), style = stroke)
                }
                // A highlight travelling round the screen while Bayan works.
                if (shimmer > 0f && shown >= 1f && headAlpha > 0f) {
                    val at = length * travel
                    drawPath(segment(measure, length, at, at + length * 0.18f), iridescent, alpha = (edge * shimmer * headAlpha * 0.75f).coerceAtMost(1f), style = stroke)
                    drawPath(segment(measure, length, at + half, at + half + length * 0.18f), iridescent, alpha = (edge * shimmer * headAlpha * 0.75f).coerceAtMost(1f), style = stroke)
                }
            }
            if (border > 0f && panel != null && panelWidth > 0f) {
                drawRoundRect(
                    sweepBrush(bright, panel.center, -angle),
                    topLeft = panel.topLeft,
                    size = panel.size,
                    cornerRadius = CornerRadius(panelRadius),
                    alpha = (border * panelAlpha * pulse).coerceAtMost(1f),
                    style = Stroke(width = with(density) { panelWidth.dp.toPx() }),
                )
            }
            fadeTowardTop(top = 0.5f)
        }
    }

    Box(modifier.fillMaxSize()) {
        if (blurs) {
            Layer(blur = 48f, lineWidth = 40f, panelWidth = 18f, edgeAlpha = 0.5f, headAlpha = 0.7f, panelAlpha = 0.3f, horizon = true)
            Layer(blur = 14f, lineWidth = 12f, panelWidth = 5f, edgeAlpha = 0.6f, headAlpha = 0.9f, panelAlpha = 0.45f)
        } else {
            Layer(blur = 0f, lineWidth = 16f, panelWidth = 8f, edgeAlpha = 0.22f, headAlpha = 0.35f, panelAlpha = 0.2f, horizon = true)
            Layer(blur = 0f, lineWidth = 6f, panelWidth = 4f, edgeAlpha = 0.4f, headAlpha = 0.6f, panelAlpha = 0.35f)
        }
        Layer(blur = 0f, lineWidth = 2f, panelWidth = 1.2f, edgeAlpha = 0.8f, headAlpha = 1f, panelAlpha = 0.7f)
    }
}

/** Placeholder lines with light sweeping across them while the first sentence is on its way. */
@Composable
fun ThinkingLines(modifier: Modifier = Modifier, lines: Int = 3) {
    val transition = rememberInfiniteTransition(label = "thinking")
    val shift by transition.animateFloat(-1f, 2f, infiniteRepeatable(tween(1300, easing = LinearEasing)), label = "shift")
    val colors = glowColors()
    val base = MaterialTheme.colorScheme.surfaceContainerHighest
    Column(modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        repeat(lines) { i ->
            val fraction = if (i == lines - 1) 0.6f else 1f
            Box(
                Modifier
                    .fillMaxWidth(fraction)
                    .height(18.dp)
                    .clip(RoundedCornerShape(9.dp))
                    .drawBehind {
                        // In RTL the light moves from right to left, the direction of reading.
                        val w = size.width
                        val x = w * (1f - shift)
                        drawRect(base)
                        drawRect(
                            Brush.linearGradient(
                                listOf(Color.Transparent, colors[1].copy(alpha = 0.35f), colors[2].copy(alpha = 0.45f), Color.Transparent),
                                Offset(x - w * 0.6f, 0f), Offset(x + w * 0.6f, 0f),
                            ),
                        )
                    },
            )
        }
    }
}
