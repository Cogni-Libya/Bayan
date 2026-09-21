package ai.bayan.android

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.widget.Button
import android.widget.TextView
import androidx.test.core.app.ActivityScenario
import com.google.android.material.textfield.TextInputEditText
import com.google.android.material.textfield.TextInputLayout
import ai.bayan.android.engine.SimplifierProvider
import ai.bayan.android.ui.SimplifiedBottomSheetDialogFragment
import org.junit.After
import org.junit.Assert.assertEquals
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
 * Robolectric automated tests for [MainActivity].
 *
 * Verifies standalone launcher initialization, ONNX model status card presentation,
 * input box validation (empty/whitespace rejection), clipboard paste functionality,
 * and presentation of [SimplifiedBottomSheetDialogFragment] with user-entered Arabic text.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class MainActivityTest {

    @Before
    fun setUp() {
        SimplifierProvider.reset()
    }

    @After
    fun tearDown() {
        SimplifierProvider.reset()
    }

    @Test
    fun testLauncherInitialization_rendersHeaderAndModelStatusCard() {
        ActivityScenario.launch(MainActivity::class.java).use { scenario ->
            scenario.onActivity { activity ->
                val tvAppTitle = activity.findViewById<TextView>(R.id.tvAppTitle)
                val tvAppSubtitle = activity.findViewById<TextView>(R.id.tvAppSubtitle)
                val tvModelStatusName = activity.findViewById<TextView>(R.id.tvModelStatusName)
                val tvModelStatusDesc = activity.findViewById<TextView>(R.id.tvModelStatusDesc)
                val tvModelStatusSpecs = activity.findViewById<TextView>(R.id.tvModelStatusSpecs)

                // Header verification
                assertNotNull("App title TextView must be present", tvAppTitle)
                assertEquals(activity.getString(R.string.app_name), tvAppTitle.text.toString())

                assertNotNull("App subtitle TextView must be present", tvAppSubtitle)
                assertEquals(activity.getString(R.string.app_subtitle), tvAppSubtitle.text.toString())

                // Model status card verification
                assertNotNull("Model status name TextView must be present", tvModelStatusName)
                val engineInfo = SimplifierProvider.getInstance().getEngineInfo()
                assertEquals("Model name must match engine specification", engineInfo.name, tvModelStatusName.text.toString())

                assertNotNull("Model status desc TextView must be present", tvModelStatusDesc)
                assertEquals("Model status must report ready state", engineInfo.status, tvModelStatusDesc.text.toString())

                assertNotNull("Model specs TextView must be present", tvModelStatusSpecs)
                assertEquals(activity.getString(R.string.model_status_specs), tvModelStatusSpecs.text.toString())
            }
        }
    }

    @Test
    fun testInputBoxValidation_emptyText_showsErrorAndDoesNotLaunchSheet() {
        ActivityScenario.launch(MainActivity::class.java).use { scenario ->
            scenario.onActivity { activity ->
                val tilInputText = activity.findViewById<TextInputLayout>(R.id.tilInputText)
                val etInputText = activity.findViewById<TextInputEditText>(R.id.etInputText)
                val btnSimplify = activity.findViewById<Button>(R.id.btnSimplify)

                etInputText.setText("")
                btnSimplify.performClick()

                // Verify validation error
                assertNotNull("Error message must be set on TextInputLayout", tilInputText.error)
                assertEquals(activity.getString(R.string.empty_text_warning), tilInputText.error.toString())

                // Verify bottom sheet is NOT presented
                val sheet = activity.supportFragmentManager.findFragmentByTag(
                    SimplifiedBottomSheetDialogFragment.TAG
                )
                assertNull("Bottom sheet must NOT launch on empty input submission", sheet)
            }
        }
    }

    @Test
    fun testInputBoxValidation_whitespaceOnly_showsErrorAndDoesNotLaunchSheet() {
        ActivityScenario.launch(MainActivity::class.java).use { scenario ->
            scenario.onActivity { activity ->
                val tilInputText = activity.findViewById<TextInputLayout>(R.id.tilInputText)
                val etInputText = activity.findViewById<TextInputEditText>(R.id.etInputText)
                val btnSimplify = activity.findViewById<Button>(R.id.btnSimplify)

                etInputText.setText("     \n\t   ")
                btnSimplify.performClick()

                assertNotNull("Error must be set on whitespace submission", tilInputText.error)
                assertEquals(activity.getString(R.string.empty_text_warning), tilInputText.error.toString())

                val sheet = activity.supportFragmentManager.findFragmentByTag(
                    SimplifiedBottomSheetDialogFragment.TAG
                )
                assertNull("Bottom sheet must NOT launch on whitespace submission", sheet)
            }
        }
    }

    @Test
    fun testValidArabicTextSubmission_launchesSimplifiedBottomSheet() {
        ActivityScenario.launch(MainActivity::class.java).use { scenario ->
            scenario.onActivity { activity ->
                val tilInputText = activity.findViewById<TextInputLayout>(R.id.tilInputText)
                val etInputText = activity.findViewById<TextInputEditText>(R.id.etInputText)
                val btnSimplify = activity.findViewById<Button>(R.id.btnSimplify)

                val sampleText = "يبتغي القارئ فهماً أعمق للنص العربي."
                etInputText.setText(sampleText)
                btnSimplify.performClick()

                // Verify error is cleared
                assertNull("Error must be cleared on valid submission", tilInputText.error)

                // Verify bottom sheet is presented with the entered text
                val sheet = activity.supportFragmentManager.findFragmentByTag(
                    SimplifiedBottomSheetDialogFragment.TAG
                ) as? SimplifiedBottomSheetDialogFragment

                assertNotNull("SimplifiedBottomSheetDialogFragment must be presented", sheet)
                assertEquals(
                    "Bottom sheet arguments must contain user entered text",
                    sampleText,
                    sheet?.arguments?.getString(SimplifiedBottomSheetDialogFragment.ARG_ORIGINAL_TEXT)
                )
                assertEquals(
                    "Launcher bottom sheet isReadOnly should be false",
                    false,
                    sheet?.arguments?.getBoolean(SimplifiedBottomSheetDialogFragment.ARG_IS_READ_ONLY)
                )
            }
        }
    }

    @Test
    fun testPasteButton_retrievesFromClipboardAndPopulatesInput() {
        ActivityScenario.launch(MainActivity::class.java).use { scenario ->
            scenario.onActivity { activity ->
                val tilInputText = activity.findViewById<TextInputLayout>(R.id.tilInputText)
                val etInputText = activity.findViewById<TextInputEditText>(R.id.etInputText)
                val btnPaste = activity.findViewById<Button>(R.id.btnPaste)

                // Populate system clipboard with test Arabic text
                val clipboard = activity.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                val clipboardText = "نص منسوخ من الحافظة لتجربة التبسيط المباشر"
                clipboard.setPrimaryClip(ClipData.newPlainText("bayan_test", clipboardText))

                // Simulate paste button click
                btnPaste.performClick()

                // Verify text populated in EditText
                assertEquals("Input EditText must contain pasted text", clipboardText, etInputText.text.toString())
                assertEquals("Cursor must be positioned at end of pasted text", clipboardText.length, etInputText.selectionStart)
                assertNull("Error should be cleared after pasting", tilInputText.error)
            }
        }
    }

    @Test
    fun testPasteButton_emptyClipboard_showsWarningToast() {
        ActivityScenario.launch(MainActivity::class.java).use { scenario ->
            scenario.onActivity { activity ->
                val etInputText = activity.findViewById<TextInputEditText>(R.id.etInputText)
                val btnPaste = activity.findViewById<Button>(R.id.btnPaste)

                // Setup clipboard with whitespace/empty content
                val clipboard = activity.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                clipboard.setPrimaryClip(ClipData.newPlainText("empty", "   "))

                btnPaste.performClick()

                val toastText = ShadowToast.getTextOfLatestToast()
                assertEquals(
                    "Warning toast must notify user when clipboard is empty",
                    activity.getString(R.string.clipboard_empty_warning),
                    toastText
                )
                assertEquals("EditText should remain blank", "", etInputText.text.toString())
            }
        }
    }
}
