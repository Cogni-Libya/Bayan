package ai.bayan.android.settings

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.PreferenceDataStoreFactory
import androidx.datastore.preferences.core.Preferences
import androidx.test.core.app.ApplicationProvider
import ai.bayan.android.engine.SimplificationLevel
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.runTest
import org.junit.Assert.*
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import java.io.File

@OptIn(ExperimentalCoroutinesApi::class)
@RunWith(RobolectricTestRunner::class)
class SettingsRepositoryTest {

    @get:Rule
    val tempFolder = TemporaryFolder()

    private val testDispatcher = UnconfinedTestDispatcher()
    private val testScope = TestScope(testDispatcher)

    private lateinit var testDataStore: DataStore<Preferences>
    private lateinit var repository: DefaultSettingsRepository
    private lateinit var context: Context

    @Before
    fun setUp() {
        context = ApplicationProvider.getApplicationContext()
        val testFile = tempFolder.newFile("test_settings.preferences_pb")
        testDataStore = PreferenceDataStoreFactory.create(
            scope = testScope,
            produceFile = { testFile }
        )
        repository = DefaultSettingsRepository(context = context, customDataStore = testDataStore)
        SettingsRepository.reset()
    }

    @Test
    fun testDefaultPreferences_matchesSpecification() = runTest(testDispatcher) {
        val prefs = repository.preferencesFlow.first()

        assertEquals("Default simplification level must be STANDARD", SimplificationLevel.STANDARD, prefs.simplificationLevel)
        assertEquals("Default font size must be 22sp", BayanPreferences.DEFAULT_FONT_SIZE_SP, prefs.fontSizeSp, 0.01f)
        assertEquals("Default line spacing multiplier must be 1.6x", BayanPreferences.DEFAULT_LINE_SPACING_MULTIPLIER, prefs.lineSpacingMultiplier, 0.01f)
        assertEquals("Default font family must be Noto Naskh Arabic", BayanPreferences.DEFAULT_FONT_FAMILY, prefs.fontFamily)
        assertEquals("Default Wi-Fi only download must be true", BayanPreferences.DEFAULT_WIFI_ONLY_DOWNLOAD, prefs.wifiOnlyDownload)
    }

    @Test
    fun testUpdateSimplificationLevel_persistsAndEmits() = runTest(testDispatcher) {
        repository.updateSimplificationLevel(SimplificationLevel.ADVANCED)
        val advancedPrefs = repository.preferencesFlow.first()
        assertEquals(SimplificationLevel.ADVANCED, advancedPrefs.simplificationLevel)

        repository.updateSimplificationLevel(SimplificationLevel.ELEMENTARY)
        val elementaryPrefs = repository.preferencesFlow.first()
        assertEquals(SimplificationLevel.ELEMENTARY, elementaryPrefs.simplificationLevel)

        repository.updateSimplificationLevel(SimplificationLevel.STANDARD)
        val standardPrefs = repository.preferencesFlow.first()
        assertEquals(SimplificationLevel.STANDARD, standardPrefs.simplificationLevel)
    }

    @Test
    fun testUpdateFontSize_persistsAndClampsToBounds() = runTest(testDispatcher) {
        // Valid range update
        repository.updateFontSize(26f)
        assertEquals(26f, repository.preferencesFlow.first().fontSizeSp, 0.01f)

        repository.updateFontSize(18f)
        assertEquals(18f, repository.preferencesFlow.first().fontSizeSp, 0.01f)

        repository.updateFontSize(32f)
        assertEquals(32f, repository.preferencesFlow.first().fontSizeSp, 0.01f)

        // Clamping below minimum (18sp)
        repository.updateFontSize(10f)
        assertEquals("Values below 18sp must clamp to 18sp", BayanPreferences.MIN_FONT_SIZE_SP, repository.preferencesFlow.first().fontSizeSp, 0.01f)

        // Clamping above maximum (32sp)
        repository.updateFontSize(45f)
        assertEquals("Values above 32sp must clamp to 32sp", BayanPreferences.MAX_FONT_SIZE_SP, repository.preferencesFlow.first().fontSizeSp, 0.01f)
    }

    @Test
    fun testUpdateLineSpacing_persistsAndClampsToBounds() = runTest(testDispatcher) {
        // Valid range update
        repository.updateLineSpacing(1.8f)
        assertEquals(1.8f, repository.preferencesFlow.first().lineSpacingMultiplier, 0.01f)

        repository.updateLineSpacing(1.2f)
        assertEquals(1.2f, repository.preferencesFlow.first().lineSpacingMultiplier, 0.01f)

        repository.updateLineSpacing(2.0f)
        assertEquals(2.0f, repository.preferencesFlow.first().lineSpacingMultiplier, 0.01f)

        // Clamping below minimum (1.2x)
        repository.updateLineSpacing(0.5f)
        assertEquals("Values below 1.2x must clamp to 1.2x", BayanPreferences.MIN_LINE_SPACING_MULTIPLIER, repository.preferencesFlow.first().lineSpacingMultiplier, 0.01f)

        // Clamping above maximum (2.0x)
        repository.updateLineSpacing(3.5f)
        assertEquals("Values above 2.0x must clamp to 2.0x", BayanPreferences.MAX_LINE_SPACING_MULTIPLIER, repository.preferencesFlow.first().lineSpacingMultiplier, 0.01f)
    }

    @Test
    fun testUpdateFontFamily_persistsSelection() = runTest(testDispatcher) {
        repository.updateFontFamily(BayanPreferences.FONT_FAMILY_NOTO_SANS)
        assertEquals("Noto Sans Arabic", repository.preferencesFlow.first().fontFamily)

        repository.updateFontFamily(BayanPreferences.FONT_FAMILY_NOTO_NASKH)
        assertEquals("Noto Naskh Arabic", repository.preferencesFlow.first().fontFamily)

        // Invalid font family must fall back to default
        repository.updateFontFamily("UnknownCustomFont")
        assertEquals(BayanPreferences.DEFAULT_FONT_FAMILY, repository.preferencesFlow.first().fontFamily)
    }

    @Test
    fun testUpdateWifiOnlyDownload_persistsFlag() = runTest(testDispatcher) {
        repository.updateWifiOnlyDownload(false)
        assertFalse("Wi-Fi only download flag must be false after update", repository.preferencesFlow.first().wifiOnlyDownload)

        repository.updateWifiOnlyDownload(true)
        assertTrue("Wi-Fi only download flag must be true after update", repository.preferencesFlow.first().wifiOnlyDownload)
    }

    @Test
    fun testPersistenceAcrossRepositoryInstances() = runTest(testDispatcher) {
        // Modify preferences on first instance
        repository.updateSimplificationLevel(SimplificationLevel.ADVANCED)
        repository.updateFontSize(28f)
        repository.updateLineSpacing(1.9f)
        repository.updateFontFamily(BayanPreferences.FONT_FAMILY_NOTO_SANS)
        repository.updateWifiOnlyDownload(false)

        // Create second repository instance backed by the same DataStore
        val secondRepository = DefaultSettingsRepository(context = context, customDataStore = testDataStore)
        val loadedPrefs = secondRepository.preferencesFlow.first()

        assertEquals(SimplificationLevel.ADVANCED, loadedPrefs.simplificationLevel)
        assertEquals(28f, loadedPrefs.fontSizeSp, 0.01f)
        assertEquals(1.9f, loadedPrefs.lineSpacingMultiplier, 0.01f)
        assertEquals(BayanPreferences.FONT_FAMILY_NOTO_SANS, loadedPrefs.fontFamily)
        assertFalse(loadedPrefs.wifiOnlyDownload)
    }

    @Test
    fun testSettingsRepository_singletonAccessAndOverride() {
        val repo1 = SettingsRepository.getInstance(context)
        val repo2 = SettingsRepository.getInstance(context)
        assertSame("getInstance must return singleton instance", repo1, repo2)

        SettingsRepository.setInstance(repository)
        assertSame("setInstance must override active singleton instance", repository, SettingsRepository.getInstance(context))

        SettingsRepository.reset()
        val repoAfterReset = SettingsRepository.getInstance(context)
        assertNotSame("reset must clear previously injected singleton instance", repository, repoAfterReset)
    }
}
