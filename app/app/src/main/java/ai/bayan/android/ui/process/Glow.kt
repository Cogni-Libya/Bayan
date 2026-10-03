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
 * The light of the overlay, after the system assistant's, which is elegant because it does little:
 * - one soft glow just inside the screen's edge, in a single tone of the phone's Material You colour, rising from the
 *   bottom centre up both sides as the overlay opens ([reveal] 0 → 1);
 * - a brief iridescent gleam along the bottom edge while it rises, gone by the time the light reaches the top;
 * - while Bayan works ([edge] 1) the glow holds and breathes slowly; once the text is ready the activity fades it out.
 * [aurora], [border] and [panel] are kept for the call site; the restrained light no longer uses them.
 * With animations off (Settings ▸ Accessibility ▸ Remove animations) the glow is still and fully shown.
 */
@Composable
fun OverlayGlow(reveal: Float, edge: Float, aurora: Float, border: Float, panel: Rect?, working: Boolean, modifier: Modifier = Modifier) {
    val bright = iridescentColors()
    val primary = MaterialTheme.colorScheme.primary
    // One warm, lightly saturated tone of the phone's colour: the system assistant's light is a tint, not a paint.
    val warm = remember(primary) {
        val hsl = FloatArray(3).also { ColorUtils.colorToHSL(primary.toArgb(), it) }
        Color(ColorUtils.HSLToColor(floatArrayOf(hsl[0], 0.62f, 0.72f)))
    }
    val context = LocalView.current.context
    val still = remember {
        android.provider.Settings.Global.getFloat(context.contentResolver, android.provider.Settings.Global.ANIMATOR_DURATION_SCALE, 1f) == 0f
    }
    val transition = rememberInfiniteTransition(label = "glow")
    val breathe by transition.animateFloat(0.85f, 1f, infiniteRepeatable(tween(3200), RepeatMode.Reverse), label = "breathe")
    val radius = screenCornerRadius()
    val density = LocalDensity.current
    val blurs = Build.VERSION.SDK_INT >= Build.VERSION_CODES.S
    val shown = if (still) 1f else reveal
    val pulse = if (working && !still) breathe else 1f
    val gleam = if (still) 0f else smoothstep(0f, 0.25f, reveal) * (1f - smoothstep(0.45f, 0.85f, reveal))
    if (edge <= 0f || shown <= 0f) return

    @Composable
    fun Layer(blur: Float, lineWidth: Float, alpha: Float) {
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
            val path = edgePath(size, radius, width * 0.2f)
            val measure = PathMeasure().apply { setPath(path, false) }
            val length = measure.length
            val stroke = Stroke(width = width, cap = StrokeCap.Round)
            val tone = Brush.verticalGradient(listOf(warm.copy(alpha = 0.6f), warm, warm))
            val a = (edge * alpha * pulse).coerceAtMost(1f)
            if (shown >= 1f) drawPath(path, tone, alpha = a, style = stroke)
            else {
                val h = length / 2 * shown
                drawPath(segment(measure, length, 0f, h), tone, alpha = a, style = stroke)
                drawPath(segment(measure, length, length - h, length), tone, alpha = a, style = stroke)
            }
            // The gleam: the bottom edge only, briefly, as the light sets off.
            if (gleam > 0f) {
                val g = length * 0.16f
                drawPath(
                    segment(measure, length, length - g, length + g),
                    Brush.horizontalGradient(listOf(bright[0], bright[1], bright[2], bright[3], bright[4])),
                    alpha = (gleam * alpha * 1.1f).coerceAtMost(1f),
                    style = stroke,
                )
            }
            fadeTowardTop(top = 0.55f)
        }
    }

    Box(modifier.fillMaxSize()) {
        if (blurs) Layer(blur = 20f, lineWidth = 30f, alpha = 1f)
        else {
            Layer(blur = 0f, lineWidth = 14f, alpha = 0.18f)
            Layer(blur = 0f, lineWidth = 6f, alpha = 0.3f)
        }
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
