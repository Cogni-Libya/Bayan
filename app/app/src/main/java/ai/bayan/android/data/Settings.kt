package ai.bayan.android.data

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.floatPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import ai.bayan.android.model.ModelCatalog
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

enum class ThemeMode { System, Light, Dark }

/**
 * The app's look: [Bayan] is Bayan's own design system (warm paper and ink, the ochre of the logo's sun, Readex Pro);
 * [System] takes the phone's Material You colours from the wallpaper and the system font.
 */
enum class AppStyle { Bayan, System }

/** [Readex] is Readex Pro (Lexend's reading-fluency design, for Arabic); [Naskh] the bundled book style; [System] the phone's own font. */
enum class ReaderFont { Readex, Naskh, System }

/**
 * Where simplified text is shown. [Default] follows the system theme; the others are tinted, low-glare
 * backgrounds recommended for readers with dyslexia (BDA style guide), offered as accessibility options.
 */
enum class ReaderSurface { Default, Cream, Mint, Paper, Night }

data class ReaderStyle(
    val font: ReaderFont = ReaderFont.Readex,
    val sizeSp: Float = 22f,
    val lineHeight: Float = 1.8f,
    val wordSpacing: Float = 0.12f,
    val surface: ReaderSurface = ReaderSurface.Default,
)

data class Settings(
    val onboardingDone: Boolean = false,
    val themeMode: ThemeMode = ThemeMode.System,
    val style: AppStyle = AppStyle.Bayan,
    val activeModel: String = ModelCatalog.DEFAULT_ID,
    val reader: ReaderStyle = ReaderStyle(),
    val speechRate: Float = 0.9f,
    val voice: String = ai.bayan.android.speech.VoiceCatalog.DEFAULT_ID,
    /** Start reading aloud as soon as the first simplified sentence is ready. */
    val autoRead: Boolean = false,
    val highlightWhileReading: Boolean = true,
    /** Beam search for models that offer it (ModelInfo.beams): keeps the meaning more often, slower, not streamed. On by
     *  default, so the large model (model 3) runs as it was benchmarked. */
    val moreFaithful: Boolean = true,
    /** Short vowels (tashkeel) on the simplified text. Off by default: full marks can crowd a line for some readers. */
    val tashkeel: Boolean = false,
    val wifiOnly: Boolean = true,
)

private val Context.dataStore: DataStore<Preferences> by preferencesDataStore("settings")

class SettingsRepository(private val context: Context) {
    private object Keys {
        val onboarding = booleanPreferencesKey("onboarding_done")
        val theme = stringPreferencesKey("theme_mode")
        val style = stringPreferencesKey("app_style")
        val model = stringPreferencesKey("active_model")
        val font = stringPreferencesKey("reader_font")
        val size = floatPreferencesKey("reader_size")
        val line = floatPreferencesKey("reader_line_height")
        val word = floatPreferencesKey("reader_word_spacing")
        val surface = stringPreferencesKey("reader_surface")
        val rate = floatPreferencesKey("speech_rate")
        val voice = stringPreferencesKey("voice")
        val autoRead = booleanPreferencesKey("auto_read")
        val highlight = booleanPreferencesKey("highlight_reading")
        val faithful = booleanPreferencesKey("more_faithful")
        val tashkeel = booleanPreferencesKey("tashkeel")
        val wifi = booleanPreferencesKey("wifi_only")
    }

    val settings: Flow<Settings> = context.dataStore.data.map { p ->
        val d = Settings()
        Settings(
            onboardingDone = p[Keys.onboarding] ?: d.onboardingDone,
            themeMode = p[Keys.theme]?.let { runCatching { ThemeMode.valueOf(it) }.getOrNull() } ?: d.themeMode,
            style = p[Keys.style]?.let { runCatching { AppStyle.valueOf(it) }.getOrNull() } ?: d.style,
            activeModel = p[Keys.model] ?: d.activeModel,
            reader = ReaderStyle(
                font = p[Keys.font]?.let { runCatching { ReaderFont.valueOf(it) }.getOrNull() } ?: d.reader.font,
                sizeSp = p[Keys.size] ?: d.reader.sizeSp,
                lineHeight = p[Keys.line] ?: d.reader.lineHeight,
                wordSpacing = p[Keys.word] ?: d.reader.wordSpacing,
                surface = p[Keys.surface]?.let { runCatching { ReaderSurface.valueOf(it) }.getOrNull() } ?: d.reader.surface,
            ),
            speechRate = p[Keys.rate] ?: d.speechRate,
            voice = p[Keys.voice] ?: d.voice,
            autoRead = p[Keys.autoRead] ?: d.autoRead,
            highlightWhileReading = p[Keys.highlight] ?: d.highlightWhileReading,
            moreFaithful = p[Keys.faithful] ?: d.moreFaithful,
            tashkeel = p[Keys.tashkeel] ?: d.tashkeel,
            wifiOnly = p[Keys.wifi] ?: d.wifiOnly,
        )
    }

    suspend fun setOnboardingDone() = context.dataStore.edit { it[Keys.onboarding] = true }
    suspend fun setThemeMode(v: ThemeMode) = context.dataStore.edit { it[Keys.theme] = v.name }
    suspend fun setStyle(v: AppStyle) = context.dataStore.edit { it[Keys.style] = v.name }
    suspend fun setActiveModel(id: String) = context.dataStore.edit { it[Keys.model] = id }
    suspend fun setReaderFont(v: ReaderFont) = context.dataStore.edit { it[Keys.font] = v.name }
    suspend fun setReaderSize(v: Float) = context.dataStore.edit { it[Keys.size] = v }
    suspend fun setLineHeight(v: Float) = context.dataStore.edit { it[Keys.line] = v }
    suspend fun setWordSpacing(v: Float) = context.dataStore.edit { it[Keys.word] = v }
    suspend fun setSurface(v: ReaderSurface) = context.dataStore.edit { it[Keys.surface] = v.name }
    suspend fun setSpeechRate(v: Float) = context.dataStore.edit { it[Keys.rate] = v }
    suspend fun setVoice(id: String) = context.dataStore.edit { it[Keys.voice] = id }
    suspend fun setAutoRead(v: Boolean) = context.dataStore.edit { it[Keys.autoRead] = v }
    suspend fun setHighlight(v: Boolean) = context.dataStore.edit { it[Keys.highlight] = v }
    suspend fun setMoreFaithful(v: Boolean) = context.dataStore.edit { it[Keys.faithful] = v }
    suspend fun setTashkeel(v: Boolean) = context.dataStore.edit { it[Keys.tashkeel] = v }
    suspend fun setWifiOnly(v: Boolean) = context.dataStore.edit { it[Keys.wifi] = v }
}
