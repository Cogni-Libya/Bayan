package ai.bayan.android

import android.app.Application
import android.content.ComponentCallbacks2
import ai.bayan.android.data.HistoryRepository
import ai.bayan.android.data.SettingsRepository
import ai.bayan.android.engine.Diacritizer
import ai.bayan.android.engine.Simplifier
import ai.bayan.android.model.ModelStore
import ai.bayan.android.speech.ReadAloud
import ai.bayan.android.ui.process.OverlaySession
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

/** The app's single object graph; screens reach it through [BayanApp.container]. */
class AppContainer(app: Application) {
    val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    val settings = SettingsRepository(app)
    val history = HistoryRepository(app)
    val modelStore = ModelStore(app)
    val simplifier = Simplifier(modelStore) {
        Diacritizer(app.assets.open("tashkeel/libtashkeel.onnx").use { it.readBytes() },
                    app.assets.open("tashkeel/libtashkeel.maps.json").bufferedReader().use { it.readText() })
    }
    val readAloud = ReadAloud(app, scope, settings, modelStore)
    /** The "تبسيط" panel's simplification and reading, which outlive the panel when it is minimized. */
    val overlay = OverlaySession(this, scope)
}

class BayanApp : Application() {
    lateinit var container: AppContainer
        private set

    override fun onCreate() {
        super.onCreate()
        container = AppContainer(this)
        container.scope.launch { container.history.load() }
    }

    override fun onTrimMemory(level: Int) {
        super.onTrimMemory(level)
        @Suppress("DEPRECATION")
        if (level >= ComponentCallbacks2.TRIM_MEMORY_BACKGROUND) {
            container.simplifier.releaseIfIdle()
            container.readAloud.releaseIfIdle()
        }
    }
}
