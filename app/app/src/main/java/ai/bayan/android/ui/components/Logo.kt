package ai.bayan.android.ui.components

import androidx.compose.foundation.Canvas
import ai.bayan.android.data.AppStyle
import ai.bayan.android.ui.theme.LocalAppStyle
import kotlinx.coroutines.launch
import kotlinx.coroutines.delay
import androidx.compose.ui.graphics.Brush
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.animation.core.LinearOutSlowInEasing
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.tween
import androidx.compose.animation.core.Animatable
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.PathFillType
import androidx.compose.ui.graphics.drawscope.scale
import androidx.compose.ui.graphics.drawscope.translate
import androidx.compose.ui.graphics.vector.PathParser
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics

/** One lockup of Bayan's logo: its view box, the ink outline (SVG path data, even-odd) and the sun (cx, cy, r). */
internal class LogoShape(val viewBox: FloatArray, val ink: String, val sun: FloatArray)

enum class LogoLockup { Symbol, Mark, Stacked, Horizontal }

private val Played = HashSet<LogoLockup>()

/**
 * Bayan's logo, drawn from the design system's vector outlines: the open book and بيان in ink, the sun where the ن's
 * dot would be. Its colours follow the theme: ink is the text colour, and the sun is the accent (the ochre of the logo
 * itself in Bayan's style). Size it by height; the width follows the lockup.
 */
@Composable
fun BayanLogo(
    lockup: LogoLockup,
    modifier: Modifier = Modifier,
    ink: Color = MaterialTheme.colorScheme.onSurface,
    sun: Color = logoSun(),
    /** Plays the splash's sunrise once when it first appears: the book opens from its spine, the sun rises and glows. */
    sunrise: Boolean = false,
) {
    // Once per lockup while the app runs: coming back to a screen does not replay it.
    val play = remember { sunrise && Played.add(lockup) }
    val book = remember { Animatable(if (play) 0f else 1f) }
    val rise = remember { Animatable(if (play) 0f else 1f) }
    val glow = remember { Animatable(if (play) 0f else 0.3f) }
    if (play) LaunchedEffect(Unit) {
        launch { book.animateTo(1f, tween(620, easing = FastOutSlowInEasing)) }
        delay(380)
        launch { rise.animateTo(1f, spring(dampingRatio = 0.55f, stiffness = 260f)) }
        delay(260)
        glow.animateTo(1f, tween(260, easing = LinearOutSlowInEasing))
        glow.animateTo(0.3f, tween(700, easing = FastOutSlowInEasing))
    }
    val shape = when (lockup) {
        LogoLockup.Symbol -> LogoSymbol
        LogoLockup.Mark -> LogoMark
        LogoLockup.Stacked -> LogoStacked
        LogoLockup.Horizontal -> LogoHorizontal
    }
    val path = remember(shape) { PathParser().parsePathString(shape.ink).toPath().apply { fillType = PathFillType.EvenOdd } }
    val (x0, y0, w, h) = shape.viewBox.toList()
    Canvas(modifier.aspectRatio(w / h).semantics { contentDescription = "بيان Bayan" }) {
        val k = size.height / h
        val (cx, cy, r) = shape.sun.toList()
        scale(k, k, pivot = Offset.Zero) {
            translate(-x0, -y0) {
                val g = glow.value
                if (g > 0f) drawCircle(
                    Brush.radialGradient(listOf(sun.copy(alpha = 0.6f * g), sun.copy(alpha = 0.2f * g), Color.Transparent), Offset(cx, cy), r * 3.2f),
                    radius = r * 3.2f, center = Offset(cx, cy),
                )
                val b = book.value
                // the book opens from its spine (the bottom of the fold, under the sun)
                scale(0.08f + 0.92f * b, 0.7f + 0.3f * b, pivot = Offset(cx, y0 + h)) {
                    drawPath(path, ink, alpha = (b * 2.5f).coerceAtMost(1f))
                }
                val u = rise.value
                if (u > 0f) drawCircle(sun, radius = r * u.coerceAtLeast(0f), center = Offset(cx, cy + 70f * (1f - u)))
            }
        }
    }
}

/** The sun: the logo's own ochre in Bayan's style (it is the primary's source there), the accent otherwise. */
@Composable
private fun logoSun(): Color =
    if (LocalAppStyle.current == AppStyle.Bayan) Color(0xFFC6986B) else MaterialTheme.colorScheme.primary
