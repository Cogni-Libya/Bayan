package ai.bayan.android

import android.content.Intent
import android.graphics.Color
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.SystemBarStyle
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.lifecycleScope
import ai.bayan.android.data.Settings
import ai.bayan.android.ui.components.LocalAppContainer
import ai.bayan.android.ui.navigation.BayanNavigation
import ai.bayan.android.ui.onboarding.OnboardingScreen
import ai.bayan.android.ui.theme.BayanTheme
import ai.bayan.android.ui.theme.isDark
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {
    /** Text shared into Bayan from another app, waiting for the home screen to pick it up. */
    private val sharedText = MutableStateFlow<String?>(null)

    override fun onCreate(savedInstanceState: Bundle?) {
        val splash = installSplashScreen()
        super.onCreate(savedInstanceState)
        val app = (application as BayanApp).container
        val settings: StateFlow<Settings?> = app.settings.settings.stateIn(lifecycleScope, SharingStarted.Eagerly, null)
        splash.setKeepOnScreenCondition { settings.value == null }
        // The sunrise plays to the end, then the splash gives way: the logo lifts a little and fades as the paper
        // dissolves into the app (after Google AI Edge Gallery's splash exit).
        splash.setOnExitAnimationListener { view ->
            val icon = view.iconView
            // starts while the glow is still settling, so the logo never just sits there
            val left = (view.iconAnimationStartMillis + view.iconAnimationDurationMillis - 280 - System.currentTimeMillis()).coerceIn(0L, 900L)
            view.view.animate().alpha(0f).setStartDelay(left + 60).setDuration(360)
                .setInterpolator(android.view.animation.DecelerateInterpolator())
                .withEndAction { view.remove() }.start()
            icon.animate().translationY(-icon.height * 0.08f).scaleX(0.94f).scaleY(0.94f).alpha(0f)
                .setStartDelay(left).setDuration(460).setInterpolator(android.view.animation.PathInterpolator(0.3f, 0f, 0f, 1f)).start()
        }
        if (savedInstanceState == null) receive(intent)

        setContent {
            val current by settings.collectAsStateWithLifecycle()
            val s = current ?: return@setContent
            val shared by sharedText.collectAsStateWithLifecycle()
            val dark = s.themeMode.isDark()
            DisposableEffect(dark) {
                val style = SystemBarStyle.auto(Color.TRANSPARENT, Color.TRANSPARENT) { dark }
                enableEdgeToEdge(statusBarStyle = style, navigationBarStyle = style)
                onDispose {}
            }
            CompositionLocalProvider(LocalAppContainer provides app) {
                BayanTheme(s.themeMode, s.style) {
                    AnimatedContent(s.onboardingDone, transitionSpec = { fadeIn() togetherWith fadeOut() }, label = "onboarding") { done ->
                        if (done) BayanNavigation(shared, onSharedTextConsumed = { sharedText.value = null })
                        else OnboardingScreen(onFinish = { app.scope.launch { app.settings.setOnboardingDone() } })
                    }
                }
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        receive(intent)
    }

    private fun receive(intent: Intent?) {
        if (intent?.action == Intent.ACTION_SEND && intent.type == "text/plain") {
            intent.getStringExtra(Intent.EXTRA_TEXT)?.takeIf { it.isNotBlank() }?.let { sharedText.value = it }
        }
    }
}
