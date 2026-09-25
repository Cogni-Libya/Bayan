package ai.bayan.android

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.view.View
import android.widget.Button
import android.widget.ImageButton
import android.widget.ImageView
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import androidx.work.WorkInfo
import com.google.android.material.button.MaterialButton
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import com.google.android.material.progressindicator.LinearProgressIndicator
import com.google.android.material.textfield.TextInputEditText
import com.google.android.material.textfield.TextInputLayout
import ai.bayan.android.download.DownloadModelWorker
import ai.bayan.android.download.ModelDownloadManager
import ai.bayan.android.engine.ModelStoreProvider
import ai.bayan.android.engine.SimplifierProvider
import ai.bayan.android.settings.SettingsRepository
import ai.bayan.android.ui.SimplifiedBottomSheetDialogFragment
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch

/**
 * Standalone launcher home activity for testing Arabic text simplification,
 * managing AI model downloads via WorkManager, and adjusting dyslexia preferences.
 */
class MainActivity : AppCompatActivity() {

    private lateinit var tilInputText: TextInputLayout
    private lateinit var etInputText: TextInputEditText
    private lateinit var btnPaste: Button
    private lateinit var btnSimplify: Button
    private lateinit var tvModelStatusName: TextView
    private lateinit var tvModelStatusDesc: TextView
    private lateinit var tvModelStatusSpecs: TextView
    private lateinit var ivStatusIcon: ImageView
    private lateinit var progressBarModelDownload: LinearProgressIndicator
    private lateinit var btnDownloadModel: MaterialButton
    private lateinit var btnSettings: ImageButton

    private lateinit var downloadManager: ModelDownloadManager

    internal var settingsRepositoryOverride: SettingsRepository? = null

    private val settingsRepository: SettingsRepository
        get() = settingsRepositoryOverride ?: SettingsRepository.getInstance(this)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        downloadManager = ModelDownloadManager.getInstance(this)

        tilInputText = findViewById(R.id.tilInputText)
        etInputText = findViewById(R.id.etInputText)
        btnPaste = findViewById(R.id.btnPaste)
        btnSimplify = findViewById(R.id.btnSimplify)
        tvModelStatusName = findViewById(R.id.tvModelStatusName)
        tvModelStatusDesc = findViewById(R.id.tvModelStatusDesc)
        tvModelStatusSpecs = findViewById(R.id.tvModelStatusSpecs)
        ivStatusIcon = findViewById(R.id.ivStatusIcon)
        progressBarModelDownload = findViewById(R.id.progressBarModelDownload)
        btnDownloadModel = findViewById(R.id.btnDownloadModel)
        btnSettings = findViewById(R.id.btnSettings)

        setupListeners()
        observeDownloadStatus()
        updateModelStatusCard()
    }

    override fun onResume() {
        super.onResume()
        updateModelStatusCard()
    }

    private fun observeDownloadStatus() {
        downloadManager.getWorkInfosLiveData().observe(this) { workInfos ->
            updateModelStatusCard(workInfos)
        }
    }

    /**
     * Updates the status card to render one of three states:
     * 1. Ready: Model file exists and checksum verified.
     * 2. Downloading: WorkManager task is currently running or enqueued.
     * 3. Not Downloaded: Model file is missing or corrupted.
     */
    fun updateModelStatusCard(workInfos: List<WorkInfo>? = null) {
        val modelStore = ModelStoreProvider.getInstance(this)
        val isReady = modelStore.isReady()

        val engineInfo = SimplifierProvider.getInstance().getEngineInfo()
        tvModelStatusName.text = engineInfo.name
        tvModelStatusSpecs.text = getString(R.string.model_status_specs)

        if (isReady) {
            // State: Ready
            tvModelStatusDesc.text = getString(R.string.model_status_ready)
            tvModelStatusDesc.setTextColor(ContextCompat.getColor(this, R.color.bayan_status_green))
            ivStatusIcon.setImageResource(R.drawable.ic_status_ready)
            progressBarModelDownload.visibility = View.GONE
            btnDownloadModel.visibility = View.GONE
            return
        }

        // Check if there is an active downloading work
        val activeWork = workInfos?.find { !it.state.isFinished }
        if (activeWork != null) {
            // State: Downloading
            val progress = activeWork.progress.getInt(DownloadModelWorker.KEY_PROGRESS, 0)
            if (progress > 0) {
                tvModelStatusDesc.text = "جاري التنزيل: $progress%"
                progressBarModelDownload.isIndeterminate = false
                progressBarModelDownload.progress = progress
            } else {
                tvModelStatusDesc.text = "جاري بدء التنزيل..."
                progressBarModelDownload.isIndeterminate = true
            }
            tvModelStatusDesc.setTextColor(ContextCompat.getColor(this, R.color.bayan_primary))
            progressBarModelDownload.visibility = View.VISIBLE
            btnDownloadModel.visibility = View.GONE
            return
        }

        // State: Not Downloaded
        tvModelStatusDesc.text = "النموذج غير محمل (يلزم التنزيل للعمل دون إنترنت)"
        tvModelStatusDesc.setTextColor(ContextCompat.getColor(this, R.color.bayan_text_muted))
        progressBarModelDownload.visibility = View.GONE
        btnDownloadModel.visibility = View.VISIBLE
    }

    private fun setupListeners() {
        btnSettings.setOnClickListener {
            navigateToSettings()
        }

        btnDownloadModel.setOnClickListener {
            showDownloadConfirmationDialog()
        }

        btnPaste.setOnClickListener {
            val clipboard = getSystemService(Context.CLIPBOARD_SERVICE) as? ClipboardManager
            val clip = clipboard?.primaryClip
            if (clip != null && clip.itemCount > 0) {
                val item = clip.getItemAt(0)
                val text = item.coerceToText(this).toString()
                if (text.isNotBlank()) {
                    etInputText.setText(text)
                    etInputText.setSelection(text.length)
                    tilInputText.error = null
                } else {
                    Toast.makeText(this, R.string.clipboard_empty_warning, Toast.LENGTH_SHORT).show()
                }
            } else {
                Toast.makeText(this, R.string.clipboard_empty_warning, Toast.LENGTH_SHORT).show()
            }
        }

        btnSimplify.setOnClickListener {
            val text = etInputText.text?.toString()?.trim().orEmpty()
            if (text.isEmpty()) {
                tilInputText.error = getString(R.string.empty_text_warning)
                return@setOnClickListener
            }

            tilInputText.error = null
            val sheet = SimplifiedBottomSheetDialogFragment.newInstance(text, isReadOnly = false)
            sheet.show(supportFragmentManager, SimplifiedBottomSheetDialogFragment.TAG)
        }
    }

    private fun showDownloadConfirmationDialog() {
        MaterialAlertDialogBuilder(this)
            .setTitle("تنزيل نموذج الذكاء الاصطناعي")
            .setMessage("حجم النموذج ~62 ميجابايت (62,321,434 بايت). هل ترغب في بدء التنزيل الآن؟")
            .setPositiveButton("تنزيل") { _, _ ->
                lifecycleScope.launch {
                    val wifiOnly = settingsRepository.preferencesFlow.first().wifiOnlyDownload
                    ModelDownloadManager.enqueueModelDownload(this@MainActivity, wifiOnly)
                    updateModelStatusCard()
                }
            }
            .setNegativeButton("إلغاء", null)
            .show()
    }

    private fun navigateToSettings() {
        val intent = Intent().setClassName(this, "ai.bayan.android.settings.SettingsActivity")
        startActivity(intent)
    }
}
