package ai.bayan.android.engine

import android.content.Context

/**
 * Service locator / factory providing singleton instance of [ModelStore].
 *
 * Allows dependency injection and replacement for unit and Robolectric tests.
 */
object ModelStoreProvider {

    @Volatile
    private var instance: ModelStore? = null

    /**
     * Obtains the active [ModelStore] instance.
     */
    fun getInstance(context: Context): ModelStore {
        return instance ?: synchronized(this) {
            instance ?: DefaultModelStore(context.applicationContext).also { instance = it }
        }
    }

    /**
     * Injects a custom [ModelStore] (useful for testing or switching store configurations).
     */
    fun setInstance(store: ModelStore) {
        synchronized(this) {
            instance = store
        }
    }

    /**
     * Resets to default instance.
     */
    fun reset() {
        synchronized(this) {
            instance = null
        }
    }
}
