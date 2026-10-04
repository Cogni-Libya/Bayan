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
import androidx.compose.ui.graphics.luminance
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
 * The light of the overlay: the system assistant's light, measured frame by frame on a phone (the light along every
 * edge over time, and across the edge at each height), in the Material theme's colours. Times are from [started] (the window is on
 * screen):
 * - 0–0.5 s: a rim of the theme's pale primary lights the whole outline of the screen at once, strongest in the bottom
 *   corners;
 * - 0.1–1.6 s: the theme's colours bloom at their places on the rim, as the assistant's four colours do — the primary
 *   low on the left, the tertiary drifting along the bottom and at the bottom right, and a tertiary streak high on the
 *   right that slides down the side and turns toward the primary — then melt into the rim;
 * - 1.6–2.1 s: the bottom glows fullest;
 * - 2.1–3.5 s: it eases down to about a quarter and holds, breathing, while Bayan works.
 * The rim is a hair of light at the sides and the top (gone about 15 dp in) that widens into a soft bloom over the
 * lowest third of the screen. Under it a faint, still grain lifts the screen a little, more toward the bottom.
 * [edge] scales the light: the activity fades it out once the text is ready, or when the overlay closes; [veil] is the
 * grain's strength. With animations off (Settings ▸ Accessibility ▸ Remove animations) it is a still, faint rim.
 */
@Composable
fun OverlayGlow(started: Boolean, reveal: Float, edge: Float, veil: Float, aurora: Float, border: Float, panel: Rect?, working: Boolean, modifier: Modifier = Modifier) {
    val context = LocalView.current.context
    val still = remember {
        android.provider.Settings.Global.getFloat(context.contentResolver, android.provider.Settings.Global.ANIMATOR_DURATION_SCALE, 1f) == 0f
    }
    // A frame-paced clock: it advances by at most one frame (20 ms) per drawn frame, so slow first frames pause the
    // light instead of skipping the part the reader should see.
    var clockValue by androidx.compose.runtime.remember { androidx.compose.runtime.mutableFloatStateOf(if (still) GLOW_END else 0f) }
    androidx.compose.runtime.LaunchedEffect(started) {
        if (!started || still) return@LaunchedEffect
        var last = androidx.compose.runtime.withFrameNanos { it }
        while (clockValue < GLOW_END) {
            androidx.compose.runtime.withFrameNanos { now ->
                clockValue = (clockValue + ((now - last) / 1e9f).coerceAtMost(0.02f)).coerceAtMost(GLOW_END)
                last = now
            }
        }
    }
    val transition = rememberInfiniteTransition(label = "glow")
    val now by transition.animateFloat(0f, 600f, infiniteRepeatable(tween(600_000, easing = LinearEasing)), label = "now")
    val breathe by transition.animateFloat(0.8f, 1.15f, infiniteRepeatable(tween(2600), RepeatMode.Reverse), label = "breathe")
    val radius = screenCornerRadius()
    val density = LocalDensity.current
    val t = clockValue
    val k = edge * (if (t >= GLOW_END && working && !still) breathe else 1f)
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
        if (!started || (k <= 0f && veil <= 0f)) return
        val shader = remember { android.graphics.RuntimeShader(EDGE_LIGHT_SHADER) }
        val dp = density.density
        val colours = edgeLightColours()
        val paper = if (MaterialTheme.colorScheme.surface.luminance() < 0.5f) 0f else 1f
        Canvas(modifier.fillMaxSize()) {
            shader.setFloatUniform("size", size.width, size.height)
            shader.setFloatUniform("radius", radius)
            shader.setFloatUniform("dp", dp)
            shader.setFloatUniform("t", t / GLOW_PACE)
            shader.setFloatUniform("strength", k)
            shader.setFloatUniform("veil", veil)
            shader.setFloatUniform("now", if (working) now else 0f)
            shader.setFloatUniform("paper", paper)
            val p = panel ?: Rect.Zero
            shader.setFloatUniform("panel", p.left, p.top, p.right, p.bottom)
            shader.setFloatUniform("panelRadius", 32 * dp)
            shader.setColorUniform("rim", colours[0].toArgb())
            shader.setColorUniform("first", colours[1].toArgb())
            shader.setColorUniform("second", colours[2].toArgb())
            shader.setColorUniform("between", colours[3].toArgb())
            drawRect(ShaderBrush(shader))
        }
        return
    }
    if (k <= 0f) return
    val rise = androidx.compose.animation.core.FastOutSlowInEasing.transform((t / 0.45f).coerceIn(0f, 1f))
    val body = 1f - 0.75f * smoothstep(2.1f, 3.5f, t)
    Box(modifier.fillMaxSize()) { LegacyGlow(k * body, rise, 0f, 0f, radius) }
}

/**
 * The light's colours, from the Material theme (the wallpaper's colours, or the palette chosen in Bayan's settings), as
 * the system assistant takes its settled light from the phone's palette: the primary, pale, for the rim; the primary,
 * the tertiary and a hue halfway between them for the blooms. Hues are kept; lightness and saturation are set so they
 * read as light, not paint. A grey theme stays grey.
 */
@Composable
internal fun edgeLightColours(): List<Color> {
    val scheme = MaterialTheme.colorScheme
    val primary = scheme.primary
    val tertiary = scheme.tertiary
    val dark = scheme.surface.luminance() < 0.5f
    return remember(primary, tertiary, dark) {
        fun hsl(c: Color) = FloatArray(3).also { ColorUtils.colorToHSL(c.toArgb(), it) }
        val p = hsl(primary)
        val q = hsl(tertiary)
        fun light(h: Float, s: Float, l: Float) =
            Color(ColorUtils.HSLToColor(floatArrayOf((h + 360f) % 360f, if (s < 0.08f) s else maxOf(s, 0.75f), l)))
        val gap = ((q[0] - p[0] + 540f) % 360f) - 180f           // shortest way round the colour wheel
        // On a light theme (light screens beneath) a pale light would vanish: the same hues, deeper.
        val l = if (dark) floatArrayOf(0.8f, 0.66f, 0.66f, 0.7f) else floatArrayOf(0.66f, 0.55f, 0.55f, 0.58f)
        listOf(
            light(p[0], maxOf(p[1], 0.9f).takeIf { p[1] >= 0.08f } ?: p[1], l[0]),
            light(p[0], p[1], l[1]),
            light(q[0], q[1], l[2]),
            light(p[0] + gap / 2f, (p[1] + q[1]) / 2f, l[3]),
        )
    }
}

/** When the entrance of the light is over (s); it then holds, breathing while Bayan works. */
private const val GLOW_END = 6f

/** The light is unhurried: its choreography (timed after the assistant's) is played this many times slower. */
private const val GLOW_PACE = 1.7f

/**
 * The edge light as a shader (Android 13+): for every pixel, the exact distance to the screen's rounded edge and a
 * smooth exponential fall-off from it, so the light melts into the screen with no banding. The fall-off widens from
 * 6 dp at the sides and the top to 62 dp over the lowest third of the screen, and further where a colour blooms. The
 * colours are the theme's ([edgeLightColours]); the blooms come and go in the first two seconds (see [OverlayGlow]).
 * A still grain (a fixed hash of the pixel) lifts the screen a little, more toward the bottom, like frosted glass.
 */
private const val EDGE_LIGHT_SHADER = """
uniform float2 size;
uniform float radius;
uniform float dp;
uniform float t;
uniform float strength;
uniform float veil;
uniform float now;
uniform float paper;
uniform float4 panel;                 // what is visible of the panel (left, top, right, bottom); empty when none
uniform float panelRadius;                  // 1 on a light theme: the grain is paler, so it never greys a white page                    // seconds, running on while the overlay is open (for the twinkle)

layout(color) uniform half4 rim;      // the theme's primary, pale: the light once it settles
layout(color) uniform half4 first;    // primary
layout(color) uniform half4 second;   // tertiary
layout(color) uniform half4 between;  // halfway between them

float sdRoundBox(float2 p, float2 b, float r) {
    float2 q = abs(p) - b + r;
    return length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - r;
}

float bump(float x, float a, float b, float c, float d) {
    return smoothstep(a, b, x) * (1.0 - smoothstep(c, d, x));
}

float blob(float2 p, float2 c, float2 r) {
    float2 q = (p - c) / r;
    return exp(-dot(q, q));
}

float hash(float2 p) {
    p = fract(p * float2(0.1031, 0.1030));
    p += dot(p, p.yx + 33.33);
    return fract((p.x + p.y) * p.x);
}

// A soft eight-pointed glint (the assistant's are four-pointed): long arms on the axes, shorter ones on the diagonals.
float glint(float2 q, float r) {
    float2 a = abs(q);
    float axes = exp(-a.x / (0.3 * r)) * exp(-a.y / r) + exp(-a.y / (0.3 * r)) * exp(-a.x / r);
    float2 d = float2(a.x + a.y, abs(a.x - a.y)) * 0.7071;
    float diag = exp(-d.y / (0.3 * r)) * exp(-d.x / (0.6 * r));
    return max(0.8 * axes + 0.4 * diag, exp(-dot(q, q) / (0.16 * r * r)));
}

float grain(float2 p) {
    p = fract(floor(p) * float2(0.1031, 0.1030));
    p += dot(p, p.yx + 33.33);
    return fract((p.x + p.y) * p.x);
}

half4 main(float2 xy) {
    float2 c = size * 0.5;
    float d = max(-sdRoundBox(xy - c, c, radius), 0.0);
    // The light's floor: the top of the panel when there is one (so the bloom sits where the reader can see it, and
    // rises with the panel as it unfolds), else the bottom of the screen.
    bool hasPanel = panel.z > panel.x;
    float floorY = hasPanel ? min(panel.y + 24.0 * dp, size.y) : size.y;
    float up = size.y - xy.y;                                   // px above the bottom edge
    float aboveFloor = max(floorY - xy.y, 0.0);
    float low = max(1.0 - smoothstep(0.0, 0.32 * size.y, up),  // 1 at the bottom, 0 from a third of the way up
                    1.0 - smoothstep(0.0, 0.24 * size.y, aboveFloor));
    // In the entrance the light climbs from the floor up both sides to the top, with a soft front.
    float climb = 1.0 - pow(1.0 - clamp(t / 0.6, 0.0, 1.0), 3.0);
    float reach = aboveFloor / max(floorY, 1.0);
    float rising = 1.0 - smoothstep(climb * 1.2 - 0.25, climb * 1.2, reach);

    float bottom = smoothstep(0.0, 0.5, t) * (1.0 - 0.15 * bump(t, 0.75, 1.05, 1.1, 1.4)) * (1.0 - 0.78 * smoothstep(2.1, 3.5, t));
    float side = smoothstep(0.0, 0.45, t) * (1.0 - 0.2 * bump(t, 0.7, 1.0, 1.2, 1.5)) * (1.0 - 0.7 * smoothstep(2.0, 3.4, t));
    float amp = mix(0.6 * side, 0.72 * bottom, pow(low, 1.2));
    float centre = 1.0 - smoothstep(0.2 * size.x, 0.42 * size.x, abs(xy.x - c.x));
    float mid = (1.0 - 0.3 * bump(t, 0.7, 1.0, 1.1, 1.4) * centre) * (1.0 - 0.3 * centre * smoothstep(2.0, 2.5, t));
    float k = bump(t, 0.1, 0.4, 0.9, 1.6);
    float2 s = size;
    float wBrick = blob(xy, float2(0.0, floorY - 0.12 * s.y), float2(0.35 * s.x, 0.2 * s.y)) * k;
    float wSlate = blob(xy, float2(s.x * (0.72 - 0.22 * smoothstep(0.4, 1.2, t)), floorY - 0.02 * s.y), float2(0.2 * s.x, 0.07 * s.y)) * k;
    float wCorner = blob(xy, float2(0.9 * s.x, floorY), float2(0.14 * s.x, 0.07 * s.y)) * k * 0.9;
    float wStreak = blob(xy, float2(s.x, floorY * (0.18 + 0.5 * smoothstep(0.3, 1.6, t))), float2(0.25 * s.x, 0.2 * s.y))
        * bump(t, 0.1, 0.35, 1.45, 2.0) * 1.1;
    // where a colour blooms, its light reaches further into the screen
    float fall = 6.0 * dp + 56.0 * dp * pow(low, 1.6) + 36.0 * dp * min(wBrick + 0.12 * wStreak + 0.5 * wSlate, 1.0);
    float glow = exp(-d / fall) * amp * (1.0 + (mid - 1.0) * low) * rising;
    // Light from the panel's own outline: it follows the droplet, the pill and the panel as they grow, brightest in
    // the entrance, then a quiet halo round what the reader is reading.
    if (panel.z > panel.x) {
        float2 pc = (panel.xy + panel.zw) * 0.5;
        float2 ph = (panel.zw - panel.xy) * 0.5;
        float dp2 = max(sdRoundBox(xy - pc, ph, min(panelRadius, min(ph.x, ph.y))), 0.0);
        float pAmp = smoothstep(0.0, 0.35, t) * (1.0 - 0.6 * smoothstep(1.6, 3.2, t));
        // above the panel the light is a taller dawn, as if rising from behind it
        float above = smoothstep(0.0, 1.0, (panel.y - xy.y) / (8.0 * dp));
        float pFall = mix(12.0, 34.0, above * centre) * dp;
        glow = max(glow, exp(-dp2 / pFall) * mix(0.62, 0.7, above) * pAmp);
    }
    half3 corner = mix(second.rgb, between.rgb, smoothstep(0.6, 1.1, t));
    half3 streak = mix(second.rgb, between.rgb, smoothstep(0.7, 1.3, t));
    float blobs = wBrick + wSlate + wCorner + wStreak;
    half3 col = (rim.rgb * 0.12 + first.rgb * wBrick + second.rgb * wSlate + corner * wCorner + streak * wStreak) / (0.12 + blobs);
    float alpha = clamp(glow * (1.0 + 0.9 * blobs * (1.0 - 0.5 * low)) * strength, 0.0, 0.92);

    // Sparkles: glints on a loose lattice that twinkle into the coloured light one by one, as the assistant's do,
    // and fade with it; while Bayan works a sparse few go on twinkling in the rim.
    float cellSize = 9.0 * dp;
    float2 cell = floor(xy / cellSize);
    float2 jitter = float2(hash(cell + 11.0), hash(cell + 37.0));
    float2 centre2 = (cell + 0.2 + 0.6 * jitter) * cellSize;
    float born = 0.3 + 0.7 * hash(cell + 71.0);
    float phase = 6.2831853 * hash(cell + 5.0);
    float twinkle = 0.55 + 0.45 * sin(now * (1.1 + 1.2 * hash(cell + 3.0)) + phase);
    float early = smoothstep(born, born + 0.25, t) * (1.0 - smoothstep(2.3, 3.0, t)) * clamp(blobs * 1.6 + 0.5 * low, 0.0, 1.0);
    float later = smoothstep(2.6, 3.4, t) * step(0.86, hash(cell + 91.0)) * low;
    float spark = glint(xy - centre2, 2.0 * dp) * twinkle * (early + 0.6 * later) * smoothstep(0.12, 0.5, alpha);
    half3 sparkCol = mix(col, half3(1.0), 0.65);
    half sa = half(clamp(spark * 0.45, 0.0, 0.6));
    col = (col * alpha + sparkCol * sa * (1.0 - alpha * 0.5)) / max(alpha + sa * (1.0 - alpha * 0.5), 0.001);
    alpha = clamp(alpha + sa * (1.0 - alpha * 0.5), 0.0, 0.95);

    float va = (0.09 + 0.12 * low) * veil * (1.0 - 0.35 * paper);   // the still grain
    half g = half(mix(0.35, 0.82, paper) + mix(0.65, 0.18, paper) * grain(xy));
    // grain under the light: premultiplied "light over grain"
    half3 rgb = col * alpha + half3(g) * va * (1.0 - alpha);
    half a = half(alpha + va * (1.0 - alpha));
    return half4(rgb, a);
}
"""

/** Before Android 13: the same light from blurred strokes (no per-pixel shader). */
@Composable
private fun LegacyGlow(k: Float, rise: Float, swell: Float, drift: Float, radius: Float) {
    val density = LocalDensity.current
    val blurs = Build.VERSION.SDK_INT >= Build.VERSION_CODES.S
    val colours = edgeLightColours().let { listOf(it[0], it[1], it[0], it[2], it[0], it[3], it[0]) }
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
            val brush = sweepBrush(colours, center, drift)
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
