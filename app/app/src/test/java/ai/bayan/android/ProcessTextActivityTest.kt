package ai.bayan.android

import android.content.Intent
import android.os.Bundle
import android.text.SpannableString
import androidx.test.core.app.ActivityScenario
import androidx.test.core.app.ApplicationProvider
import ai.bayan.android.engine.SimplifierProvider
import ai.bayan.android.ui.SimplifiedBottomSheetDialogFragment
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.shadows.ShadowToast

/**
 * Robolectric automated tests for [ProcessTextActivity].
 *
 * Verifies system PROCESS_TEXT intent handling, text extraction, read-only propagation,
 * immediate finish on empty/null inputs with user toast notification, and proper dismissal lifecycle finish.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class ProcessTextActivityTest {

    @Before
    fun setUp() {
        SimplifierProvider.reset()
    }

    @After
    fun tearDown() {
        SimplifierProvider.reset()
    }

    @Test
    fun testProcessText_withValidArabicText_presentsBottomSheet() {
        val sampleArabic = "يمتطي الفارس جواده مسرعاً نحو القرية قاطبة."
        val intent = Intent(ApplicationProvider.getApplicationContext(), ProcessTextActivity::class.java).apply {
            action = Intent.ACTION_PROCESS_TEXT
            type = "text/plain"
            putExtra(Intent.EXTRA_PROCESS_TEXT, sampleArabic)
            putExtra(Intent.EXTRA_PROCESS_TEXT_READONLY, false)
        }

        ActivityScenario.launch<ProcessTextActivity>(intent).use { scenario ->
            scenario.onActivity { activity ->
                assertFalse("Activity must not finish while presenting sheet", activity.isFinishing)

                val fragment = activity.supportFragmentManager.findFragmentByTag(
                    SimplifiedBottomSheetDialogFragment.TAG
                ) as? SimplifiedBottomSheetDialogFragment

                assertNotNull("SimplifiedBottomSheetDialogFragment must be presented", fragment)
                assertEquals(
                    "Extracted Arabic text must match intent extra",
                    sampleArabic,
                    fragment?.arguments?.getString(SimplifiedBottomSheetDialogFragment.ARG_ORIGINAL_TEXT)
                )
                assertEquals(
                    "Read-only flag should propagate false",
                    false,
                    fragment?.arguments?.getBoolean(SimplifiedBottomSheetDialogFragment.ARG_IS_READ_ONLY)
                )
            }
        }
    }

    @Test
    fun testProcessText_withReadOnlyFlag_propagatesToBottomSheetArguments() {
        val sampleArabic = "نص مقروء فقط من صفحة ويب في المتصفح"
        val intent = Intent(ApplicationProvider.getApplicationContext(), ProcessTextActivity::class.java).apply {
            action = Intent.ACTION_PROCESS_TEXT
            type = "text/plain"
            putExtra(Intent.EXTRA_PROCESS_TEXT, sampleArabic)
            putExtra(Intent.EXTRA_PROCESS_TEXT_READONLY, true)
        }

        ActivityScenario.launch<ProcessTextActivity>(intent).use { scenario ->
            scenario.onActivity { activity ->
                val fragment = activity.supportFragmentManager.findFragmentByTag(
                    SimplifiedBottomSheetDialogFragment.TAG
                ) as? SimplifiedBottomSheetDialogFragment

                assertNotNull(fragment)
                assertEquals(
                    "Read-only true flag must be forwarded to bottom sheet bundle",
                    true,
                    fragment?.arguments?.getBoolean(SimplifiedBottomSheetDialogFragment.ARG_IS_READ_ONLY)
                )
            }
        }
    }

    @Test
    fun testProcessText_withoutReadOnlyExtra_defaultsToFalse() {
        val sampleArabic = "نص بدون تحديد قيمة EXTRA_PROCESS_TEXT_READONLY"
        val intent = Intent(ApplicationProvider.getApplicationContext(), ProcessTextActivity::class.java).apply {
            action = Intent.ACTION_PROCESS_TEXT
            type = "text/plain"
            putExtra(Intent.EXTRA_PROCESS_TEXT, sampleArabic)
        }

        ActivityScenario.launch<ProcessTextActivity>(intent).use { scenario ->
            scenario.onActivity { activity ->
                val fragment = activity.supportFragmentManager.findFragmentByTag(
                    SimplifiedBottomSheetDialogFragment.TAG
                ) as? SimplifiedBottomSheetDialogFragment

                assertNotNull(fragment)
                assertEquals(
                    "Omitted EXTRA_PROCESS_TEXT_READONLY must default to false",
                    false,
                    fragment?.arguments?.getBoolean(SimplifiedBottomSheetDialogFragment.ARG_IS_READ_ONLY)
                )
            }
        }
    }

    @Test
    fun testProcessText_emptyString_finishesImmediatelyAndShowsToast() {
        val intent = Intent(ApplicationProvider.getApplicationContext(), ProcessTextActivity::class.java).apply {
            action = Intent.ACTION_PROCESS_TEXT
            type = "text/plain"
            putExtra(Intent.EXTRA_PROCESS_TEXT, "")
        }

        ActivityScenario.launch<ProcessTextActivity>(intent).use { scenario ->
            scenario.onActivity { activity ->
                assertTrue("Activity must finish immediately when EXTRA_PROCESS_TEXT is empty string", activity.isFinishing)

                val fragment = activity.supportFragmentManager.findFragmentByTag(
                    SimplifiedBottomSheetDialogFragment.TAG
                )
                assertNull("No bottom sheet should be launched for empty text", fragment)

                val toastText = ShadowToast.getTextOfLatestToast()
                assertEquals("Warning toast must be shown for empty input", activity.getString(R.string.empty_text_warning), toastText)
            }
        }
    }

    @Test
    fun testProcessText_whitespaceOnly_finishesImmediatelyAndShowsToast() {
        val intent = Intent(ApplicationProvider.getApplicationContext(), ProcessTextActivity::class.java).apply {
            action = Intent.ACTION_PROCESS_TEXT
            type = "text/plain"
            putExtra(Intent.EXTRA_PROCESS_TEXT, "   \n\t  \r  ")
        }

        ActivityScenario.launch<ProcessTextActivity>(intent).use { scenario ->
            scenario.onActivity { activity ->
                assertTrue("Activity must finish immediately when EXTRA_PROCESS_TEXT is whitespace", activity.isFinishing)

                val fragment = activity.supportFragmentManager.findFragmentByTag(
                    SimplifiedBottomSheetDialogFragment.TAG
                )
                assertNull("No bottom sheet should be launched for whitespace text", fragment)
                assertEquals(activity.getString(R.string.empty_text_warning), ShadowToast.getTextOfLatestToast())
            }
        }
    }

    @Test
    fun testProcessText_nullExtra_finishesImmediatelyAndShowsToast() {
        val intent = Intent(ApplicationProvider.getApplicationContext(), ProcessTextActivity::class.java).apply {
            action = Intent.ACTION_PROCESS_TEXT
            type = "text/plain"
            // Intent without EXTRA_PROCESS_TEXT extra
        }

        ActivityScenario.launch<ProcessTextActivity>(intent).use { scenario ->
            scenario.onActivity { activity ->
                assertTrue("Activity must finish immediately when EXTRA_PROCESS_TEXT is null", activity.isFinishing)

                val fragment = activity.supportFragmentManager.findFragmentByTag(
                    SimplifiedBottomSheetDialogFragment.TAG
                )
                assertNull("No bottom sheet should be launched for null text", fragment)
                assertEquals(activity.getString(R.string.empty_text_warning), ShadowToast.getTextOfLatestToast())
            }
        }
    }

    @Test
    fun testProcessText_charSequenceSpannable_extractsPlainText() {
        val spannable = SpannableString("نص عربي مرمز بتنسيق خاص")
        val intent = Intent(ApplicationProvider.getApplicationContext(), ProcessTextActivity::class.java).apply {
            action = Intent.ACTION_PROCESS_TEXT
            type = "text/plain"
            putExtra(Intent.EXTRA_PROCESS_TEXT, spannable)
        }

        ActivityScenario.launch<ProcessTextActivity>(intent).use { scenario ->
            scenario.onActivity { activity ->
                assertFalse(activity.isFinishing)

                val fragment = activity.supportFragmentManager.findFragmentByTag(
                    SimplifiedBottomSheetDialogFragment.TAG
                ) as? SimplifiedBottomSheetDialogFragment

                assertNotNull(fragment)
                assertEquals(
                    "CharSequence text must be converted to String cleanly",
                    "نص عربي مرمز بتنسيق خاص",
                    fragment?.arguments?.getString(SimplifiedBottomSheetDialogFragment.ARG_ORIGINAL_TEXT)
                )
            }
        }
    }

    @Test
    fun testOnDismissedCallback_finishesActivity() {
        val intent = Intent(ApplicationProvider.getApplicationContext(), ProcessTextActivity::class.java).apply {
            action = Intent.ACTION_PROCESS_TEXT
            type = "text/plain"
            putExtra(Intent.EXTRA_PROCESS_TEXT, "نص تجريبي لاختبار الإغلاق")
        }

        ActivityScenario.launch<ProcessTextActivity>(intent).use { scenario ->
            scenario.onActivity { activity ->
                assertFalse("Activity initially not finishing", activity.isFinishing)

                // Trigger onDismissed callback
                activity.onDismissed()

                assertTrue("ProcessTextActivity must call finish() in onDismissed() to release host window", activity.isFinishing)
            }
        }
    }

    @Test
    fun testProcessText_recreatedWithoutExistingSheet_finishesImmediately() {
        val intent = Intent(ApplicationProvider.getApplicationContext(), ProcessTextActivity::class.java).apply {
            action = Intent.ACTION_PROCESS_TEXT
            type = "text/plain"
            putExtra(Intent.EXTRA_PROCESS_TEXT, "نص تجريبي لاختبار استعادة الحالة")
        }

        val savedInstanceState = Bundle().apply {
            putString("dummy_state_key", "dummy_state_val")
        }

        val controller = org.robolectric.Robolectric.buildActivity(ProcessTextActivity::class.java, intent)
        controller.create(savedInstanceState).start().resume()
        val activity = controller.get()

        assertTrue(
            "ProcessTextActivity must call finish() immediately on recreation if existingSheet is null",
            activity.isFinishing
        )
    }

    @Test
    fun testProcessText_recreatedWithExistingSheet_reattachesDismissListenerAndFinishesOnDismiss() {
        val sampleArabic = "نص تجريبي لاختبار تدوير الشاشة"
        val intent = Intent(ApplicationProvider.getApplicationContext(), ProcessTextActivity::class.java).apply {
            action = Intent.ACTION_PROCESS_TEXT
            type = "text/plain"
            putExtra(Intent.EXTRA_PROCESS_TEXT, sampleArabic)
        }

        ActivityScenario.launch<ProcessTextActivity>(intent).use { scenario ->
            scenario.recreate()
            scenario.onActivity { recreatedActivity ->
                assertFalse(
                    "Recreated activity must not finish while sheet is still present",
                    recreatedActivity.isFinishing
                )

                val fragment = recreatedActivity.supportFragmentManager.findFragmentByTag(
                    SimplifiedBottomSheetDialogFragment.TAG
                ) as? SimplifiedBottomSheetDialogFragment

                assertNotNull("Restored bottom sheet fragment must exist in FragmentManager", fragment)

                recreatedActivity.onDismissed()
                assertTrue(
                    "Recreated activity must finish when onDismissed is invoked",
                    recreatedActivity.isFinishing
                )
            }
        }
    }
}
