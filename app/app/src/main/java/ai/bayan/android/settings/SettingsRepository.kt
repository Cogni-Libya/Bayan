package ai.bayan.android.settings

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.emptyPreferences
import androidx.datastore.preferences.core.floatPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import ai.bayan.android.engine.SimplificationLevel
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.flow.map
import java.io.IOException

val Context.bayanDataStore: DataStore<Preferences> by preferencesDataStore(name = "bayan_settings")

/**
 * Interface contract for persisting and observing user reading accessibility preferences.
 */
interface SettingsRepository {

    val preferencesFlow: Flow<BayanPreferences>

    suspend fun updateSimplificationLevel(level: SimplificationLevel)
    suspend fun updateFontSize(fontSizeSp: Float)
    suspend fun updateLineSpacing(multiplier: Float)
    suspend fun updateFontFamily(fontFamily: String)
    suspend fun updateWifiOnlyDownload(wifiOnly: Boolean)

    companion object {
        val KEY_SIMPLIFICATION_LEVEL = stringPreferencesKey("simplification_level")
        val KEY_SIMPLIFICATION_STRENGTH = stringPreferencesKey("simplification_strength")
        val KEY_FONT_SIZE = floatPreferencesKey("font_size_sp")
        val KEY_LINE_SPACING = floatPreferencesKey("line_spacing_multiplier")
        val KEY_FONT_FAMILY = stringPreferencesKey("font_family")
        val KEY_WIFI_ONLY = booleanPreferencesKey("wifi_only_download")

        @Volatile
        private var instance: SettingsRepository? = null

        fun getInstance(context: Context): SettingsRepository {
            return instance ?: synchronized(this) {
                instance ?: DefaultSettingsRepository(context.applicationContext).also { instance = it }
            }
        }

        fun setInstance(repository: SettingsRepository) {
            instance = repository
        }

        fun reset() {
            instance = null
        }

        operator fun invoke(context: Context): SettingsRepository = getInstance(context)
    }
}

/**
 * Jetpack DataStore Preferences implementation of [SettingsRepository].
 */
open class DefaultSettingsRepository(
    private val context: Context? = null,
    private val customDataStore: DataStore<Preferences>? = null
) : SettingsRepository {

    private val dataStore: DataStore<Preferences>
        get() = customDataStore ?: checkNotNull(context?.bayanDataStore) {
            "A non-null Context or custom DataStore<Preferences> must be provided."
        }

    override val preferencesFlow: Flow<BayanPreferences> = dataStore.data
        .catch { exception ->
            if (exception is IOException) {
                emit(emptyPreferences())
            } else {
                throw exception
            }
        }
        .map { preferences ->
            val levelStr = preferences[SettingsRepository.KEY_SIMPLIFICATION_LEVEL]
                ?: preferences[SettingsRepository.KEY_SIMPLIFICATION_STRENGTH]
                ?: SimplificationLevel.STANDARD.name

            val level = try {
                when (levelStr.uppercase()) {
                    "LIGHT" -> SimplificationLevel.ADVANCED
                    "STRONG" -> SimplificationLevel.ELEMENTARY
                    "MEDIUM" -> SimplificationLevel.STANDARD
                    else -> SimplificationLevel.valueOf(levelStr)
                }
            } catch (e: IllegalArgumentException) {
                SimplificationLevel.STANDARD
            }

            val fontSize = (preferences[SettingsRepository.KEY_FONT_SIZE] ?: BayanPreferences.DEFAULT_FONT_SIZE_SP)
                .coerceIn(BayanPreferences.MIN_FONT_SIZE_SP, BayanPreferences.MAX_FONT_SIZE_SP)

            val lineSpacing = (preferences[SettingsRepository.KEY_LINE_SPACING] ?: BayanPreferences.DEFAULT_LINE_SPACING_MULTIPLIER)
                .coerceIn(BayanPreferences.MIN_LINE_SPACING_MULTIPLIER, BayanPreferences.MAX_LINE_SPACING_MULTIPLIER)

            val fontFamily = preferences[SettingsRepository.KEY_FONT_FAMILY]
                ?.takeIf { it == BayanPreferences.FONT_FAMILY_NOTO_NASKH || it == BayanPreferences.FONT_FAMILY_NOTO_SANS }
                ?: BayanPreferences.DEFAULT_FONT_FAMILY

            val wifiOnly = preferences[SettingsRepository.KEY_WIFI_ONLY] ?: BayanPreferences.DEFAULT_WIFI_ONLY_DOWNLOAD

            BayanPreferences(
                simplificationLevel = level,
                fontSizeSp = fontSize,
                lineSpacingMultiplier = lineSpacing,
                fontFamily = fontFamily,
                wifiOnlyDownload = wifiOnly
            )
        }

    override suspend fun updateSimplificationLevel(level: SimplificationLevel) {
        dataStore.edit { preferences ->
            preferences[SettingsRepository.KEY_SIMPLIFICATION_LEVEL] = level.name
            preferences[SettingsRepository.KEY_SIMPLIFICATION_STRENGTH] = level.name
        }
    }

    override suspend fun updateFontSize(fontSizeSp: Float) {
        val clamped = fontSizeSp.coerceIn(BayanPreferences.MIN_FONT_SIZE_SP, BayanPreferences.MAX_FONT_SIZE_SP)
        dataStore.edit { preferences ->
            preferences[SettingsRepository.KEY_FONT_SIZE] = clamped
        }
    }

    override suspend fun updateLineSpacing(multiplier: Float) {
        val clamped = multiplier.coerceIn(BayanPreferences.MIN_LINE_SPACING_MULTIPLIER, BayanPreferences.MAX_LINE_SPACING_MULTIPLIER)
        dataStore.edit { preferences ->
            preferences[SettingsRepository.KEY_LINE_SPACING] = clamped
        }
    }

    override suspend fun updateFontFamily(fontFamily: String) {
        val validatedFamily = if (fontFamily == BayanPreferences.FONT_FAMILY_NOTO_SANS) {
            BayanPreferences.FONT_FAMILY_NOTO_SANS
        } else {
            BayanPreferences.FONT_FAMILY_NOTO_NASKH
        }
        dataStore.edit { preferences ->
            preferences[SettingsRepository.KEY_FONT_FAMILY] = validatedFamily
        }
    }

    override suspend fun updateWifiOnlyDownload(wifiOnly: Boolean) {
        dataStore.edit { preferences ->
            preferences[SettingsRepository.KEY_WIFI_ONLY] = wifiOnly
        }
    }
}
