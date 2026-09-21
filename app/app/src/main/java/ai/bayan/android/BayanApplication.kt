package ai.bayan.android

import android.app.Application
import ai.bayan.android.engine.SimplifierProvider

/**
 * Base Application class for Bayan Android.
 */
class BayanApplication : Application() {

    override fun onCreate() {
        super.onCreate()
        // Initialize default text simplifier engine
        SimplifierProvider.getInstance()
    }
}

