package ai.bayan.android.ui

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.DialogInterface
import android.content.Intent
import android.graphics.Typeface
import android.graphics.text.LineBreaker
import android.os.Build
import android.os.Bundle
import android.util.TypedValue
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.TextView
import android.widget.Toast
import androidx.core.content.res.ResourcesCompat
import androidx.lifecycle.lifecycleScope
import androidx.work.WorkInfo
import com.google.android.material.bottomsheet.BottomSheetDialogFragment
import com.google.android.material.button.MaterialButton
import com.google.android.material.progressindicator.LinearProgressIndicator
import ai.bayan.android.R
import ai.bayan.android.download.DownloadModelWorker
import ai.bayan.android.download.ModelDownloadManager
import ai.bayan.android.engine.ModelStore
import ai.bayan.android.engine.ModelStoreProvider
import ai.bayan.android.engine.SimplificationRequest
import ai.bayan.android.engine.SimplifierProvider
import ai.bayan.android.engine.TextSimplifier
import ai.bayan.android.settings.BayanPreferences
import ai.bayan.android.settings.SettingsRepository
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch

/**
 * Dyslexia-friendly presentation bottom sheet displaying original and simplified Arabic text,
 * governed by a reactive [SheetState] state machine.
 */
class SimplifiedBottomSheetDialogFragment : BottomSheetDialogFragment() {

    interface OnDismissListener {
        fun onDismissed()
    }

    private var onDismissListener: OnDismissListener? = null
    private var originalText: String = ""
    private var isReadOnly: Boolean = false

    // State machine tracking
    var currentState: SheetState = SheetState.Loading
        private set

    var currentPreferences: BayanPreferences = BayanPreferences()
        private set

    // Injection points for unit and Robolectric tests
    internal var modelStoreOverride: ModelStore? = null
    internal var settingsRepositoryOverride: SettingsRepository? = null
    internal var simplifierOverride: TextSimplifier? = null
    internal var downloadManagerOverride: ModelDownloadManager? = null

    private val modelStore: ModelStore
        get() = modelStoreOverride ?: ModelStoreProvider.getInstance(requireContext())

    private val settingsRepository: SettingsRepository
        get() = settingsRepositoryOverride ?: SettingsRepository.getInstance(requireContext())

    private val simplifier: TextSimplifier
        get() = simplifierOverride ?: SimplifierProvider.getInstance()

    private val downloadManager: ModelDownloadManager
        get() = downloadManagerOverride ?: ModelDownloadManager.getInstance(requireContext())

    // View references
    private lateinit var layoutNeedsModel: View
    private lateinit var layoutLoading: View
    private lateinit var layoutResult: View
    private lateinit var layoutError: View

    private lateinit var tvNeedsModelPrompt: TextView
    private lateinit var btnDownloadModel: MaterialButton

    private var progressBarLoading: LinearProgressIndicator? = null
    private var tvLoadingStatus: TextView? = null

    private lateinit var btnToggleText: MaterialButton
    private lateinit var tvLargeLabel: TextView
    private lateinit var tvLargeText: TextView
    private var tvSimplifiedText: TextView? = null
    private lateinit var tvMutedLabel: TextView
    private lateinit var tvMutedText: TextView

    private lateinit var tvErrorMessage: TextView
    private lateinit var tvOriginalText: TextView

    private lateinit var layoutControlRow: View
    private lateinit var btnListen: Button
    private lateinit var btnCopy: Button
    private lateinit var btnSettings: Button
    private lateinit var tvDisabledNotice: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        originalText = arguments?.getString(ARG_ORIGINAL_TEXT).orEmpty()
        isReadOnly = arguments?.getBoolean(ARG_IS_READ_ONLY, false) ?: false
    }

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View? {
        return inflater.inflate(R.layout.fragment_bottom_sheet, container, false)
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        bindViews(view)
        setupListeners()

        // Populate initial original text values immediately
        tvOriginalText.text = originalText
        tvMutedText.text = originalText
        tvLargeText.text = originalText

        // Apply initial dyslexia typography with defaults
        applyDyslexiaTypography(tvLargeText, currentPreferences)
        tvSimplifiedText?.let { applyDyslexiaTypography(it, currentPreferences) }

        // Start collecting preferences reactively
        observePreferences()

        // Observe background model download status to auto-transition when ready
        observeModelDownloadStatus()

        // Evaluate model readiness and transition to initial state
        if (!modelStore.isReady()) {
            render(SheetState.NeedsModel())
        } else {
            render(SheetState.Loading)
            startSimplification()
        }
    }

    private fun bindViews(view: View) {
        layoutNeedsModel = view.findViewById(R.id.layoutNeedsModel)
        layoutLoading = view.findViewById(R.id.layoutLoading)
        layoutResult = view.findViewById(R.id.layoutResult)
        layoutError = view.findViewById(R.id.layoutError)

        tvNeedsModelPrompt = view.findViewById(R.id.tvNeedsModelPrompt)
        btnDownloadModel = view.findViewById(R.id.btnDownloadModel)

        progressBarLoading = view.findViewById(R.id.progressBarLoading)
        tvLoadingStatus = view.findViewById(R.id.tvLoadingStatus)

        btnToggleText = view.findViewById(R.id.btnToggleText)
        tvLargeLabel = view.findViewById(R.id.tvLargeLabel)
        tvLargeText = view.findViewById(R.id.tvLargeText)
        tvSimplifiedText = view.findViewById(R.id.tvSimplifiedText)
        tvMutedLabel = view.findViewById(R.id.tvMutedLabel)
        tvMutedText = view.findViewById(R.id.tvMutedText)

        tvErrorMessage = view.findViewById(R.id.tvErrorMessage)
        tvOriginalText = view.findViewById(R.id.tvOriginalText)

        layoutControlRow = view.findViewById(R.id.layoutControlRow)
        btnListen = view.findViewById(R.id.btnListen)
        btnCopy = view.findViewById(R.id.btnCopy)
        btnSettings = view.findViewById(R.id.btnSettings)
        tvDisabledNotice = view.findViewById(R.id.tvDisabledNotice)
    }

    private fun setupListeners() {
        btnDownloadModel.setOnClickListener {
            btnDownloadModel.isEnabled = false
            btnDownloadModel.text = "جاري التنزيل..."
            ModelDownloadManager.enqueueModelDownload(
                requireContext(),
                wifiOnly = currentPreferences.wifiOnlyDownload
            )
            Toast.makeText(requireContext(), "جاري بدء تنزيل النموذج...", Toast.LENGTH_SHORT).show()
        }

        btnToggleText.setOnClickListener {
            val state = currentState
            if (state is SheetState.Result) {
                render(state.copy(isShowingSimplifiedLarge = !state.isShowingSimplifiedLarge))
            }
        }

        btnCopy.setOnClickListener {
            val state = currentState
            if (state is SheetState.Result) {
                val textToCopy = if (state.isShowingSimplifiedLarge) {
                    state.simplifiedText
                } else {
                    state.originalText
                }
                val clipboard = requireContext().getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                val clip = ClipData.newPlainText("Bayan Active Text", textToCopy)
                clipboard.setPrimaryClip(clip)
                Toast.makeText(requireContext(), "تم نسخ النص إلى الحافظة", Toast.LENGTH_SHORT).show()
            }
        }

        btnSettings.setOnClickListener {
            val intent = Intent().setClassName(requireContext(), "ai.bayan.android.settings.SettingsActivity")
            startActivity(intent)
        }
    }

    private fun observePreferences() {
        viewLifecycleOwner.lifecycleScope.launch {
            settingsRepository.preferencesFlow.collect { prefs ->
                currentPreferences = prefs
                val state = currentState
                if (state is SheetState.Result) {
                    applyDyslexiaTypography(tvLargeText, prefs)
                    tvSimplifiedText?.let { applyDyslexiaTypography(it, prefs) }
                }
            }
        }
    }

    private fun observeModelDownloadStatus() {
        downloadManager.getWorkInfosLiveData().observe(viewLifecycleOwner) { workInfos ->
            if (currentState is SheetState.NeedsModel) {
                val isSucceeded = workInfos.any { it.state == WorkInfo.State.SUCCEEDED }
                if (isSucceeded && modelStore.isReady()) {
                    render(SheetState.Loading)
                    startSimplification()
                } else {
                    val activeWork = workInfos.find { !it.state.isFinished }
                    if (activeWork != null) {
                        val progress = activeWork.progress.getInt(DownloadModelWorker.KEY_PROGRESS, 0)
                        btnDownloadModel.isEnabled = false
                        btnDownloadModel.text = if (progress > 0) "جاري التنزيل ($progress%)..." else "جاري التنزيل..."
                    } else {
                        btnDownloadModel.isEnabled = true
                        btnDownloadModel.text = "تنزيل"
                    }
                }
            }
        }
    }

    private fun startSimplification() {
        viewLifecycleOwner.lifecycleScope.launch {
            try {
                val prefs = settingsRepository.preferencesFlow.first()
                currentPreferences = prefs

                val request = SimplificationRequest(
                    originalText = originalText,
                    targetLevel = prefs.simplificationLevel
                )
                val result = simplifier.simplify(request)
                if (result.isSuccess) {
                    render(
                        SheetState.Result(
                            originalText = originalText,
                            simplifiedText = result.simplifiedText,
                            isShowingSimplifiedLarge = true
                        )
                    )
                } else {
                    render(
                        SheetState.Error(
                            originalText = originalText,
                            errorMessage = result.errorMessage ?: "تعذر تبسيط النص حالياً، يرجى المحاولة لاحقاً."
                        )
                    )
                }
            } catch (t: Throwable) {
                render(
                    SheetState.Error(
                        originalText = originalText,
                        errorMessage = t.localizedMessage ?: "تعذر تبسيط النص حالياً، يرجى المحاولة لاحقاً."
                    )
                )
            }
        }
    }

    /**
     * Declarative single rendering function driving bottom sheet visibility, content binding,
     * typography, and button states strictly from [SheetState].
     */
    fun render(state: SheetState) {
        this.currentState = state

        // State container visibility toggles
        layoutNeedsModel.visibility = if (state is SheetState.NeedsModel) View.VISIBLE else View.GONE
        layoutLoading.visibility = if (state is SheetState.Loading) View.VISIBLE else View.GONE
        layoutResult.visibility = if (state is SheetState.Result) View.VISIBLE else View.GONE
        layoutError.visibility = if (state is SheetState.Error) View.VISIBLE else View.GONE

        when (state) {
            is SheetState.NeedsModel -> {
                state.message?.let { tvNeedsModelPrompt.text = it }
                btnListen.isEnabled = false
                btnCopy.isEnabled = false
                btnSettings.isEnabled = true
            }

            is SheetState.Loading -> {
                btnListen.isEnabled = false
                btnCopy.isEnabled = false
                btnSettings.isEnabled = false
            }

            is SheetState.Result -> {
                btnListen.isEnabled = false
                btnCopy.isEnabled = true
                btnSettings.isEnabled = true

                val activeEnlarged = if (state.isShowingSimplifiedLarge) state.simplifiedText else state.originalText
                val activeMuted = if (state.isShowingSimplifiedLarge) state.originalText else state.simplifiedText

                tvLargeText.text = activeEnlarged
                tvLargeLabel.text = if (state.isShowingSimplifiedLarge) {
                    getString(R.string.simplified_text_title)
                } else {
                    getString(R.string.original_text_title)
                }

                tvMutedText.text = activeMuted
                tvMutedLabel.text = if (state.isShowingSimplifiedLarge) {
                    getString(R.string.original_text_title)
                } else {
                    getString(R.string.simplified_text_title)
                }

                // Preserve legacy bindings for compatibility
                tvSimplifiedText?.text = state.simplifiedText
                tvOriginalText.text = state.originalText

                applyDyslexiaTypography(tvLargeText, currentPreferences)
                tvSimplifiedText?.let { applyDyslexiaTypography(it, currentPreferences) }
            }

            is SheetState.Error -> {
                tvErrorMessage.text = state.errorMessage
                // Crucial requirement: Original captured Arabic text is preserved and readable
                tvOriginalText.text = state.originalText
                btnListen.isEnabled = false
                btnCopy.isEnabled = false
                btnSettings.isEnabled = true
            }
        }
    }

    /**
     * Dynamically applies dyslexia accessibility typography according to user preferences.
     */
    private fun applyDyslexiaTypography(textView: TextView, preferences: BayanPreferences) {
        val context = context ?: return

        // 1. Font Family / Typeface
        val fontResId = if (preferences.fontFamily == BayanPreferences.FONT_FAMILY_NOTO_SANS) {
            R.font.noto_sans_arabic
        } else {
            R.font.noto_naskh_arabic
        }
        val typeface = try {
            ResourcesCompat.getFont(context, fontResId)
        } catch (e: Exception) {
            Typeface.DEFAULT
        }
        if (typeface != null) {
            textView.typeface = typeface
        }

        // 2. Font Size (in sp)
        textView.setTextSize(TypedValue.COMPLEX_UNIT_SP, preferences.fontSizeSp)

        // 3. Line Spacing Multiplier & Extra
        val extraPx = try {
            resources.getDimensionPixelSize(R.dimen.dyslexia_line_spacing_extra)
        } catch (e: Exception) {
            0
        }
        textView.setLineSpacing(extraPx.toFloat(), preferences.lineSpacingMultiplier)

        // 4. Letter Spacing (0.04f)
        textView.letterSpacing = 0.04f

        // 5. Right-To-Left Text Direction
        textView.textDirection = View.TEXT_DIRECTION_RTL

        // 6. Unjustified Text Flow (eliminates kashida rivers)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            textView.justificationMode = LineBreaker.JUSTIFICATION_MODE_NONE
        }
    }

    fun setOnDismissListener(listener: OnDismissListener) {
        this.onDismissListener = listener
    }

    override fun onDismiss(dialog: DialogInterface) {
        super.onDismiss(dialog)
        onDismissListener?.onDismissed()
    }

    companion object {
        const val TAG = "SimplifiedBottomSheetDialogFragment"
        const val ARG_ORIGINAL_TEXT = "arg_original_text"
        const val ARG_IS_READ_ONLY = "arg_is_read_only"

        fun newBundle(text: String, isReadOnly: Boolean = false): Bundle {
            return Bundle().apply {
                putString(ARG_ORIGINAL_TEXT, text)
                putBoolean(ARG_IS_READ_ONLY, isReadOnly)
            }
        }

        fun newInstance(text: String, isReadOnly: Boolean = false): SimplifiedBottomSheetDialogFragment {
            return SimplifiedBottomSheetDialogFragment().apply {
                arguments = newBundle(text, isReadOnly)
            }
        }
    }
}
