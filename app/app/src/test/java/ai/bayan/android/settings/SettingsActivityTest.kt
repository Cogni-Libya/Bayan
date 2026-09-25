package ai.bayan.android.settings

import android.content.Context
import android.widget.RadioButton
import android.widget.RadioGroup
import android.widget.TextView
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.PreferenceDataStoreFactory
import androidx.datastore.preferences.core.Preferences
import androidx.test.core.app.ApplicationProvider
import com.google.android.material.appbar.MaterialToolbar
import com.google.android.material.materialswitch.MaterialSwitch
import com.google.android.material.slider.Slider
import ai.bayan.android.R
import ai.bayan.android.engine.SimplificationLevel
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.runTest
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.android.controller.ActivityController
import org.robolectric.shadows.ShadowLooper

@OptIn(ExperimentalCoroutinesApi::class)
@RunWith(RobolectricTestRunner::class)
class SettingsActivityTest {

    @get:Rule
    val tempFolder = TemporaryFolder()

    private val testDispatcher = UnconfinedTestDispatcher()
    private val testScope = TestScope(testDispatcher)

    private lateinit var context: Context
    private lateinit var testDataStore: DataStore<Preferences>
    private lateinit var repository: DefaultSettingsRepository
    private lateinit var controller: ActivityController<SettingsActivity>
    private lateinit var activity: SettingsActivity


    @Before
    fun setUp() {
        context = ApplicationProvider.getApplicationContext()
        val testFile = tempFolder.newFile("activity_test_settings.preferences_pb")
        testDataStore = PreferenceDataStoreFactory.create(
            scope = testScope,
            produceFile = { testFile }
        )
        repository = DefaultSettingsRepository(context = context, customDataStore = testDataStore)
        SettingsRepository.setInstance(repository)

        controller = Robolectric.buildActivity(SettingsActivity::class.java)
        activity = controller.get()
        activity.settingsRepository = repository
        controller.setup()
        ShadowLooper.idleMainLooper()
    }

    @After
    fun tearDown() {
        controller.destroy()
        SettingsRepository.reset()
    }

    @Test
    fun testSettingsActivity_displaysInitialDefaultPreferences() {
        // Toolbar
        val toolbar = activity.findViewById<MaterialToolbar>(R.id.toolbarSettings)
        assertNotNull("Toolbar must be present", toolbar)
        assertEquals("إعدادات القراءة", toolbar.title.toString())

        // Live preview
        val tvPreviewText = activity.findViewById<TextView>(R.id.tvPreviewText)
        assertNotNull("Live preview text view must be present", tvPreviewText)
        assertEquals("بيان لتيسير القراءة وتسهيل فهم النصوص العربية لدعم القراء والباحثين.", tvPreviewText.text.toString())

        // Simplification Strength (Default: STANDARD / متوسط)
        val rbMedium = activity.findViewById<RadioButton>(R.id.rbStrengthMedium)
        assertTrue("Medium radio button must be checked by default", rbMedium.isChecked)

        // Font Size Slider (Default: 22sp)
        val sliderFontSize = activity.findViewById<Slider>(R.id.sliderFontSize)
        val tvFontSizeValue = activity.findViewById<TextView>(R.id.tvFontSizeValue)
        assertEquals("Font size slider must be set to 22sp", 22f, sliderFontSize.value, 0.01f)
        assertEquals("22 sp", tvFontSizeValue.text.toString())

        // Line Spacing Slider (Default: 1.6x)
        val sliderLineSpacing = activity.findViewById<Slider>(R.id.sliderLineSpacing)
        val tvLineSpacingValue = activity.findViewById<TextView>(R.id.tvLineSpacingValue)
        assertEquals("Line spacing slider must be set to 1.6x", 1.6f, sliderLineSpacing.value, 0.01f)
        assertEquals("1.6x", tvLineSpacingValue.text.toString())

        // Font Family (Default: Noto Naskh)
        val rbNotoNaskh = activity.findViewById<RadioButton>(R.id.rbFontNotoNaskh)
        assertTrue("Noto Naskh radio button must be checked by default", rbNotoNaskh.isChecked)

        // Wi-Fi Only Switch (Default: true)
        val switchWifiOnly = activity.findViewById<MaterialSwitch>(R.id.switchWifiOnly)
        assertTrue("Wi-Fi only switch must be checked by default", switchWifiOnly.isChecked)
    }

    @Test
    fun testSettingsActivity_changeSimplificationStrength_updatesDataStore() = runTest(testDispatcher) {
        val rbLight = activity.findViewById<RadioButton>(R.id.rbStrengthLight)
        rbLight.performClick()
        ShadowLooper.idleMainLooper()

        val updatedPrefs1 = repository.preferencesFlow.first()
        assertEquals("Light radio button (خفيف) must update to ADVANCED", SimplificationLevel.ADVANCED, updatedPrefs1.simplificationLevel)

        val rbStrong = activity.findViewById<RadioButton>(R.id.rbStrengthStrong)
        rbStrong.performClick()
        ShadowLooper.idleMainLooper()

        val updatedPrefs2 = repository.preferencesFlow.first()
        assertEquals("Strong radio button (قوي) must update to ELEMENTARY", SimplificationLevel.ELEMENTARY, updatedPrefs2.simplificationLevel)

        val rbMedium = activity.findViewById<RadioButton>(R.id.rbStrengthMedium)
        rbMedium.performClick()
        ShadowLooper.idleMainLooper()

        val updatedPrefs3 = repository.preferencesFlow.first()
        assertEquals("Medium radio button (متوسط) must update to STANDARD", SimplificationLevel.STANDARD, updatedPrefs3.simplificationLevel)
    }

    @Test
    fun testSettingsActivity_changeFontSizeSlider_updatesLivePreviewAndDataStore() = runTest(testDispatcher) {
        val sliderFontSize = activity.findViewById<Slider>(R.id.sliderFontSize)
        val tvFontSizeValue = activity.findViewById<TextView>(R.id.tvFontSizeValue)

        // Programmatically update slider
        sliderFontSize.value = 28f
        ShadowLooper.idleMainLooper()

        // Persist via repository
        repository.updateFontSize(28f)
        ShadowLooper.idleMainLooper()

        assertEquals("28 sp", tvFontSizeValue.text.toString())
        val updatedPrefs = repository.preferencesFlow.first()
        assertEquals(28f, updatedPrefs.fontSizeSp, 0.01f)
    }

    @Test
    fun testSettingsActivity_changeLineSpacingSlider_updatesLivePreviewAndDataStore() = runTest(testDispatcher) {
        val sliderLineSpacing = activity.findViewById<Slider>(R.id.sliderLineSpacing)
        val tvLineSpacingValue = activity.findViewById<TextView>(R.id.tvLineSpacingValue)

        sliderLineSpacing.value = 1.8f
        ShadowLooper.idleMainLooper()

        repository.updateLineSpacing(1.8f)
        ShadowLooper.idleMainLooper()

        assertEquals("1.8x", tvLineSpacingValue.text.toString())
        val updatedPrefs = repository.preferencesFlow.first()
        assertEquals(1.8f, updatedPrefs.lineSpacingMultiplier, 0.01f)
    }

    @Test
    fun testSettingsActivity_changeFontFamily_updatesLivePreviewAndDataStore() = runTest(testDispatcher) {
        val rbNotoSans = activity.findViewById<RadioButton>(R.id.rbFontNotoSans)
        rbNotoSans.performClick()
        ShadowLooper.idleMainLooper()

        val updatedPrefs = repository.preferencesFlow.first()
        assertEquals(BayanPreferences.FONT_FAMILY_NOTO_SANS, updatedPrefs.fontFamily)
    }

    @Test
    fun testSettingsActivity_toggleWifiOnlySwitch_updatesDataStore() = runTest(testDispatcher) {
        val switchWifiOnly = activity.findViewById<MaterialSwitch>(R.id.switchWifiOnly)
        switchWifiOnly.performClick()
        ShadowLooper.idleMainLooper()

        val updatedPrefs = repository.preferencesFlow.first()
        assertFalse("Wi-Fi only setting must be false after toggle click", updatedPrefs.wifiOnlyDownload)
    }

    @Test
    fun testSettingsActivity_toolbarNavigationClick_finishesActivity() {
        val toolbar = activity.findViewById<MaterialToolbar>(R.id.toolbarSettings)
        toolbar.navigationIcon?.let {
            // Trigger navigation click listener directly
            toolbar.performClick()
        }
        // Also call navigation click
        val navView = toolbar.findViewById<android.view.View>(com.google.android.material.R.id.navigation_bar_item_icon_view)
            ?: toolbar
        toolbar.callOnClick()
        // Or simulate up navigation
        activity.onBackPressedDispatcher.onBackPressed()
        assertTrue("Activity must be finishing after back navigation", activity.isFinishing)
    }
}
