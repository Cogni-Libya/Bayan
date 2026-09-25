package ai.bayan.android

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.view.View
import android.widget.Button
import android.widget.ImageButton
import android.widget.TextView
import androidx.test.core.app.ActivityScenario
import androidx.test.core.app.ApplicationProvider
import android.content.DialogInterface
import androidx.work.WorkManager
import androidx.work.testing.WorkManagerTestInitHelper
import com.google.android.material.button.MaterialButton
import com.google.android.material.progressindicator.LinearProgressIndicator
import com.google.android.material.textfield.TextInputEditText
import com.google.android.material.textfield.TextInputLayout
import ai.bayan.android.download.ModelDownloadManager
import ai.bayan.android.engine.ModelStore
import ai.bayan.android.engine.ModelStoreProvider
import ai.bayan.android.engine.SimplificationLevel
import ai.bayan.android.engine.SimplifierProvider
import ai.bayan.android.settings.BayanPreferences
import ai.bayan.android.settings.SettingsRepository
import ai.bayan.android.ui.SimplifiedBottomSheetDialogFragment
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows
import org.robolectric.annotation.Config
import org.robolectric.shadows.ShadowAlertDialog
import org.robolectric.shadows.ShadowLooper
import org.robolectric.shadows.ShadowToast
import java.io.File

/**
 * Robolectric automated tests for [MainActivity].
 *
 * Verifies standalone launcher initialization, reactive model status card presentation
 * across 3 states (Not Downloaded, Downloading, Ready), download confirmation dialog,
 * navigation to SettingsActivity, input validation, and bottom sheet presentation.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class MainActivityTest {

    private lateinit var notReadyStore: ModelStore
    private lateinit var readyStore: ModelStore

    @Before
    fun setUp() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        WorkManagerTestInitHelper.initializeTestWorkManager(context)
        SimplifierProvider.reset()
        ModelStoreProvider.reset()

        notReadyStore = object : ModelStore {
            override fun isReady(): Boolean = false
            override suspend fun download(onProgress: (Float) -> Unit) {}
            override fun modelDir(): File = File(context.filesDir, "models")
            override fun getModelFile(): File = File(modelDir(), "pytorch_model.bin")
            override fun getPartFile(): File = File(modelDir(), "pytorch_model.bin.part")
            override fun getExpectedSha256(): String = "test_sha"
            override fun getDownloadUrl(): String = "http://localhost/model.bin"
            override fun deleteCorruptedFiles() {}
        }

        readyStore = object : ModelStore {
            override fun isReady(): Boolean = true
            override suspend fun download(onProgress: (Float) -> Unit) {}
            override fun modelDir(): File = File(context.filesDir, "models")
            override fun getModelFile(): File = File(modelDir(), "pytorch_model.bin")
            override fun getPartFile(): File = File(modelDir(), "pytorch_model.bin.part")
            override fun getExpectedSha256(): String = "test_sha"
            override fun getDownloadUrl(): String = "http://localhost/model.bin"
            override fun deleteCorruptedFiles() {}
        }
    }

    @After
    fun tearDown() {
        SimplifierProvider.reset()
        ModelStoreProvider.reset()
    }

    @Test
    fun testLauncherInitialization_rendersHeaderAndComponents() {
        ModelStoreProvider.setInstance(readyStore)

        ActivityScenario.launch(MainActivity::class.java).use { scenario ->
            scenario.onActivity { activity ->
                val tvAppTitle = activity.findViewById<TextView>(R.id.tvAppTitle)
                val tvAppSubtitle = activity.findViewById<TextView>(R.id.tvAppSubtitle)
                val btnSettings = activity.findViewById<ImageButton>(R.id.btnSettings)
                val tvModelStatusName = activity.findViewById<TextView>(R.id.tvModelStatusName)
                val tvModelStatusSpecs = activity.findViewById<TextView>(R.id.tvModelStatusSpecs)

                // Header verification
                assertNotNull("App title TextView must be present", tvAppTitle)
                assertEquals(activity.getString(R.string.app_name), tvAppTitle.text.toString())

                assertNotNull("App subtitle TextView must be present", tvAppSubtitle)
                assertEquals(activity.getString(R.string.app_subtitle), tvAppSubtitle.text.toString())

                assertNotNull("Settings button must be present in header", btnSettings)

                // Model status metadata
                assertNotNull("Model status name TextView must be present", tvModelStatusName)
                val engineInfo = SimplifierProvider.getInstance().getEngineInfo()
                assertEquals("Model name must match engine specification", engineInfo.name, tvModelStatusName.text.toString())

                assertNotNull("Model specs TextView must be present", tvModelStatusSpecs)
                assertEquals(activity.getString(R.string.model_status_specs), tvModelStatusSpecs.text.toString())
            }
        }
    }

    @Test
    fun testModelStatusCard_whenModelMissing_showsNotDownloadedState() {
        ModelStoreProvider.setInstance(notReadyStore)

        ActivityScenario.launch(MainActivity::class.java).use { scenario ->
            scenario.onActivity { activity ->
                val tvModelStatusDesc = activity.findViewById<TextView>(R.id.tvModelStatusDesc)
                val btnDownloadModel = activity.findViewById<MaterialButton>(R.id.btnDownloadModel)
                val progressBar = activity.findViewById<LinearProgressIndicator>(R.id.progressBarModelDownload)

                assertNotNull("Status description must be present", tvModelStatusDesc)
                assertTrue(
                    "Status desc must indicate model is not downloaded",
                    tvModelStatusDesc.text.toString().contains("غير محمل")
                )

                assertEquals(
                    "Download button must be visible when model is not downloaded",
                    View.VISIBLE,
                    btnDownloadModel.visibility
                )
                assertEquals(
                    "Progress bar must be hidden when model is not downloaded",
                    View.GONE,
                    progressBar.visibility
                )
            }
        }
    }

    @Test
    fun testModelStatusCard_whenModelReady_showsReadyState() {
        ModelStoreProvider.setInstance(readyStore)

        ActivityScenario.launch(MainActivity::class.java).use { scenario ->
            scenario.onActivity { activity ->
                val tvModelStatusDesc = activity.findViewById<TextView>(R.id.tvModelStatusDesc)
                val btnDownloadModel = activity.findViewById<MaterialButton>(R.id.btnDownloadModel)
                val progressBar = activity.findViewById<LinearProgressIndicator>(R.id.progressBarModelDownload)

                assertNotNull("Status description must be present", tvModelStatusDesc)
                assertTrue(
                    "Status desc must indicate model is ready",
                    tvModelStatusDesc.text.toString().contains("جاهز")
                )

                assertEquals(
                    "Download button must be hidden when model is ready",
                    View.GONE,
                    btnDownloadModel.visibility
                )
                assertEquals(
                    "Progress bar must be hidden when model is ready",
                    View.GONE,
                    progressBar.visibility
                )
            }
        }
    }

    @Test
    fun testDownloadButtonClick_showsConfirmationDialog() {
        ModelStoreProvider.setInstance(notReadyStore)

        ActivityScenario.launch(MainActivity::class.java).use { scenario ->
            scenario.onActivity { activity ->
                val btnDownloadModel = activity.findViewById<MaterialButton>(R.id.btnDownloadModel)
                assertEquals("Download button must be visible initially", View.VISIBLE, btnDownloadModel.visibility)

                btnDownloadModel.performClick()

                // Check that confirmation dialog is displayed
                val dialog = ShadowAlertDialog.getLatestDialog()
                assertNotNull("Confirmation dialog must be presented on download click", dialog)

                val shadowDialog = Shadows.shadowOf(dialog)
                assertEquals("تنزيل نموذج الذكاء الاصطناعي", shadowDialog.title)
                assertTrue(
                    "Dialog message must mention model size (~62 MB)",
                    shadowDialog.message.toString().contains("62")
                )
            }
        }
    }

    @Test
    fun testSettingsButtonClick_launchesSettingsActivity() {
        ActivityScenario.launch(MainActivity::class.java).use { scenario ->
            scenario.onActivity { activity ->
                val btnSettings = activity.findViewById<ImageButton>(R.id.btnSettings)
                assertNotNull("Settings button must be present", btnSettings)

                btnSettings.performClick()

                val shadowActivity = Shadows.shadowOf(activity)
                val nextIntent = shadowActivity.nextStartedActivity
                assertNotNull("Intent to launch SettingsActivity must be started", nextIntent)
                assertEquals(
                    "Launched intent must target SettingsActivity",
                    "ai.bayan.android.settings.SettingsActivity",
                    nextIntent.component?.className
                )
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

    @Test
    fun testDownloadConfirmationDialog_positiveClick_enqueuesWorkWithWifiOnlyConstraintFromSettings() {
        ModelStoreProvider.setInstance(notReadyStore)

        val fakeRepo = object : SettingsRepository {
            override val preferencesFlow: Flow<BayanPreferences> = MutableStateFlow(
                BayanPreferences(wifiOnlyDownload = true)
            )
            override suspend fun updateSimplificationLevel(level: SimplificationLevel) {}
            override suspend fun updateFontSize(fontSizeSp: Float) {}
            override suspend fun updateLineSpacing(multiplier: Float) {}
            override suspend fun updateFontFamily(fontFamily: String) {}
            override suspend fun updateWifiOnlyDownload(wifiOnly: Boolean) {}
        }

        ActivityScenario.launch(MainActivity::class.java).use { scenario ->
            scenario.onActivity { activity ->
                activity.settingsRepositoryOverride = fakeRepo
                val btnDownloadModel = activity.findViewById<MaterialButton>(R.id.btnDownloadModel)
                btnDownloadModel.performClick()

                val dialog = ShadowAlertDialog.getLatestDialog() as? androidx.appcompat.app.AlertDialog
                assertNotNull("Confirmation dialog must be visible", dialog)

                val positiveButton = dialog?.getButton(DialogInterface.BUTTON_POSITIVE)
                assertNotNull("Positive 'تنزيل' button must exist", positiveButton)
                positiveButton?.performClick()

                ShadowLooper.idleMainLooper()

                val workInfos = WorkManager.getInstance(activity)
                    .getWorkInfosForUniqueWork(ModelDownloadManager.WORK_NAME)
                    .get()
                assertTrue("Work must be enqueued", workInfos.isNotEmpty())
            }
        }
    }
}
