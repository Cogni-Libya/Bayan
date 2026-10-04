package ai.bayan.android.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Shapes
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

/**
 * Bayan's own colours, from its design system: ink on warm paper (never pure black on white), the ochre of the logo's
 * sun as the accent, olive / brick / slate for success / error / information. Dark mode is the night ground with
 * cream ink and the same sun.
 */
val BayanLight = lightColorScheme(
    primary = Color(0xFF8A5E35), onPrimary = Color(0xFFFBF8F0),                      // ochre-700 (accent text, filled)
    primaryContainer = Color(0xFFEEDDC7), onPrimaryContainer = Color(0xFF3B2814),     // ochre-100
    inversePrimary = Color(0xFFDDBB95),
    secondary = Color(0xFF6F6B5E), onSecondary = Color(0xFFFBF8F0),                  // ink-3
    secondaryContainer = Color(0xFFE6DFCC), onSecondaryContainer = Color(0xFF282824), // paper-3
    tertiary = Color(0xFF5B7447), onTertiary = Color(0xFFFBF8F0),                    // olive-600
    tertiaryContainer = Color(0xFFE9EDDC), onTertiaryContainer = Color(0xFF232A1C),
    error = Color(0xFFA2463A), onError = Color(0xFFFBF8F0),                          // brick-600
    errorContainer = Color(0xFFF4E1DA), onErrorContainer = Color(0xFF5C221A),
    background = Color(0xFFF6F2E6), onBackground = Color(0xFF282824),                // paper-1 / ink-1
    surface = Color(0xFFF6F2E6), onSurface = Color(0xFF282824),
    surfaceVariant = Color(0xFFEFE9D9), onSurfaceVariant = Color(0xFF4A4842),        // paper-2 / ink-2
    surfaceTint = Color(0xFF8A5E35),
    inverseSurface = Color(0xFF282824), inverseOnSurface = Color(0xFFF6F2E6),
    outline = Color(0xFFA29D8C), outlineVariant = Color(0xFFDCD4BF),                 // ink-4 / paper-4
    scrim = Color(0xFF282824),
    surfaceBright = Color(0xFFFBF8F0), surfaceDim = Color(0xFFE6DFCC),
    surfaceContainerLowest = Color(0xFFFBF8F0), surfaceContainerLow = Color(0xFFF3EEE0),
    surfaceContainer = Color(0xFFEFE9D9), surfaceContainerHigh = Color(0xFFEAE3D2), surfaceContainerHighest = Color(0xFFE6DFCC),
)

val BayanDark = darkColorScheme(
    primary = Color(0xFFDDBB95), onPrimary = Color(0xFF3B2814),                      // ochre-700 (dark)
    primaryContainer = Color(0xFF3E3222), onPrimaryContainer = Color(0xFFEEDDC7),
    inversePrimary = Color(0xFF8A5E35),
    secondary = Color(0xFFA19D8E), onSecondary = Color(0xFF1A1A14),
    secondaryContainer = Color(0xFF302F27), onSecondaryContainer = Color(0xFFF2EFE2),
    tertiary = Color(0xFF9DB585), onTertiary = Color(0xFF1A1A14),
    tertiaryContainer = Color(0xFF232A1C), onTertiaryContainer = Color(0xFFE9EDDC),
    error = Color(0xFFD98A7E), onError = Color(0xFF1A1A14),
    errorContainer = Color(0xFF33201B), onErrorContainer = Color(0xFFF4E1DA),
    background = Color(0xFF1A1A14), onBackground = Color(0xFFF2EFE2),                // night / cream
    surface = Color(0xFF1A1A14), onSurface = Color(0xFFF2EFE2),
    surfaceVariant = Color(0xFF26261E), onSurfaceVariant = Color(0xFFD2CEBF),
    surfaceTint = Color(0xFFDDBB95),
    inverseSurface = Color(0xFFF2EFE2), inverseOnSurface = Color(0xFF1A1A14),
    outline = Color(0xFF6C695E), outlineVariant = Color(0xFF3D3C33),
    scrim = Color(0xFF000000),
    surfaceBright = Color(0xFF302F27), surfaceDim = Color(0xFF15150F),
    surfaceContainerLowest = Color(0xFF15150F), surfaceContainerLow = Color(0xFF212119),
    surfaceContainer = Color(0xFF26261E), surfaceContainerHigh = Color(0xFF2B2A22), surfaceContainerHighest = Color(0xFF302F27),
)

/** Bayan's corner radii (design system: 6 / 10 / 16 / 24 px). */
val BayanShapes = Shapes(
    extraSmall = RoundedCornerShape(6.dp), small = RoundedCornerShape(10.dp), medium = RoundedCornerShape(16.dp),
    large = RoundedCornerShape(24.dp), extraLarge = RoundedCornerShape(28.dp),
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
