package ai.bayan.android.ui.theme

import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.ExperimentalMaterial3ExpressiveApi
import androidx.compose.material3.MaterialExpressiveTheme
import androidx.compose.material3.MotionScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.platform.LocalContext
import ai.bayan.android.data.AppStyle
import ai.bayan.android.data.ThemeMode
import androidx.compose.material3.Typography

@Composable
fun ThemeMode.isDark(): Boolean = when (this) {
    ThemeMode.System -> isSystemInDarkTheme()
    ThemeMode.Light -> false
    ThemeMode.Dark -> true
}

/**
 * Two looks, the reader's choice (onboarding, Settings ▸ Style): [AppStyle.Bayan], Bayan's own design system (warm
 * paper and ink, the ochre sun, Readex Pro, its radii); or [AppStyle.System], the phone's Material You colours from
 * the wallpaper (Android 12+) with the system font, so it looks like part of Android. Both keep Material's components
 * and expressive motion.
 */
@OptIn(ExperimentalMaterial3ExpressiveApi::class)
@Composable
fun BayanTheme(themeMode: ThemeMode = ThemeMode.System, style: AppStyle = AppStyle.Bayan, content: @Composable () -> Unit) {
    val dark = themeMode.isDark()
    // One call site for both looks, so switching between them changes colours in place (the screen and its state stay).
    val bayan = style == AppStyle.Bayan
    val context = LocalContext.current
    val colors = when {
        bayan -> if (dark) BayanDark else BayanLight
        Build.VERSION.SDK_INT >= Build.VERSION_CODES.S -> if (dark) dynamicDarkColorScheme(context) else dynamicLightColorScheme(context)
        else -> if (dark) FallbackDark else FallbackLight
    }
    MaterialExpressiveTheme(
        colorScheme = colors,
        typography = if (bayan) BayanTypography else SystemTypography,
        shapes = if (bayan) BayanShapes else SystemShapes,
        motionScheme = MotionScheme.expressive(),
    ) { CompositionLocalProvider(LocalAppStyle provides style, content = content) }
}

/** The look in use, for the few places that draw Bayan's own palette rather than the colour scheme (light, logo). */
val LocalAppStyle = staticCompositionLocalOf { AppStyle.Bayan }

private val BayanTypography = Typography().inReadexPro()
private val SystemTypography = Typography()
private val SystemShapes = androidx.compose.material3.Shapes()
