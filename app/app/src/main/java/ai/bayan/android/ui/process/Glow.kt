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
import androidx.compose.runtime.setValue
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
 * Bayan's sunrise palette round the screen, as fractions of a turn starting at the right edge and going clockwise
 * (so 0.25 is the bottom centre): the sun under the book of the logo at the bottom, terracotta at the bottom corners,
 * warm peach up the sides and a soft teal sky at the top.
 */
private val SUNRISE = listOf(
    0.000f to Color(0xFFF3C9A6), // right: peach
    0.125f to Color(0xFFE88E6B), // bottom right: terracotta
    0.250f to Color(0xFFF6C35E), // bottom: sun
    0.375f to Color(0xFFE88E6B), // bottom left: terracotta
    0.500f to Color(0xFFF3C9A6), // left: peach
    0.625f to Color(0xFFF6E3C8), // top left: cream
    0.750f to Color(0xFF8CCFC0), // top: teal sky
    0.875f to Color(0xFFF6E3C8), // top right: cream
    1.000f to Color(0xFFF3C9A6),
)

private fun sunriseBrush(center: Offset, drift: Float): ShaderBrush {
    val shader = SweepGradient(center.x, center.y, SUNRISE.map { it.second.toArgb() }.toIntArray(), SUNRISE.map { it.first }.toFloatArray())
    shader.setLocalMatrix(Matrix().apply { postRotate(drift, center.x, center.y) })
    return ShaderBrush(shader)
}

/**
 * The light of the overlay: the system assistant's choreography, measured frame by frame on a phone (light per edge
 * region over time), in Bayan's sunrise colours. Times are from [started] (the window is on screen):
 * - 0–0.35 s: the light appears at the bottom and runs up both sides at once to the top;
 * - to 1.6 s: full strength; the bottom corners are the brightest, then the bottom edge, while the sides and the top
 *   carry a fainter light (about 0.4 of the corners); the colours drift slowly round the screen;
 * - 1.6–2.2 s: a second, gentler swell along the bottom;
 * - 2.2–3 s: it eases down to a quarter and holds, breathing, while Bayan works.
 * At the sides the light is brightest at the very edge and gone about 13 dp in; along the bottom it is a taller band.
 * [edge] scales everything: the activity fades it out once the text is ready, or when the overlay closes.
 * With animations off (Settings ▸ Accessibility ▸ Remove animations) it is a still, faint frame.
 */
@Composable
fun OverlayGlow(started: Boolean, reveal: Float, edge: Float, aurora: Float, border: Float, panel: Rect?, working: Boolean, modifier: Modifier = Modifier) {
    val context = LocalView.current.context
    val still = remember {
        android.provider.Settings.Global.getFloat(context.contentResolver, android.provider.Settings.Global.ANIMATOR_DURATION_SCALE, 1f) == 0f
    }
    // A frame-paced clock: it advances by at most one frame (20 ms) per drawn frame, so the long first frames (shader
    // compilation of the blur) pause the light instead of skipping the rise the reader should see.
    var clockValue by androidx.compose.runtime.remember { androidx.compose.runtime.mutableFloatStateOf(if (still) 3f else 0f) }
    androidx.compose.runtime.LaunchedEffect(started) {
        if (!started || still) return@LaunchedEffect
        var last = androidx.compose.runtime.withFrameNanos { it }
        while (clockValue < 3f) {
            androidx.compose.runtime.withFrameNanos { now ->
                clockValue = (clockValue + ((now - last) / 1e9f).coerceAtMost(0.02f)).coerceAtMost(3f)
                last = now
            }
        }
    }
    val transition = rememberInfiniteTransition(label = "glow")
    val wander by transition.animateFloat(-14f, 14f, infiniteRepeatable(tween(5200), RepeatMode.Reverse), label = "wander")
    val breathe by transition.animateFloat(0.85f, 1f, infiniteRepeatable(tween(2600), RepeatMode.Reverse), label = "breathe")
    val radius = screenCornerRadius()
    val density = LocalDensity.current
    val blurs = Build.VERSION.SDK_INT >= Build.VERSION_CODES.S
    val t = clockValue
    val rise = androidx.compose.animation.core.FastOutSlowInEasing.transform((t / 0.35f).coerceIn(0f, 1f))
    val body = when {                                   // the whole light
        t < 0.5f -> smoothstep(0f, 0.5f, t)
        t < 1.6f -> 1f
        else -> 1f - 0.75f * smoothstep(2.2f, 3f, t)
    } * (if (t >= 3f && working && !still) breathe else 1f)
    val swell = smoothstep(1.5f, 2.0f, t) * (1f - smoothstep(2.1f, 2.6f, t)) // the second swell along the bottom
    val drift = if (still) 0f else wander + 26f * smoothstep(0.4f, 2.2f, t)
    if (edge <= 0f || body <= 0f) return
    val k = edge * body
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
        val shader = remember { android.graphics.RuntimeShader(EDGE_LIGHT_SHADER) }
        val sideFalloff = with(density) { 6.5.dp.toPx() }
        val bottomFalloff = with(density) { 26.dp.toPx() }
        Canvas(modifier.fillMaxSize()) {
            shader.setFloatUniform("size", size.width, size.height)
            shader.setFloatUniform("radius", radius)
            shader.setFloatUniform("sideFalloff", sideFalloff)
            shader.setFloatUniform("bottomFalloff", bottomFalloff)
            shader.setFloatUniform("rise", rise)
            shader.setFloatUniform("strength", k)
            shader.setFloatUniform("swell", swell)
            shader.setFloatUniform("drift", Math.toRadians(drift.toDouble()).toFloat())
            drawRect(ShaderBrush(shader))
        }
        return
    }
    Box(modifier.fillMaxSize()) { LegacyGlow(k, rise, swell, drift, radius) }
}

/**
 * The edge light as a shader (Android 13+): for every pixel, the exact distance to the screen's rounded edge, and a
 * smooth exponential fall-off from it, so the light melts into the screen the way light from the bezel would, with
 * no banding. The fall-off is about 6.5 dp at the sides and a taller 26 dp along the bottom; the bottom corners carry
 * the most light. The colour is a luminous cream tinted by Bayan's sunrise round the screen (sun at the bottom
 * centre, terracotta at the bottom corners, peach on the sides, a teal sky at the top), drifting slowly.
 * [rise] (0 → 1) carries the light from the bottom up both sides; its front is soft.
 */
private const val EDGE_LIGHT_SHADER = """
uniform float2 size;
uniform float radius;
uniform float sideFalloff;
uniform float bottomFalloff;
uniform float rise;
uniform float strength;
uniform float swell;
uniform float drift;

float sdRoundBox(float2 p, float2 b, float r) {
    float2 q = abs(p) - b + r;
    return length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - r;
}

half3 sunrise(float a) {
    // a: angle in turns, 0 = right, 0.25 = bottom (y grows downward), clockwise
    half3 peach = half3(0.953, 0.788, 0.651);
    half3 terracotta = half3(0.910, 0.557, 0.420);
    half3 sun = half3(0.965, 0.765, 0.369);
    half3 cream = half3(0.965, 0.890, 0.784);
    half3 sky = half3(0.549, 0.812, 0.753);
    float t = fract(a) * 8.0;
    half3 c0; half3 c1;
    if (t < 1.0)      { c0 = peach;      c1 = terracotta; }
    else if (t < 2.0) { c0 = terracotta; c1 = sun; }
    else if (t < 3.0) { c0 = sun;        c1 = terracotta; }
    else if (t < 4.0) { c0 = terracotta; c1 = peach; }
    else if (t < 5.0) { c0 = peach;      c1 = cream; }
    else if (t < 6.0) { c0 = cream;      c1 = sky; }
    else if (t < 7.0) { c0 = sky;        c1 = cream; }
    else              { c0 = cream;      c1 = peach; }
    return mix(c0, c1, smoothstep(0.0, 1.0, fract(t)));
}

half4 main(float2 xy) {
    float2 c = size * 0.5;
    float d = max(-sdRoundBox(xy - c, c, radius), 0.0);      // distance inside the screen's edge, px
    float v = 1.0 - xy.y / size.y;                            // 0 at the bottom, 1 at the top
    float front = rise * 1.15;
    float reveal = 1.0 - smoothstep(front - 0.18, front, v);  // the rising light, with a soft front
    float fall = mix(bottomFalloff, sideFalloff, smoothstep(0.0, 0.07, v));
    float glow = exp(-d / fall);
    float corner = 1.0 + 0.9 * (1.0 - smoothstep(0.0, 0.09, v)) * smoothstep(0.25, 0.5, abs(xy.x - c.x) / size.x);
    float bottom = 1.0 + (0.35 + 0.5 * swell) * (1.0 - smoothstep(0.0, 0.05, v));
    float a = atan(xy.y - c.y, xy.x - c.x) / 6.2831853 + drift / 6.2831853;
    half3 col = mix(half3(1.0, 0.96, 0.92), sunrise(a), 0.62);
    float alpha = clamp(glow * reveal * strength * 0.62 * corner * bottom, 0.0, 0.9);
    return half4(col * alpha, alpha);
}
"""

/** Before Android 13: the same light from blurred strokes (no per-pixel shader). */
@Composable
private fun LegacyGlow(k: Float, rise: Float, swell: Float, drift: Float, radius: Float) {
    val density = LocalDensity.current
    val blurs = Build.VERSION.SDK_INT >= Build.VERSION_CODES.S
    @Composable
    fun Layer(blur: Float, sideWidth: Float, bottomBand: Float, sideAlpha: Float, bottomAlpha: Float) {
        val blurPx = with(density) { blur.dp.toPx() }
        Canvas(
            Modifier
                .fillMaxSize()
                .graphicsLayer {
                    compositingStrategy = CompositingStrategy.Offscreen
                    if (blurs && blur > 0f) renderEffect = BlurEffect(blurPx, blurPx, TileMode.Decal)
                },
        ) {
            val width = with(density) { sideWidth.dp.toPx() }
            val band = with(density) { bottomBand.dp.toPx() }
            val brush = sunriseBrush(center, drift)
            val path = edgePath(size, radius, 0f)
            val measure = PathMeasure().apply { setPath(path, false) }
            val length = measure.length
            val stroke = Stroke(width = width * 2, cap = StrokeCap.Round)
            val side = (k * sideAlpha).coerceIn(0f, 1f)
            if (rise >= 1f) drawPath(path, brush, alpha = side, style = stroke)
            else if (rise > 0f) {
                val h = length / 2 * rise
                drawPath(segment(measure, length, 0f, h), brush, alpha = side, style = stroke)
                drawPath(segment(measure, length, length - h, length), brush, alpha = side, style = stroke)
            }
            drawRect(brush, topLeft = Offset(0f, size.height - band), size = Size(size.width, band), alpha = (k * (bottomAlpha + 0.5f * swell)).coerceIn(0f, 1f))
            drawRect(
                Brush.verticalGradient(listOf(Color.Black, Color.Transparent), startY = size.height - band, endY = size.height),
                topLeft = Offset(0f, size.height - band), size = Size(size.width, band), blendMode = BlendMode.DstOut,
            )
        }
    }
    Layer(blur = if (blurs) 9f else 0f, sideWidth = 13f, bottomBand = 34f, sideAlpha = 0.42f, bottomAlpha = 0.75f)
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
