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
