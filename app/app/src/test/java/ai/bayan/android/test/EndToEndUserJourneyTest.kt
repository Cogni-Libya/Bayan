package ai.bayan.android.test

import android.content.ClipboardManager
import android.content.Context
import android.util.TypedValue
import android.view.View
import android.widget.Button
import android.widget.RadioButton
import android.widget.TextView
import androidx.datastore.preferences.core.PreferenceDataStoreFactory
import androidx.fragment.app.testing.launchFragmentInContainer
import androidx.test.core.app.ApplicationProvider
import androidx.work.ListenableWorker
import androidx.work.WorkManager
import androidx.work.testing.TestListenableWorkerBuilder
import androidx.work.testing.WorkManagerTestInitHelper
import androidx.work.workDataOf
import com.google.android.material.materialswitch.MaterialSwitch
import com.google.android.material.slider.Slider
import ai.bayan.android.R
import ai.bayan.android.download.DownloadModelWorker
import ai.bayan.android.download.ModelDownloadManager
import ai.bayan.android.engine.DefaultModelStore
import ai.bayan.android.engine.MockTextSimplifier
import ai.bayan.android.engine.ModelStoreProvider
import ai.bayan.android.engine.SimplificationLevel
import ai.bayan.android.engine.SimplifierProvider
import ai.bayan.android.settings.BayanPreferences
import ai.bayan.android.settings.DefaultSettingsRepository
import ai.bayan.android.settings.SettingsActivity
import ai.bayan.android.settings.SettingsRepository
import ai.bayan.android.ui.SheetState
import ai.bayan.android.ui.SimplifiedBottomSheetDialogFragment
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.shadows.ShadowLooper
import java.io.File

/**
 * Tier 4 End-to-End User Journey Test Suite for Bayan Android Application (Issue #31).
 *
 * Exercises opaque-box real-world integration flows driving genuine Android components:
 * - Scenario 1: First-Time User Journey (Model not ready -> Sheet shows NeedsModel CTA ->
 *               Download action enqueues WorkManager -> Model ready -> Sheet shows Result ->
 *               Toggle text display -> Copy text to clipboard).
 * - Scenario 2: Network Resume Journey (Interrupted download with partial .part file ->
 *               Resumes from byte offset with HTTP Range -> Verifies SHA-256 -> Reaches Ready).
 * - Scenario 3: Dyslexia Customization Journey (Configures DataStore preferences via SettingsActivity
 *               for strength, font size 28sp, line spacing 1.8x, font family Noto Sans ->
 *               Launches sheet -> Verifies dyslexia styling applied to real TextView).
 * - Scenario 4: Corrupted Model Recovery (Disk contains corrupted model file ->
 *               Detection triggers deletion -> Recovers by re-downloading via DownloadModelWorker).
 * - Scenario 5: Error Resilience Journey (Simplification engine error ->
 *               Sheet transitions to Error state -> Preserves readable original text).
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class EndToEndUserJourneyTest {

    @get:Rule
    val tempFolder = TemporaryFolder()

    private lateinit var context: Context
    private lateinit var testServer: TestHttpRangeServer
    private lateinit var customModelDir: File
    private lateinit var settingsRepository: DefaultSettingsRepository

    @Before
    fun setUp() {
        context = ApplicationProvider.getApplicationContext<Context>()
        WorkManagerTestInitHelper.initializeTestWorkManager(context)
        customModelDir = tempFolder.newFolder("bayan_models")

        // Reset singleton service locators
        ModelStoreProvider.reset()
        SimplifierProvider.reset()
        SettingsRepository.reset()

        // Set up isolated DataStore for tests
        val testDataStoreFile = tempFolder.newFile("e2e_test_settings.preferences_pb")
        val testDataStore = PreferenceDataStoreFactory.create(
            produceFile = { testDataStoreFile }
        )
        settingsRepository = DefaultSettingsRepository(context, customDataStore = testDataStore)
        SettingsRepository.setInstance(settingsRepository)

        // Start deterministic in-process HTTP range server
        testServer = TestHttpRangeServer(E2ETestFixtures.TEST_PAYLOAD)
        testServer.start()
    }

    @After
    fun tearDown() {
        testServer.stop()
        ModelStoreProvider.reset()
        SimplifierProvider.reset()
        SettingsRepository.reset()
    }

    // =========================================================================
    // Scenario 1: First-Time User Journey (Genuine Bottom Sheet UI Flow)
    // =========================================================================

    @Test
    fun testScenario1_firstTimeUserJourney_modelNotReadyToDownloadToResultAndCopy() = runBlocking {
        // 1. Initial State: Model is not ready
        val store = DefaultModelStore(
            context = context,
            downloadUrl = testServer.url(),
            expectedSha256 = E2ETestFixtures.TEST_PAYLOAD_SHA256,
            customModelDir = customModelDir
        )
        ModelStoreProvider.setInstance(store)
        SimplifierProvider.setInstance(MockTextSimplifier())

        assertFalse("Model must not be ready initially", store.isReady())

        val capturedArabicText = "يمتطي الفارس جواده قاطبة في حلكة الليل."
        val expectedSimplifiedText = "يركب الفارس جواده جميعاً في ظلام الليل."

        // 2. Launch genuine SimplifiedBottomSheetDialogFragment
        val args = SimplifiedBottomSheetDialogFragment.newBundle(capturedArabicText)
        val scenario = launchFragmentInContainer<SimplifiedBottomSheetDialogFragment>(
            fragmentArgs = args,
            themeResId = R.style.Theme_Bayan
        )
        ShadowLooper.idleMainLooper()

        // 3. Verify SheetState.NeedsModel and UI views
        scenario.onFragment { fragment ->
            assertTrue("State must be NeedsModel", fragment.currentState is SheetState.NeedsModel)

            val view = fragment.requireView()
            assertEquals(View.VISIBLE, view.findViewById<View>(R.id.layoutNeedsModel).visibility)
            assertEquals(View.GONE, view.findViewById<View>(R.id.layoutResult).visibility)
            assertEquals(View.GONE, view.findViewById<View>(R.id.layoutLoading).visibility)

            val btnDownload = view.findViewById<Button>(R.id.btnDownloadModel)
            val btnCopy = view.findViewById<Button>(R.id.btnCopy)
            assertTrue("Download button must be enabled", btnDownload.isEnabled)
            assertFalse("Copy button must be disabled", btnCopy.isEnabled)

            // 4. User clicks download CTA in bottom sheet
            btnDownload.performClick()
        }

        // 5. Verify WorkManager unique work enqueued
        val workInfos = WorkManager.getInstance(context)
            .getWorkInfosForUniqueWork(ModelDownloadManager.WORK_NAME).get()
        assertNotNull(workInfos)
        assertTrue("WorkManager must have enqueued model-download work", workInfos.isNotEmpty())

        // 6. Complete model download via TestListenableWorkerBuilder
        val worker = TestListenableWorkerBuilder<DownloadModelWorker>(context)
            .setInputData(
                workDataOf(
                    DownloadModelWorker.KEY_URL to testServer.url(),
                    DownloadModelWorker.KEY_EXPECTED_SHA256 to E2ETestFixtures.TEST_PAYLOAD_SHA256,
                    DownloadModelWorker.KEY_MODEL_DIR to customModelDir.absolutePath,
                    DownloadModelWorker.KEY_TARGET_FILENAME to "pytorch_model.bin"
                )
            )
            .build()

        val workerResult = worker.doWork()
        assertEquals(ListenableWorker.Result.success(), workerResult)
        assertTrue("Model must now be ready", store.isReady())
        assertTrue("Model file must exist", store.getModelFile().exists())

        // 7. Launch bottom sheet with ready model
        val readyScenario = launchFragmentInContainer<SimplifiedBottomSheetDialogFragment>(
            fragmentArgs = args,
            themeResId = R.style.Theme_Bayan
        )
        ShadowLooper.idleMainLooper()

        // 8. Verify Result state, text views, and toggle interactions
        readyScenario.onFragment { fragment ->
            assertTrue("Fragment must reach SheetState.Result", fragment.currentState is SheetState.Result)

            val view = fragment.requireView()
            val tvLargeText = view.findViewById<TextView>(R.id.tvLargeText)
            val tvMutedText = view.findViewById<TextView>(R.id.tvMutedText)
            val btnToggle = view.findViewById<Button>(R.id.btnToggleText)
            val btnCopy = view.findViewById<Button>(R.id.btnCopy)

            assertEquals("layoutResult must be visible", View.VISIBLE, view.findViewById<View>(R.id.layoutResult).visibility)
            assertEquals("Initial enlarged text must be simplified", expectedSimplifiedText, tvLargeText.text.toString())
            assertEquals("Initial muted text must be original", capturedArabicText, tvMutedText.text.toString())
            assertTrue("Copy button must be enabled", btnCopy.isEnabled)

            // 9. User clicks toggle to swap enlarged text to original
            btnToggle.performClick()
            val toggledResult = fragment.currentState as SheetState.Result
            assertFalse("isShowingSimplifiedLarge must be false after toggle", toggledResult.isShowingSimplifiedLarge)
            assertEquals("Enlarged text must now be original", capturedArabicText, tvLargeText.text.toString())
            assertEquals("Muted text must now be simplified", expectedSimplifiedText, tvMutedText.text.toString())

            // 10. User clicks copy button while original is enlarged
            btnCopy.performClick()
            val clipboard = fragment.requireContext().getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
            assertEquals(capturedArabicText, clipboard.primaryClip?.getItemAt(0)?.text?.toString())

            // 11. User toggles back and copies simplified text
            btnToggle.performClick()
            btnCopy.performClick()
            assertEquals(expectedSimplifiedText, clipboard.primaryClip?.getItemAt(0)?.text?.toString())
        }
    }

    // =========================================================================
    // Scenario 2: Network Resume Journey (Worker & HTTP Range Server)
    // =========================================================================

    @Test
    fun testScenario2_networkResumeJourney_partialDownloadResumesWithRangeHeaderAndVerifiesSha256() = runBlocking {
        val store = DefaultModelStore(
            context = context,
            downloadUrl = testServer.url(),
            expectedSha256 = E2ETestFixtures.TEST_PAYLOAD_SHA256,
            customModelDir = customModelDir
        )
        ModelStoreProvider.setInstance(store)

        // Pre-create partial file with 400 bytes
        val partialLength = 400
        val partialBytes = E2ETestFixtures.TEST_PAYLOAD.copyOfRange(0, partialLength)
        store.getPartFile().writeBytes(partialBytes)

        assertTrue(store.getPartFile().exists())
        assertEquals(partialLength.toLong(), store.getPartFile().length())
        assertFalse(store.isReady())

        // Run worker via TestListenableWorkerBuilder
        val worker = TestListenableWorkerBuilder<DownloadModelWorker>(context)
            .setInputData(
                workDataOf(
                    DownloadModelWorker.KEY_URL to testServer.url(),
                    DownloadModelWorker.KEY_EXPECTED_SHA256 to E2ETestFixtures.TEST_PAYLOAD_SHA256,
                    DownloadModelWorker.KEY_MODEL_DIR to customModelDir.absolutePath,
                    DownloadModelWorker.KEY_TARGET_FILENAME to "pytorch_model.bin"
                )
            )
            .build()

        val result = worker.doWork()

        assertEquals(ListenableWorker.Result.success(), result)
        assertEquals("HTTP request must include Range header", "bytes=$partialLength-", testServer.lastRequestedRange)
        assertTrue("Model must be ready", store.isReady())
        assertTrue("Target model file must exist", store.getModelFile().exists())
        assertFalse("Partial file must be deleted", store.getPartFile().exists())
        assertEquals(E2ETestFixtures.TEST_PAYLOAD.size.toLong(), store.getModelFile().length())
        assertEquals(E2ETestFixtures.TEST_PAYLOAD_SHA256, DefaultModelStore.calculateSha256(store.getModelFile()))
    }

    @Test
    fun testScenario2_adversarial_serverIgnoresRangeAndReturns200_overwritesPartSafely() = runBlocking {
        val store = DefaultModelStore(
            context = context,
            downloadUrl = testServer.url(),
            expectedSha256 = E2ETestFixtures.TEST_PAYLOAD_SHA256,
            customModelDir = customModelDir
        )
        ModelStoreProvider.setInstance(store)

        // Server returns HTTP 200 instead of 206
        testServer.forceHttp200 = true

        // Stale corrupted 250 bytes in part file
        store.getPartFile().writeBytes(ByteArray(250) { 0x55.toByte() })

        val worker = TestListenableWorkerBuilder<DownloadModelWorker>(context)
            .setInputData(
                workDataOf(
                    DownloadModelWorker.KEY_URL to testServer.url(),
                    DownloadModelWorker.KEY_EXPECTED_SHA256 to E2ETestFixtures.TEST_PAYLOAD_SHA256,
                    DownloadModelWorker.KEY_MODEL_DIR to customModelDir.absolutePath,
                    DownloadModelWorker.KEY_TARGET_FILENAME to "pytorch_model.bin"
                )
            )
            .build()

        val result = worker.doWork()

        assertEquals(ListenableWorker.Result.success(), result)
        assertTrue(store.isReady())
        assertEquals(E2ETestFixtures.TEST_PAYLOAD.size.toLong(), store.getModelFile().length())
        assertEquals(E2ETestFixtures.TEST_PAYLOAD_SHA256, DefaultModelStore.calculateSha256(store.getModelFile()))
    }

    // =========================================================================
    // Scenario 3: Dyslexia Customization Journey (SettingsActivity -> DataStore -> Bottom Sheet)
    // =========================================================================

    @Test
    fun testScenario3_dyslexiaCustomizationJourney_datastorePreferencesAppliedToSheetTypography() = runBlocking {
        // 1. Launch genuine SettingsActivity using Robolectric controller
        val activityController = Robolectric.buildActivity(SettingsActivity::class.java)
        val activity = activityController.get()
        activity.settingsRepository = settingsRepository
        activityController.setup()
        ShadowLooper.idleMainLooper()

        // 2. Adjust settings UI widgets (rbStrengthLight maps to ADVANCED)
        val rbLight = activity.findViewById<RadioButton>(R.id.rbStrengthLight)
        rbLight.performClick()

        val sliderFontSize = activity.findViewById<Slider>(R.id.sliderFontSize)
        sliderFontSize.value = 28f
        settingsRepository.updateFontSize(28f)

        val sliderLineSpacing = activity.findViewById<Slider>(R.id.sliderLineSpacing)
        sliderLineSpacing.value = 1.8f
        settingsRepository.updateLineSpacing(1.8f)

        val rbNotoSans = activity.findViewById<RadioButton>(R.id.rbFontNotoSans)
        rbNotoSans.performClick()

        val switchWifi = activity.findViewById<MaterialSwitch>(R.id.switchWifiOnly)
        switchWifi.performClick()

        ShadowLooper.idleMainLooper()

        // 3. Verify preferences were persisted to DataStore
        val persisted = settingsRepository.preferencesFlow.first()
        assertEquals(SimplificationLevel.ADVANCED, persisted.simplificationLevel)
        assertEquals(28f, persisted.fontSizeSp, 0.01f)
        assertEquals(1.8f, persisted.lineSpacingMultiplier, 0.01f)
        assertEquals(BayanPreferences.FONT_FAMILY_NOTO_SANS, persisted.fontFamily)
        assertFalse(persisted.wifiOnlyDownload)

        activityController.destroy()

        // 4. Set up ready model
        val store = DefaultModelStore(context = context, customModelDir = customModelDir)
        store.getModelFile().writeBytes(E2ETestFixtures.TEST_PAYLOAD)
        ModelStoreProvider.setInstance(store)
        SimplifierProvider.setInstance(MockTextSimplifier())

        // 5. Launch genuine SimplifiedBottomSheetDialogFragment
        val inputArabic = "يبتغي الطالب النجاح في مسألة شائكة للغاية."
        val args = SimplifiedBottomSheetDialogFragment.newBundle(inputArabic)
        val scenario = launchFragmentInContainer<SimplifiedBottomSheetDialogFragment>(
            fragmentArgs = args,
            themeResId = R.style.Theme_Bayan
        )
        ShadowLooper.idleMainLooper()

        // 6. Verify dyslexia styling applied to real bottom sheet TextView
        scenario.onFragment { fragment ->
            assertTrue(fragment.currentState is SheetState.Result)
            val tvLargeText = fragment.requireView().findViewById<TextView>(R.id.tvLargeText)

            val expectedPx = TypedValue.applyDimension(
                TypedValue.COMPLEX_UNIT_SP,
                28f,
                fragment.resources.displayMetrics
            )
            assertEquals("Font size must match 28sp", expectedPx, tvLargeText.textSize, 0.5f)
            assertEquals("Line spacing multiplier must match 1.8x", 1.8f, tvLargeText.lineSpacingMultiplier, 0.01f)
            assertEquals("Letter spacing must be 0.04f", 0.04f, tvLargeText.letterSpacing, 0.005f)
            assertEquals("Text direction must be RTL", View.TEXT_DIRECTION_RTL, tvLargeText.textDirection)
        }
    }

    @Test
    fun testScenario3_boundaryValueAnalysis_dyslexiaPreferenceLimits() = runBlocking {
        val store = DefaultModelStore(context = context, customModelDir = customModelDir)
        store.getModelFile().writeBytes(E2ETestFixtures.TEST_PAYLOAD)
        ModelStoreProvider.setInstance(store)
        SimplifierProvider.setInstance(MockTextSimplifier())

        // Test minimum boundary (18sp, 1.2x)
        settingsRepository.updateFontSize(18f)
        settingsRepository.updateLineSpacing(1.2f)
        settingsRepository.updateSimplificationLevel(SimplificationLevel.ELEMENTARY)
        ShadowLooper.idleMainLooper()

        val scenarioMin = launchFragmentInContainer<SimplifiedBottomSheetDialogFragment>(
            fragmentArgs = SimplifiedBottomSheetDialogFragment.newBundle("نص تجريبي للحد الأدنى"),
            themeResId = R.style.Theme_Bayan
        )
        ShadowLooper.idleMainLooper()

        scenarioMin.onFragment { fragment ->
            val tvLargeText = fragment.requireView().findViewById<TextView>(R.id.tvLargeText)
            val expectedMinPx = TypedValue.applyDimension(
                TypedValue.COMPLEX_UNIT_SP,
                18f,
                fragment.resources.displayMetrics
            )
            assertEquals(expectedMinPx, tvLargeText.textSize, 0.5f)
            assertEquals(1.2f, tvLargeText.lineSpacingMultiplier, 0.01f)
        }

        // Test maximum boundary (32sp, 2.0x)
        settingsRepository.updateFontSize(32f)
        settingsRepository.updateLineSpacing(2.0f)
        settingsRepository.updateSimplificationLevel(SimplificationLevel.ADVANCED)
        ShadowLooper.idleMainLooper()

        val scenarioMax = launchFragmentInContainer<SimplifiedBottomSheetDialogFragment>(
            fragmentArgs = SimplifiedBottomSheetDialogFragment.newBundle("نص تجريبي للحد الأقصى"),
            themeResId = R.style.Theme_Bayan
        )
        ShadowLooper.idleMainLooper()

        scenarioMax.onFragment { fragment ->
            val tvLargeText = fragment.requireView().findViewById<TextView>(R.id.tvLargeText)
            val expectedMaxPx = TypedValue.applyDimension(
                TypedValue.COMPLEX_UNIT_SP,
                32f,
                fragment.resources.displayMetrics
            )
            assertEquals(expectedMaxPx, tvLargeText.textSize, 0.5f)
            assertEquals(2.0f, tvLargeText.lineSpacingMultiplier, 0.01f)
        }
    }

    // =========================================================================
    // Scenario 4: Corrupted Model Recovery (Worker Self-Healing)
    // =========================================================================

    @Test
    fun testScenario4_corruptedModelRecovery_detectionDeletesCorruptFileAndRecoversViaWorkerRedownload() = runBlocking {
        val store = DefaultModelStore(
            context = context,
            downloadUrl = testServer.url(),
            expectedSha256 = E2ETestFixtures.TEST_PAYLOAD_SHA256,
            customModelDir = customModelDir
        )
        ModelStoreProvider.setInstance(store)

        // Pre-populate disk with corrupted files
        store.getModelFile().writeBytes(E2ETestFixtures.CORRUPTED_PAYLOAD)
        store.getPartFile().writeBytes(ByteArray(128) { 0xFF.toByte() })
        assertTrue(store.getModelFile().exists())
        assertTrue(store.getPartFile().exists())

        // Integrity check detects mismatch and deletes corrupt files
        assertFalse(store.isReady())
        assertFalse(store.getModelFile().exists())
        assertFalse(store.getPartFile().exists())

        // Recover using DownloadModelWorker
        val worker = TestListenableWorkerBuilder<DownloadModelWorker>(context)
            .setInputData(
                workDataOf(
                    DownloadModelWorker.KEY_URL to testServer.url(),
                    DownloadModelWorker.KEY_EXPECTED_SHA256 to E2ETestFixtures.TEST_PAYLOAD_SHA256,
                    DownloadModelWorker.KEY_MODEL_DIR to customModelDir.absolutePath,
                    DownloadModelWorker.KEY_TARGET_FILENAME to "pytorch_model.bin"
                )
            )
            .build()

        val result = worker.doWork()

        assertEquals(ListenableWorker.Result.success(), result)
        assertTrue("Model must be ready after recovery", store.isReady())
        assertTrue("Recovered model file must exist", store.getModelFile().exists())
        assertEquals(E2ETestFixtures.TEST_PAYLOAD.size.toLong(), store.getModelFile().length())
        assertEquals(E2ETestFixtures.TEST_PAYLOAD_SHA256, DefaultModelStore.calculateSha256(store.getModelFile()))
    }

    @Test
    fun testScenario4_adversarial_serverServesCorruptedPayload_triggersDownloadFailureAndCleanup() = runBlocking {
        testServer.serveCorruptedPayload = true

        val store = DefaultModelStore(
            context = context,
            downloadUrl = testServer.url(),
            expectedSha256 = E2ETestFixtures.TEST_PAYLOAD_SHA256,
            customModelDir = customModelDir
        )
        ModelStoreProvider.setInstance(store)

        val worker = TestListenableWorkerBuilder<DownloadModelWorker>(context)
            .setInputData(
                workDataOf(
                    DownloadModelWorker.KEY_URL to testServer.url(),
                    DownloadModelWorker.KEY_EXPECTED_SHA256 to E2ETestFixtures.TEST_PAYLOAD_SHA256,
                    DownloadModelWorker.KEY_MODEL_DIR to customModelDir.absolutePath,
                    DownloadModelWorker.KEY_TARGET_FILENAME to "pytorch_model.bin"
                )
            )
            .build()

        val result = worker.doWork()

        assertTrue("Worker must return Retry or Failure on checksum mismatch", result is ListenableWorker.Result.Retry || result is ListenableWorker.Result.Failure)
        assertFalse("Corrupted part file must be deleted", store.getPartFile().exists())
        assertFalse("Target model file must not be created", store.getModelFile().exists())
        assertFalse(store.isReady())
    }

    // =========================================================================
    // Scenario 5: Error Resilience Journey (Genuine Bottom Sheet Error State)
    // =========================================================================

    @Test
    fun testScenario5_errorResilienceJourney_simplificationEngineErrorPreservesOriginalText() = runBlocking {
        val store = DefaultModelStore(context = context, customModelDir = customModelDir)
        store.getModelFile().writeBytes(E2ETestFixtures.TEST_PAYLOAD)
        ModelStoreProvider.setInstance(store)

        // Inject failing simplifier that throws runtime exception
        val failingSimplifier = FailingTextSimplifier(
            shouldThrowException = true,
            exceptionToThrow = RuntimeException("ONNX Runtime internal memory allocation failure (Out of Memory)")
        )
        SimplifierProvider.setInstance(failingSimplifier)

        val preciousOriginalText = "نص عربي بالغ الأهمية يجب عدم فقدانه عند حدوث أي خطأ تقني في المعالجة."
        val args = SimplifiedBottomSheetDialogFragment.newBundle(preciousOriginalText)

        val scenario = launchFragmentInContainer<SimplifiedBottomSheetDialogFragment>(
            fragmentArgs = args,
            themeResId = R.style.Theme_Bayan
        )
        ShadowLooper.idleMainLooper()

        // Verify Error state and view bindings
        scenario.onFragment { fragment ->
            assertTrue("Fragment state must be Error", fragment.currentState is SheetState.Error)

            val view = fragment.requireView()
            val layoutError = view.findViewById<View>(R.id.layoutError)
            val layoutResult = view.findViewById<View>(R.id.layoutResult)
            val tvErrorMessage = view.findViewById<TextView>(R.id.tvErrorMessage)
            val tvOriginalText = view.findViewById<TextView>(R.id.tvOriginalText)
            val btnCopy = view.findViewById<Button>(R.id.btnCopy)
            val btnSettings = view.findViewById<Button>(R.id.btnSettings)

            assertEquals("layoutError must be VISIBLE", View.VISIBLE, layoutError.visibility)
            assertEquals("layoutResult must be GONE", View.GONE, layoutResult.visibility)
            assertTrue("Error message must be shown", tvErrorMessage.text.contains("Out of Memory") || tvErrorMessage.text.contains("خطأ"))

            // CRITICAL INVARIANT: Original text must be preserved verbatim
            assertEquals("Original text must be preserved in Error state", preciousOriginalText, tvOriginalText.text.toString())
            assertFalse("Copy button must be disabled in Error state", btnCopy.isEnabled)
            assertTrue("Settings button must remain enabled", btnSettings.isEnabled)
        }

        // Engine recovers: restore valid simplifier
        SimplifierProvider.setInstance(MockTextSimplifier())

        val recoveredScenario = launchFragmentInContainer<SimplifiedBottomSheetDialogFragment>(
            fragmentArgs = args,
            themeResId = R.style.Theme_Bayan
        )
        ShadowLooper.idleMainLooper()

        recoveredScenario.onFragment { fragment ->
            assertTrue("Sheet must recover to Result state", fragment.currentState is SheetState.Result)
            val view = fragment.requireView()
            assertEquals(View.VISIBLE, view.findViewById<View>(R.id.layoutResult).visibility)
            assertEquals(preciousOriginalText, (fragment.currentState as SheetState.Result).originalText)
        }
    }

    @Test
    fun testScenario5_unsuccessfulSimplificationResult_transitionsToErrorStatePreservingText() = runBlocking {
        val store = DefaultModelStore(context = context, customModelDir = customModelDir)
        store.getModelFile().writeBytes(E2ETestFixtures.TEST_PAYLOAD)
        ModelStoreProvider.setInstance(store)

        val failingSimplifier = FailingTextSimplifier(
            shouldThrowException = false,
            errorMessage = "تعذر تبسيط النص نظراً لعدم توفر الموارد الكافية"
        )
        SimplifierProvider.setInstance(failingSimplifier)

        val text = "أضحت المسألة شائكة للغاية نظراً لـ شديد التعقيد."
        val args = SimplifiedBottomSheetDialogFragment.newBundle(text)

        val scenario = launchFragmentInContainer<SimplifiedBottomSheetDialogFragment>(
            fragmentArgs = args,
            themeResId = R.style.Theme_Bayan
        )
        ShadowLooper.idleMainLooper()

        scenario.onFragment { fragment ->
            assertTrue("State must be Error on unsuccessful result", fragment.currentState is SheetState.Error)
            val view = fragment.requireView()
            val tvOriginalText = view.findViewById<TextView>(R.id.tvOriginalText)
            val tvErrorMessage = view.findViewById<TextView>(R.id.tvErrorMessage)

            assertEquals("Original text preserved", text, tvOriginalText.text.toString())
            assertEquals("تعذر تبسيط النص نظراً لعدم توفر الموارد الكافية", tvErrorMessage.text.toString())
        }
    }
}
