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

/** Draws the part of the outline that has lit up: from the bottom centre up both sides, meeting at the top. */
private fun DrawScope.edgeLight(brush: ShaderBrush, radius: Float, width: Float, reveal: Float, alpha: Float = 1f) {
    if (reveal <= 0f) return
    val measure = PathMeasure().apply { setPath(edgePath(size, radius, width / 2), false) }
    val length = measure.length
    val half = length / 2 * reveal.coerceIn(0f, 1f)
    val stroke = Stroke(width = width, cap = StrokeCap.Round)
    if (reveal >= 1f) {
        drawPath(edgePath(size, radius, width / 2), brush, alpha = alpha, style = stroke)
        return
    }
    val a = Path(); measure.getSegment(0f, half, a, true)
    val b = Path(); measure.getSegment(length - half, length, b, true)
    drawPath(a, brush, alpha = alpha, style = stroke)
    drawPath(b, brush, alpha = alpha, style = stroke)
}

/** Light is strongest at the bottom, where the panel is, and fades toward the top of the screen. */
private fun DrawScope.fadeTowardTop(top: Float = 0.25f) = drawRect(
    Brush.verticalGradient(0f to Color.Black.copy(alpha = top), 0.55f to Color.Black.copy(alpha = 0.6f), 1f to Color.Black),
    blendMode = BlendMode.DstIn,
)

/**
 * The light of the overlay, in the manner of the system assistant:
 * - [edge]: a thin bright line round the screen with a soft halo, rising from the bottom ([reveal] 0 → 1);
 * - [aurora]: a luminous horizon behind the panel while Bayan works;
 * - [border]: the same light, finer, round the panel at [panel].
 * Each part is a stack of the same shape at growing width and blur: crisp line, inner glow, outer halo.
 */
@Composable
fun OverlayGlow(reveal: Float, edge: Float, aurora: Float, border: Float, panel: Rect?, working: Boolean, modifier: Modifier = Modifier) {
    val colors = glowColors()
    val transition = rememberInfiniteTransition(label = "glow")
    val angle by transition.animateFloat(0f, 360f, infiniteRepeatable(tween(if (working) 7000 else 14000, easing = LinearEasing)), label = "angle")
    val breathe by transition.animateFloat(0.85f, 1f, infiniteRepeatable(tween(2200), RepeatMode.Reverse), label = "breathe")
    val radius = screenCornerRadius()
    val density = LocalDensity.current
    val panelRadius = with(density) { 32.dp.toPx() }
    val blurs = Build.VERSION.SDK_INT >= Build.VERSION_CODES.S
    val pulse = if (working) breathe else 1f

    @Composable
    fun Layer(blur: Float, lineWidth: Float, panelWidth: Float, edgeAlpha: Float, panelAlpha: Float, horizon: Boolean = false) {
        val blurPx = with(density) { blur.dp.toPx() }
        Canvas(
            Modifier
                .fillMaxSize()
                .graphicsLayer {
                    compositingStrategy = CompositingStrategy.Offscreen
                    if (blurs && blur > 0f) renderEffect = BlurEffect(blurPx, blurPx, TileMode.Decal)
                },
        ) {
            val brush = sweepBrush(colors, center, angle)
            if (horizon && aurora > 0f) {
                drawRect(
                    Brush.radialGradient(
                        listOf(colors[1].copy(alpha = 0.35f), colors[3].copy(alpha = 0.16f), Color.Transparent),
                        center = Offset(size.width * (0.5f + 0.18f * kotlin.math.sin(Math.toRadians(angle.toDouble())).toFloat()), size.height * 1.02f),
                        radius = size.width * 0.95f,
                    ),
                    alpha = aurora * pulse,
                )
            }
            if (edge > 0f && lineWidth > 0f) {
                edgeLight(brush, radius, with(density) { lineWidth.dp.toPx() }, reveal, (edge * edgeAlpha * pulse).coerceAtMost(1f))
            }
            if (border > 0f && panel != null && panelWidth > 0f) {
                drawRoundRect(
                    sweepBrush(colors, panel.center, -angle),
                    topLeft = panel.topLeft,
                    size = panel.size,
                    cornerRadius = CornerRadius(panelRadius),
                    alpha = (border * panelAlpha * pulse).coerceAtMost(1f),
                    style = Stroke(width = with(density) { panelWidth.dp.toPx() }),
                )
            }
            fadeTowardTop()
        }
    }

    Box(modifier.fillMaxSize()) {
        if (blurs) {
            Layer(blur = 56f, lineWidth = 30f, panelWidth = 20f, edgeAlpha = 0.28f, panelAlpha = 0.3f, horizon = true)
            Layer(blur = 12f, lineWidth = 7f, panelWidth = 5f, edgeAlpha = 0.5f, panelAlpha = 0.45f)
        } else {
            Layer(blur = 0f, lineWidth = 14f, panelWidth = 8f, edgeAlpha = 0.18f, panelAlpha = 0.2f)
            Layer(blur = 0f, lineWidth = 6f, panelWidth = 4f, edgeAlpha = 0.35f, panelAlpha = 0.35f)
        }
        Layer(blur = 0f, lineWidth = 1.8f, panelWidth = 1.2f, edgeAlpha = 0.85f, panelAlpha = 0.7f)
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
