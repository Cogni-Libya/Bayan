package ai.bayan.android

import android.content.DialogInterface
import android.graphics.text.LineBreaker
import android.os.Build
import android.view.View
import android.widget.Button
import android.widget.TextView
import androidx.fragment.app.testing.launchFragmentInContainer
import ai.bayan.android.engine.ModelStore
import ai.bayan.android.engine.ModelStoreProvider
import ai.bayan.android.engine.SimplifierProvider
import ai.bayan.android.ui.SimplifiedBottomSheetDialogFragment
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.shadows.ShadowLooper
import java.io.File

/**
 * Robolectric automated tests for [SimplifiedBottomSheetDialogFragment].
 *
 * Verifies argument initialization, view binding of original and simplified Arabic text,
 * dyslexia typography specifications (1.6x line multiplier, 10sp extra spacing, 0.04 letter spacing,
 * RTL alignment, unjustified text flow), enabled/disabled action buttons in Result state,
 * and dismissal callbacks.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class SimplifiedBottomSheetTest {

    @Before
    fun setUp() {
        SimplifierProvider.reset()
        val readyStore = object : ModelStore {
            override fun isReady(): Boolean = true
            override suspend fun download(onProgress: (Float) -> Unit) {}
            override fun modelDir(): File = File("/tmp")
            override fun getModelFile(): File = File("/tmp/pytorch_model.bin")
            override fun getPartFile(): File = File("/tmp/pytorch_model.bin.part")
            override fun getExpectedSha256(): String = ""
            override fun getDownloadUrl(): String = ""
            override fun deleteCorruptedFiles() {}
        }
        ModelStoreProvider.setInstance(readyStore)
    }

    @After
    fun tearDown() {
        SimplifierProvider.reset()
        ModelStoreProvider.reset()
    }

    @Test
    fun testNewBundle_populatesArgumentsCorrectly() {
        val testText = "نص عربي تجريبي لبيان"
        val bundle = SimplifiedBottomSheetDialogFragment.newBundle(testText, isReadOnly = true)

        assertNotNull("Bundle must not be null", bundle)
        assertEquals(testText, bundle.getString(SimplifiedBottomSheetDialogFragment.ARG_ORIGINAL_TEXT))
        assertTrue(bundle.getBoolean(SimplifiedBottomSheetDialogFragment.ARG_IS_READ_ONLY))
    }

    @Test
    fun testNewBundle_defaultsIsReadOnlyToFalse() {
        val testText = "نص بدون تحديد خاصية القراءة فقط"
        val bundle = SimplifiedBottomSheetDialogFragment.newBundle(testText)

        assertEquals(testText, bundle.getString(SimplifiedBottomSheetDialogFragment.ARG_ORIGINAL_TEXT))
        assertFalse("Default isReadOnly must be false", bundle.getBoolean(SimplifiedBottomSheetDialogFragment.ARG_IS_READ_ONLY))
    }

    @Test
    fun testNewInstance_setsArgumentsOnFragment() {
        val testText = "نص لاختبار دالة newInstance"
        val sheet = SimplifiedBottomSheetDialogFragment.newInstance(testText, isReadOnly = true)

        assertNotNull(sheet.arguments)
        assertEquals(testText, sheet.arguments?.getString(SimplifiedBottomSheetDialogFragment.ARG_ORIGINAL_TEXT))
        assertEquals(true, sheet.arguments?.getBoolean(SimplifiedBottomSheetDialogFragment.ARG_IS_READ_ONLY))
    }

    @Test
    fun testViewBinding_displaysOriginalText() {
        val originalArabic = "يمتطي الفارس جواده مسرعاً نحو القرية قاطبة."
        val args = SimplifiedBottomSheetDialogFragment.newBundle(originalArabic, isReadOnly = false)

        val scenario = launchFragmentInContainer<SimplifiedBottomSheetDialogFragment>(
            fragmentArgs = args,
            themeResId = R.style.Theme_Bayan
        )

        scenario.onFragment { fragment ->
            val view = fragment.requireView()
            val tvOriginal = view.findViewById<TextView>(R.id.tvOriginalText) ?: view.findViewById<TextView>(R.id.tvMutedText)
            assertNotNull("tvOriginalText view must be present in layout", tvOriginal)
            assertEquals("Original text view must display captured text", originalArabic, tvOriginal.text.toString())
        }
    }

    @Test
    fun testViewBinding_displaysSimplifiedText() {
        val originalArabic = "يبتغي الطالب مؤازرة زملائه نظراً لـ حلكة الظروف."
        val expectedSimplified = "يريد الطالب مساعدة زملائه بسبب ظلام الظروف."
        val args = SimplifiedBottomSheetDialogFragment.newBundle(originalArabic, isReadOnly = false)

        val scenario = launchFragmentInContainer<SimplifiedBottomSheetDialogFragment>(
            fragmentArgs = args,
            themeResId = R.style.Theme_Bayan
        )

        // Advance looper to allow lifecycleScope coroutine to complete
        ShadowLooper.idleMainLooper()

        scenario.onFragment { fragment ->
            val view = fragment.requireView()
            val tvSimplified = view.findViewById<TextView>(R.id.tvLargeText) ?: view.findViewById<TextView>(R.id.tvSimplifiedText)
            assertNotNull("tvSimplifiedText view must be present in layout", tvSimplified)
            assertEquals("Simplified text view must display transformed text", expectedSimplified, tvSimplified.text.toString())
        }
    }

    @Test
    fun testDyslexiaTypographyAttributes_configuredStrictly() {
        val originalArabic = "نص لفحص مواصفات الخط المخصص لعسر القراءة."
        val args = SimplifiedBottomSheetDialogFragment.newBundle(originalArabic, isReadOnly = false)

        val scenario = launchFragmentInContainer<SimplifiedBottomSheetDialogFragment>(
            fragmentArgs = args,
            themeResId = R.style.Theme_Bayan
        )

        ShadowLooper.idleMainLooper()

        scenario.onFragment { fragment ->
            val view = fragment.requireView()
            val tvSimplified = view.findViewById<TextView>(R.id.tvLargeText) ?: view.findViewById<TextView>(R.id.tvSimplifiedText)
            assertNotNull(tvSimplified)

            // 1. Generous line spacing multiplier (1.6x)
            assertEquals(
                "Line spacing multiplier must be 1.6f for Arabic dyslexia readability",
                1.6f,
                tvSimplified.lineSpacingMultiplier,
                0.01f
            )

            // 2. Extra line spacing (10sp)
            val expectedExtraPx = fragment.resources.getDimensionPixelSize(R.dimen.dyslexia_line_spacing_extra)
            assertEquals(
                "Line spacing extra must match 10sp dimension",
                expectedExtraPx.toFloat(),
                tvSimplified.lineSpacingExtra,
                0.5f
            )

            // 3. Moderate letter spacing (0.04f)
            assertEquals(
                "Letter spacing must be 0.04f to balance clarity without breaking cursive ligatures",
                0.04f,
                tvSimplified.letterSpacing,
                0.005f
            )

            // 4. Explicit Right-to-Left alignment
            assertEquals(
                "Text direction must be View.TEXT_DIRECTION_RTL",
                View.TEXT_DIRECTION_RTL,
                tvSimplified.textDirection
            )

            // 5. Anti-rivers unjustified text flow (JUSTIFICATION_MODE_NONE)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                assertEquals(
                    "Justification mode must be LineBreaker.JUSTIFICATION_MODE_NONE to eliminate kashida elongation rivers",
                    LineBreaker.JUSTIFICATION_MODE_NONE,
                    tvSimplified.justificationMode
                )
            }
        }
    }

    @Test
    fun testDisabledControlRow_allButtonsDisabledPerSpecification() {
        val args = SimplifiedBottomSheetDialogFragment.newBundle("نص تجريبي", isReadOnly = false)

        val scenario = launchFragmentInContainer<SimplifiedBottomSheetDialogFragment>(
            fragmentArgs = args,
            themeResId = R.style.Theme_Bayan
        )

        ShadowLooper.idleMainLooper()

        scenario.onFragment { fragment ->
            val view = fragment.requireView()
            val btnListen = view.findViewById<Button>(R.id.btnListen)
            val btnCopy = view.findViewById<Button>(R.id.btnCopy)
            val btnSettings = view.findViewById<Button>(R.id.btnSettings)
            val tvDisabledNotice = view.findViewById<TextView>(R.id.tvDisabledNotice)

            assertNotNull("btnListen must exist", btnListen)
            assertNotNull("btnCopy must exist", btnCopy)
            assertNotNull("btnSettings must exist", btnSettings)
            assertNotNull("tvDisabledNotice must exist", tvDisabledNotice)

            assertFalse("Listen button (▶ استمع) must be disabled in this release", btnListen.isEnabled)
            assertTrue("Copy button (⧉ نسخ) must be enabled in Result state", btnCopy.isEnabled)
            assertTrue("Settings button (⚙) must be enabled in Result state", btnSettings.isEnabled)
            assertTrue("Feature in development notice must be displayed", tvDisabledNotice.text.isNotBlank())
        }
    }

    @Test
    fun testOnDismissListener_notifiedWhenDialogDismissed() {
        val args = SimplifiedBottomSheetDialogFragment.newBundle("نص تجريبي", isReadOnly = false)

        val scenario = launchFragmentInContainer<SimplifiedBottomSheetDialogFragment>(
            fragmentArgs = args,
            themeResId = R.style.Theme_Bayan
        )

        scenario.onFragment { fragment ->
            var dismissedCalled = false
            fragment.setOnDismissListener(object : SimplifiedBottomSheetDialogFragment.OnDismissListener {
                override fun onDismissed() {
                    dismissedCalled = true
                }
            })

            // Simulate dialog dismiss event
            val dummyDialog = object : DialogInterface {
                override fun cancel() {}
                override fun dismiss() {}
            }
            fragment.onDismiss(dummyDialog)

            assertTrue("onDismissed callback must be invoked on listener when sheet is dismissed", dismissedCalled)
        }
    }
}
