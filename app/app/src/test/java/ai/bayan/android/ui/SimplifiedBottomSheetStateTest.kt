package ai.bayan.android.ui

import android.content.ClipboardManager
import android.content.Context
import android.util.TypedValue
import android.view.View
import android.widget.Button
import android.widget.TextView
import androidx.fragment.app.testing.launchFragmentInContainer
import androidx.test.core.app.ApplicationProvider
import androidx.work.WorkManager
import androidx.work.testing.WorkManagerTestInitHelper
import ai.bayan.android.R
import ai.bayan.android.download.ModelDownloadManager
import ai.bayan.android.engine.EngineInfo
import ai.bayan.android.engine.ModelStore
import ai.bayan.android.engine.ModelStoreProvider
import ai.bayan.android.engine.SimplificationLevel
import ai.bayan.android.engine.SimplificationRequest
import ai.bayan.android.engine.SimplificationResult
import ai.bayan.android.engine.SimplifierProvider
import ai.bayan.android.engine.TextSimplifier
import ai.bayan.android.settings.BayanPreferences
import ai.bayan.android.settings.SettingsRepository
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config
import org.robolectric.shadows.ShadowLooper
import java.io.File

/**
 * Comprehensive Robolectric tests for [SimplifiedBottomSheetDialogFragment] and [SheetState] state machine.
 *
 * Verifies all 4 states (NeedsModel, Loading, Result, Error), download work enqueueing,
 * active text toggle and clipboard copy, error resilience with original Arabic text preservation,
 * settings navigation, and dynamic dyslexia typography propagation from DataStore preferences.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class SimplifiedBottomSheetStateTest {

    private lateinit var context: Context

    private val readyModelStore = object : ModelStore {
        override fun isReady(): Boolean = true
        override suspend fun download(onProgress: (Float) -> Unit) {}
        override fun modelDir(): File = File("/tmp")
        override fun getModelFile(): File = File("/tmp/pytorch_model.bin")
        override fun getPartFile(): File = File("/tmp/pytorch_model.bin.part")
        override fun getExpectedSha256(): String = "b840cd5afdcc806b8175fed5a8800a5aa8be1beb60aab8ab7f650728b122dac2"
        override fun getDownloadUrl(): String = "https://example.com/model.bin"
        override fun deleteCorruptedFiles() {}
    }

    private val notReadyModelStore = object : ModelStore {
        override fun isReady(): Boolean = false
        override suspend fun download(onProgress: (Float) -> Unit) {}
        override fun modelDir(): File = File("/tmp")
        override fun getModelFile(): File = File("/tmp/pytorch_model.bin")
        override fun getPartFile(): File = File("/tmp/pytorch_model.bin.part")
        override fun getExpectedSha256(): String = "b840cd5afdcc806b8175fed5a8800a5aa8be1beb60aab8ab7f650728b122dac2"
        override fun getDownloadUrl(): String = "https://example.com/model.bin"
        override fun deleteCorruptedFiles() {}
    }

    @Before
    fun setUp() {
        context = ApplicationProvider.getApplicationContext<Context>()
        WorkManagerTestInitHelper.initializeTestWorkManager(context)
        SimplifierProvider.reset()
        ModelStoreProvider.reset()
        SettingsRepository.reset()
    }

    @After
    fun tearDown() {
        SimplifierProvider.reset()
        ModelStoreProvider.reset()
        SettingsRepository.reset()
    }

    @Test
    fun testInitialState_whenModelNotReady_rendersNeedsModelState() {
        ModelStoreProvider.setInstance(notReadyModelStore)

        val args = SimplifiedBottomSheetDialogFragment.newBundle("نص تجريبي للاختبار")
        val scenario = launchFragmentInContainer<SimplifiedBottomSheetDialogFragment>(
            fragmentArgs = args,
            themeResId = R.style.Theme_Bayan
        )

        scenario.onFragment { fragment ->
            assertTrue(
                "Fragment state must be SheetState.NeedsModel when model is not ready",
                fragment.currentState is SheetState.NeedsModel
            )

            val view = fragment.requireView()
            val layoutNeedsModel = view.findViewById<View>(R.id.layoutNeedsModel)
            val layoutLoading = view.findViewById<View>(R.id.layoutLoading)
            val layoutResult = view.findViewById<View>(R.id.layoutResult)
            val layoutError = view.findViewById<View>(R.id.layoutError)
            val btnDownloadModel = view.findViewById<Button>(R.id.btnDownloadModel)
            val btnCopy = view.findViewById<Button>(R.id.btnCopy)

            assertEquals("layoutNeedsModel must be VISIBLE", View.VISIBLE, layoutNeedsModel.visibility)
            assertEquals("layoutLoading must be GONE", View.GONE, layoutLoading.visibility)
            assertEquals("layoutResult must be GONE", View.GONE, layoutResult.visibility)
            assertEquals("layoutError must be GONE", View.GONE, layoutError.visibility)

            assertTrue("Download button must be enabled", btnDownloadModel.isEnabled)
            assertFalse("Copy button must be disabled in NeedsModel state", btnCopy.isEnabled)
        }
    }

    @Test
    fun testNeedsModel_clickDownload_enqueuesWork() {
        ModelStoreProvider.setInstance(notReadyModelStore)

        val args = SimplifiedBottomSheetDialogFragment.newBundle("نص تجريبي للتنزيل")
        val scenario = launchFragmentInContainer<SimplifiedBottomSheetDialogFragment>(
            fragmentArgs = args,
            themeResId = R.style.Theme_Bayan
        )

        scenario.onFragment { fragment ->
            val view = fragment.requireView()
            val btnDownloadModel = view.findViewById<Button>(R.id.btnDownloadModel)
            assertNotNull("btnDownloadModel must exist", btnDownloadModel)

            // Click the download CTA
            btnDownloadModel.performClick()

            // Verify unique work was enqueued with WorkManager
            val workInfos = WorkManager.getInstance(fragment.requireContext())
                .getWorkInfosForUniqueWork(ModelDownloadManager.WORK_NAME)
                .get()

            assertNotNull(workInfos)
            assertTrue("WorkManager must have enqueued unique model-download work", workInfos.isNotEmpty())
        }
    }

    @Test
    fun testInitialState_whenModelReady_transitionsLoadingToResult() {
        ModelStoreProvider.setInstance(readyModelStore)

        val originalArabic = "يسعى الباحث إلى استنباط الحلول لمعالجة عسر القراءة."
        val expectedSimplified = "يحاول الباحث إيجاد الحلول لتسهيل القراءة."

        val fakeSimplifier = object : TextSimplifier {
            override suspend fun simplify(request: SimplificationRequest): SimplificationResult {
                return SimplificationResult(
                    originalText = request.originalText,
                    simplifiedText = expectedSimplified,
                    isSuccess = true
                )
            }
            override fun isModelReady(): Boolean = true
            override fun getEngineInfo(): EngineInfo = EngineInfo("Fake", "1.0", "Ready", "1MB", false)
        }
        SimplifierProvider.setInstance(fakeSimplifier)

        val args = SimplifiedBottomSheetDialogFragment.newBundle(originalArabic)
        val scenario = launchFragmentInContainer<SimplifiedBottomSheetDialogFragment>(
            fragmentArgs = args,
            themeResId = R.style.Theme_Bayan
        )

        // Advance coroutines on main looper
        ShadowLooper.idleMainLooper()

        scenario.onFragment { fragment ->
            assertTrue(
                "Fragment state must be SheetState.Result after successful simplification",
                fragment.currentState is SheetState.Result
            )

            val view = fragment.requireView()
            val layoutResult = view.findViewById<View>(R.id.layoutResult)
            val layoutLoading = view.findViewById<View>(R.id.layoutLoading)
            val layoutNeedsModel = view.findViewById<View>(R.id.layoutNeedsModel)
            val tvLargeText = view.findViewById<TextView>(R.id.tvLargeText)
            val tvMutedText = view.findViewById<TextView>(R.id.tvMutedText)

            assertEquals("layoutResult must be VISIBLE", View.VISIBLE, layoutResult.visibility)
            assertEquals("layoutLoading must be GONE", View.GONE, layoutLoading.visibility)
            assertEquals("layoutNeedsModel must be GONE", View.GONE, layoutNeedsModel.visibility)

            assertEquals("Active enlarged text must display simplified output", expectedSimplified, tvLargeText.text.toString())
            assertEquals("Muted text must display captured original text", originalArabic, tvMutedText.text.toString())
        }
    }

    @Test
    fun testResultState_toggleButton_swapsEnlargedText() {
        ModelStoreProvider.setInstance(readyModelStore)

        val originalArabic = "النص الأصلي المعقد"
        val simplifiedArabic = "النص المبسط الميسر"

        val fakeSimplifier = object : TextSimplifier {
            override suspend fun simplify(request: SimplificationRequest): SimplificationResult {
                return SimplificationResult(
                    originalText = request.originalText,
                    simplifiedText = simplifiedArabic,
                    isSuccess = true
                )
            }
            override fun isModelReady(): Boolean = true
            override fun getEngineInfo(): EngineInfo = EngineInfo("Fake", "1.0", "Ready", "1MB", false)
        }
        SimplifierProvider.setInstance(fakeSimplifier)

        val args = SimplifiedBottomSheetDialogFragment.newBundle(originalArabic)
        val scenario = launchFragmentInContainer<SimplifiedBottomSheetDialogFragment>(
            fragmentArgs = args,
            themeResId = R.style.Theme_Bayan
        )

        ShadowLooper.idleMainLooper()

        scenario.onFragment { fragment ->
            val view = fragment.requireView()
            val tvLargeText = view.findViewById<TextView>(R.id.tvLargeText)
            val tvMutedText = view.findViewById<TextView>(R.id.tvMutedText)
            val btnToggleText = view.findViewById<Button>(R.id.btnToggleText)

            // Initially: simplified text is enlarged
            val initialResult = fragment.currentState as SheetState.Result
            assertTrue("Initially isShowingSimplifiedLarge must be true", initialResult.isShowingSimplifiedLarge)
            assertEquals(simplifiedArabic, tvLargeText.text.toString())
            assertEquals(originalArabic, tvMutedText.text.toString())

            // 1st Click: toggle to show original text enlarged
            btnToggleText.performClick()
            val toggledResult = fragment.currentState as SheetState.Result
            assertFalse("After first toggle, isShowingSimplifiedLarge must be false", toggledResult.isShowingSimplifiedLarge)
            assertEquals("Enlarged text must now show original text", originalArabic, tvLargeText.text.toString())
            assertEquals("Muted text must now show simplified text", simplifiedArabic, tvMutedText.text.toString())

            // 2nd Click: toggle back to show simplified text enlarged
            btnToggleText.performClick()
            val revertedResult = fragment.currentState as SheetState.Result
            assertTrue("After second toggle, isShowingSimplifiedLarge must be true", revertedResult.isShowingSimplifiedLarge)
            assertEquals(simplifiedArabic, tvLargeText.text.toString())
            assertEquals(originalArabic, tvMutedText.text.toString())
        }
    }

    @Test
    fun testResultState_copyButton_copiesActiveEnlargedText() {
        ModelStoreProvider.setInstance(readyModelStore)

        val originalArabic = "النص الأصلي للحفظ"
        val simplifiedArabic = "النص المبسط للحفظ"

        val fakeSimplifier = object : TextSimplifier {
            override suspend fun simplify(request: SimplificationRequest): SimplificationResult {
                return SimplificationResult(
                    originalText = request.originalText,
                    simplifiedText = simplifiedArabic,
                    isSuccess = true
                )
            }
            override fun isModelReady(): Boolean = true
            override fun getEngineInfo(): EngineInfo = EngineInfo("Fake", "1.0", "Ready", "1MB", false)
        }
        SimplifierProvider.setInstance(fakeSimplifier)

        val args = SimplifiedBottomSheetDialogFragment.newBundle(originalArabic)
        val scenario = launchFragmentInContainer<SimplifiedBottomSheetDialogFragment>(
            fragmentArgs = args,
            themeResId = R.style.Theme_Bayan
        )

        ShadowLooper.idleMainLooper()

        scenario.onFragment { fragment ->
            val view = fragment.requireView()
            val btnCopy = view.findViewById<Button>(R.id.btnCopy)
            val btnToggleText = view.findViewById<Button>(R.id.btnToggleText)
            val clipboard = fragment.requireContext().getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager

            assertTrue("Copy button must be enabled in Result state", btnCopy.isEnabled)

            // When simplified text is enlarged: copies simplified text
            btnCopy.performClick()
            val clip1 = clipboard.primaryClip?.getItemAt(0)?.text?.toString()
            assertEquals("Copy button must copy active simplified text", simplifiedArabic, clip1)

            // Toggle to original text enlarged: copies original text
            btnToggleText.performClick()
            btnCopy.performClick()
            val clip2 = clipboard.primaryClip?.getItemAt(0)?.text?.toString()
            assertEquals("Copy button must copy active original text after toggle", originalArabic, clip2)
        }
    }

    @Test
    fun testErrorState_onSimplificationException_preservesOriginalText() {
        ModelStoreProvider.setInstance(readyModelStore)

        val capturedArabic = "هذا النص العربي التخصصي شديد الأهمية ويجب ألا يُفقد أبداً عند حدوث خطأ."
        val expectedErrorMessage = "تعذر تشغيل نموذج الذكاء الاصطناعي بسبب استهلاك الذاكرة."

        val failingSimplifier = object : TextSimplifier {
            override suspend fun simplify(request: SimplificationRequest): SimplificationResult {
                throw IllegalStateException(expectedErrorMessage)
            }
            override fun isModelReady(): Boolean = true
            override fun getEngineInfo(): EngineInfo = EngineInfo("FailingEngine", "1.0", "Error", "0MB", false)
        }
        SimplifierProvider.setInstance(failingSimplifier)

        val args = SimplifiedBottomSheetDialogFragment.newBundle(capturedArabic)
        val scenario = launchFragmentInContainer<SimplifiedBottomSheetDialogFragment>(
            fragmentArgs = args,
            themeResId = R.style.Theme_Bayan
        )

        ShadowLooper.idleMainLooper()

        scenario.onFragment { fragment ->
            assertTrue(
                "Fragment state must be SheetState.Error on simplification exception",
                fragment.currentState is SheetState.Error
            )

            val view = fragment.requireView()
            val layoutError = view.findViewById<View>(R.id.layoutError)
            val layoutResult = view.findViewById<View>(R.id.layoutResult)
            val tvErrorMessage = view.findViewById<TextView>(R.id.tvErrorMessage)
            val tvOriginalText = view.findViewById<TextView>(R.id.tvOriginalText)

            assertEquals("layoutError must be VISIBLE", View.VISIBLE, layoutError.visibility)
            assertEquals("layoutResult must be GONE", View.GONE, layoutResult.visibility)

            assertTrue("Error message must be displayed to the user", tvErrorMessage.text.contains(expectedErrorMessage))

            // CRUCIAL REQUIREMENT: Original captured Arabic text must be fully preserved and readable
            assertEquals(
                "Captured Arabic text must be preserved verbatim in Error state",
                capturedArabic,
                tvOriginalText.text.toString()
            )
        }
    }

    @Test
    fun testSettingsButton_launchesSettingsActivity() {
        ModelStoreProvider.setInstance(readyModelStore)

        val args = SimplifiedBottomSheetDialogFragment.newBundle("نص لفتح الإعدادات")
        val scenario = launchFragmentInContainer<SimplifiedBottomSheetDialogFragment>(
            fragmentArgs = args,
            themeResId = R.style.Theme_Bayan
        )

        ShadowLooper.idleMainLooper()

        scenario.onFragment { fragment ->
            val view = fragment.requireView()
            val btnSettings = view.findViewById<Button>(R.id.btnSettings)
            assertNotNull("btnSettings must exist", btnSettings)
            assertTrue("btnSettings must be enabled", btnSettings.isEnabled)

            btnSettings.performClick()

            val shadowActivity = shadowOf(fragment.requireActivity())
            val startedIntent = shadowActivity.nextStartedActivity

            assertNotNull("SettingsActivity intent must be launched", startedIntent)
            assertEquals(
                "ai.bayan.android.settings.SettingsActivity",
                startedIntent.component?.className
            )
        }
    }

    @Test
    fun testBottomSheet_appliesDynamicTypographyFromPreferences() {
        ModelStoreProvider.setInstance(readyModelStore)

        val preferencesFlowState = MutableStateFlow(
            BayanPreferences(
                fontSizeSp = 22f,
                lineSpacingMultiplier = 1.6f,
                fontFamily = BayanPreferences.FONT_FAMILY_NOTO_NASKH
            )
        )

        val mockRepository = object : SettingsRepository {
            override val preferencesFlow: Flow<BayanPreferences> = preferencesFlowState

            override suspend fun updateSimplificationLevel(level: SimplificationLevel) {
                preferencesFlowState.value = preferencesFlowState.value.copy(simplificationLevel = level)
            }
            override suspend fun updateFontSize(fontSizeSp: Float) {
                preferencesFlowState.value = preferencesFlowState.value.copy(fontSizeSp = fontSizeSp)
            }
            override suspend fun updateLineSpacing(multiplier: Float) {
                preferencesFlowState.value = preferencesFlowState.value.copy(lineSpacingMultiplier = multiplier)
            }
            override suspend fun updateFontFamily(fontFamily: String) {
                preferencesFlowState.value = preferencesFlowState.value.copy(fontFamily = fontFamily)
            }
            override suspend fun updateWifiOnlyDownload(wifiOnly: Boolean) {
                preferencesFlowState.value = preferencesFlowState.value.copy(wifiOnlyDownload = wifiOnly)
            }
        }
        SettingsRepository.setInstance(mockRepository)

        val args = SimplifiedBottomSheetDialogFragment.newBundle("نص لفحص التنسيق الديناميكي")
        val scenario = launchFragmentInContainer<SimplifiedBottomSheetDialogFragment>(
            fragmentArgs = args,
            themeResId = R.style.Theme_Bayan
        )

        ShadowLooper.idleMainLooper()

        scenario.onFragment { fragment ->
            val view = fragment.requireView()
            val tvLargeText = view.findViewById<TextView>(R.id.tvLargeText)

            // Initial typography check (22sp, 1.6x)
            val initialExpectedPx = TypedValue.applyDimension(
                TypedValue.COMPLEX_UNIT_SP,
                22f,
                fragment.resources.displayMetrics
            )
            assertEquals(initialExpectedPx, tvLargeText.textSize, 0.5f)
            assertEquals(1.6f, tvLargeText.lineSpacingMultiplier, 0.01f)
            assertEquals(0.04f, tvLargeText.letterSpacing, 0.005f)
            assertEquals(View.TEXT_DIRECTION_RTL, tvLargeText.textDirection)

            // Dynamically update preferences in repository
            runBlocking {
                mockRepository.updateFontSize(30f)
                mockRepository.updateLineSpacing(1.9f)
                mockRepository.updateFontFamily(BayanPreferences.FONT_FAMILY_NOTO_SANS)
            }

            // Idle looper so coroutines process flow emission
            ShadowLooper.idleMainLooper()

            // Verify typography updated dynamically
            val updatedExpectedPx = TypedValue.applyDimension(
                TypedValue.COMPLEX_UNIT_SP,
                30f,
                fragment.resources.displayMetrics
            )
            assertEquals("Font size must reactively update to 30sp", updatedExpectedPx, tvLargeText.textSize, 0.5f)
            assertEquals("Line spacing multiplier must reactively update to 1.9x", 1.9f, tvLargeText.lineSpacingMultiplier, 0.01f)
            assertEquals("Letter spacing must be preserved at 0.04f", 0.04f, tvLargeText.letterSpacing, 0.005f)
            assertEquals("Text direction must remain RTL", View.TEXT_DIRECTION_RTL, tvLargeText.textDirection)
        }
    }

    @Test
    fun testNeedsModel_whenDownloadCompletes_automaticallyTransitionsToResult() {
        var isReady = false
        val dynamicallyReadyStore = object : ModelStore {
            override fun isReady(): Boolean = isReady
            override suspend fun download(onProgress: (Float) -> Unit) {
                isReady = true
                onProgress(1.0f)
            }
            override fun modelDir(): File = File("/tmp")
            override fun getModelFile(): File = File("/tmp/pytorch_model.bin")
            override fun getPartFile(): File = File("/tmp/pytorch_model.bin.part")
            override fun getExpectedSha256(): String = "test_sha"
            override fun getDownloadUrl(): String = "http://example.com/model.bin"
            override fun deleteCorruptedFiles() {}
        }
        ModelStoreProvider.setInstance(dynamicallyReadyStore)

        val simplifiedOutput = "النص المبسط تلقائياً بعد اكتمال التنزيل"
        val fakeSimplifier = object : TextSimplifier {
            override suspend fun simplify(request: SimplificationRequest): SimplificationResult {
                return SimplificationResult(
                    originalText = request.originalText,
                    simplifiedText = simplifiedOutput,
                    isSuccess = true
                )
            }
            override fun isModelReady(): Boolean = true
            override fun getEngineInfo(): EngineInfo = EngineInfo("Fake", "1.0", "Ready", "1MB", false)
        }
        SimplifierProvider.setInstance(fakeSimplifier)

        val args = SimplifiedBottomSheetDialogFragment.newBundle("نص تجريبي للاختبار التلقائي")
        val scenario = launchFragmentInContainer<SimplifiedBottomSheetDialogFragment>(
            fragmentArgs = args,
            themeResId = R.style.Theme_Bayan
        )

        scenario.onFragment { fragment ->
            // Initially in NeedsModel
            assertTrue("Must begin in NeedsModel", fragment.currentState is SheetState.NeedsModel)

            val btnDownloadModel = fragment.requireView().findViewById<Button>(R.id.btnDownloadModel)
            btnDownloadModel.performClick()

            // Simulate download finishing in background
            isReady = true
            val testDriver = WorkManagerTestInitHelper.getTestDriver(fragment.requireContext())
            val workInfos = WorkManager.getInstance(fragment.requireContext())
                .getWorkInfosForUniqueWork(ModelDownloadManager.WORK_NAME)
                .get()
            val workId = workInfos.first().id
            testDriver?.setAllConstraintsMet(workId)

            ShadowLooper.idleMainLooper()

            // Verify auto-transition to Result without user dismissing sheet
            assertTrue(
                "Fragment must auto-transition to Result state",
                fragment.currentState is SheetState.Result
            )
            val resultState = fragment.currentState as SheetState.Result
            assertEquals(simplifiedOutput, resultState.simplifiedText)
        }
    }
}
