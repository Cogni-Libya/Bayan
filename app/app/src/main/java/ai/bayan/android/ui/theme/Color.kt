package ai.bayan.android.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import ai.bayan.android.data.ReaderSurface

// Only for Android 8–11, which have no wallpaper colours: Material's tonal palette from the launcher icon's teal.
val FallbackLight = lightColorScheme(
    primary = Color(0xFF006A60), onPrimary = Color.White,
    primaryContainer = Color(0xFF9EF2E4), onPrimaryContainer = Color(0xFF00201C),
    secondary = Color(0xFF4A635F), secondaryContainer = Color(0xFFCCE8E2), onSecondaryContainer = Color(0xFF05201C),
    tertiary = Color(0xFF456179), tertiaryContainer = Color(0xFFCCE5FF), onTertiaryContainer = Color(0xFF001E31),
    background = Color(0xFFF4FBF8), surface = Color(0xFFF4FBF8), onSurface = Color(0xFF161D1C),
    surfaceVariant = Color(0xFFDAE5E1), onSurfaceVariant = Color(0xFF3F4947),
    surfaceContainerLowest = Color.White, surfaceContainerLow = Color(0xFFEEF5F2), surfaceContainer = Color(0xFFE9EFEC),
    surfaceContainerHigh = Color(0xFFE3EAE7), surfaceContainerHighest = Color(0xFFDDE4E1),
    outline = Color(0xFF6F7977), outlineVariant = Color(0xFFBEC9C6),
)

val FallbackDark = darkColorScheme(
    primary = Color(0xFF82D5C8), onPrimary = Color(0xFF003731),
    primaryContainer = Color(0xFF005048), onPrimaryContainer = Color(0xFF9EF2E4),
    secondary = Color(0xFFB1CCC6), secondaryContainer = Color(0xFF334B47), onSecondaryContainer = Color(0xFFCCE8E2),
    tertiary = Color(0xFFADCAE6), tertiaryContainer = Color(0xFF2D4960), onTertiaryContainer = Color(0xFFCCE5FF),
    background = Color(0xFF0E1513), surface = Color(0xFF0E1513), onSurface = Color(0xFFDDE4E1),
    surfaceVariant = Color(0xFF3F4947), onSurfaceVariant = Color(0xFFBEC9C6),
    surfaceContainerLowest = Color(0xFF090F0E), surfaceContainerLow = Color(0xFF161D1C), surfaceContainer = Color(0xFF1A2120),
    surfaceContainerHigh = Color(0xFF252B2A), surfaceContainerHighest = Color(0xFF303635),
    outline = Color(0xFF899390), outlineVariant = Color(0xFF3F4947),
)

/** Background and text colours of a reading surface. The tinted ones use dark grey on paper, never pure black on white. */
data class ReaderColors(val background: Color, val text: Color, val muted: Color, val highlight: Color)

@Composable
fun ReaderSurface.colors(): ReaderColors = when (this) {
    ReaderSurface.Default -> with(MaterialTheme.colorScheme) {
        ReaderColors(surfaceContainer, onSurface, onSurfaceVariant, primaryContainer)
    }
    ReaderSurface.Cream -> ReaderColors(Color(0xFFFBF3E0), Color(0xFF2B2A26), Color(0xFF6E6A5E), Color(0xFFF5D98B))
    ReaderSurface.Mint -> ReaderColors(Color(0xFFE6F4EE), Color(0xFF1F2B27), Color(0xFF5B6B65), Color(0xFFB4E3D2))
    ReaderSurface.Paper -> ReaderColors(Color(0xFFF7F7F5), Color(0xFF242424), Color(0xFF666666), Color(0xFFD7E6F7))
    ReaderSurface.Night -> ReaderColors(Color(0xFF1E2221), Color(0xFFE6E2D8), Color(0xFFA6A198), Color(0xFF4A4428))
}
