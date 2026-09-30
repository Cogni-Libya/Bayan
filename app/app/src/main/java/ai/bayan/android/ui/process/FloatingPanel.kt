package ai.bayan.android.ui.process

import android.content.Context
import android.graphics.PixelFormat
import android.os.Build
import android.view.Gravity
import android.view.WindowInsets
import android.view.WindowManager
import androidx.compose.runtime.Composable
import androidx.compose.ui.platform.ComposeView
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.LifecycleRegistry
import androidx.lifecycle.setViewTreeLifecycleOwner
import androidx.savedstate.SavedStateRegistry
import androidx.savedstate.SavedStateRegistryController
import androidx.savedstate.SavedStateRegistryOwner
import androidx.savedstate.setViewTreeSavedStateRegistryOwner

/**
 * A small window that floats over whatever app is on screen ("Display over other apps"), for the minimized
 * "تبسيط" panel: the app underneath stays fully usable while Bayan keeps reading.
 */
class FloatingPanel(private val context: Context) {
    private val windows = context.getSystemService(WindowManager::class.java)
    private val owner = WindowOwner()
    private var view: ComposeView? = null
    private val params = WindowManager.LayoutParams(
        WindowManager.LayoutParams.MATCH_PARENT,
        WindowManager.LayoutParams.WRAP_CONTENT,
        WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
        WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL,
        PixelFormat.TRANSLUCENT,
    ).apply {
        gravity = Gravity.BOTTOM
        y = bottomInset()
    }

    val isShown: Boolean get() = view != null

    fun show(content: @Composable (move: (Float) -> Unit) -> Unit) {
        if (view != null) return
        owner.start()
        val v = ComposeView(context).apply {
            setViewTreeLifecycleOwner(owner)
            setViewTreeSavedStateRegistryOwner(owner)
            setContent { content(::moveBy) }
        }
        windows.addView(v, params)
        view = v
    }

    /** Drags the panel up or down the screen; [dy] is in pixels, positive downwards. */
    private fun moveBy(dy: Float) {
        val v = view ?: return
        val max = context.resources.displayMetrics.heightPixels - v.height - bottomInset()
        params.y = (params.y - dy.toInt()).coerceIn(bottomInset(), maxOf(bottomInset(), max))
        windows.updateViewLayout(v, params)
    }

    fun remove() {
        view?.let { runCatching { windows.removeView(it) } }
        view = null
        owner.stop()
    }

    /** Above the navigation bar. */
    private fun bottomInset(): Int =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            windows.currentWindowMetrics.windowInsets.getInsets(WindowInsets.Type.navigationBars()).bottom
        } else {
            (48 * context.resources.displayMetrics.density).toInt()
        }

    /** Compose needs a lifecycle and saved state, which a window owned by a service does not have by itself. */
    private class WindowOwner : LifecycleOwner, SavedStateRegistryOwner {
        private val registry = LifecycleRegistry(this)
        private val saved = SavedStateRegistryController.create(this)
        override val lifecycle: Lifecycle get() = registry
        override val savedStateRegistry: SavedStateRegistry get() = saved.savedStateRegistry
        fun start() {
            if (registry.currentState == Lifecycle.State.INITIALIZED) saved.performRestore(null)
            registry.currentState = Lifecycle.State.RESUMED
        }
        fun stop() {
            if (registry.currentState != Lifecycle.State.INITIALIZED) registry.currentState = Lifecycle.State.DESTROYED
        }
    }
}
