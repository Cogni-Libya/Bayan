package ai.bayan.android.ui

import android.content.DialogInterface
import android.graphics.text.LineBreaker
import android.os.Build
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.TextView
import androidx.lifecycle.lifecycleScope
import com.google.android.material.bottomsheet.BottomSheetDialogFragment
import ai.bayan.android.R
import ai.bayan.android.engine.SimplificationRequest
import ai.bayan.android.engine.SimplifierProvider
import kotlinx.coroutines.launch

/**
 * Dyslexia-friendly presentation bottom sheet displaying original and simplified Arabic text.
 */
class SimplifiedBottomSheetDialogFragment : BottomSheetDialogFragment() {

    interface OnDismissListener {
        fun onDismissed()
    }

    private var onDismissListener: OnDismissListener? = null
    private var originalText: String = ""
    private var isReadOnly: Boolean = false

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

        val tvOriginalText = view.findViewById<TextView>(R.id.tvOriginalText)
        val tvSimplifiedText = view.findViewById<TextView>(R.id.tvSimplifiedText)
        val btnListen = view.findViewById<Button>(R.id.btnListen)
        val btnCopy = view.findViewById<Button>(R.id.btnCopy)
        val btnSettings = view.findViewById<Button>(R.id.btnSettings)

        // Ensure buttons are disabled per specification
        btnListen?.isEnabled = false
        btnCopy?.isEnabled = false
        btnSettings?.isEnabled = false

        // Display original text
        tvOriginalText?.text = originalText

        // Ensure dyslexia typography settings on tvSimplifiedText
        tvSimplifiedText?.let { tv ->
            tv.lineSpacingMultiplier = 1.6f
            val extraPx = resources.getDimensionPixelSize(R.dimen.dyslexia_line_spacing_extra)
            tv.setLineSpacing(extraPx.toFloat(), 1.6f)
            tv.letterSpacing = 0.04f
            tv.textDirection = View.TEXT_DIRECTION_RTL
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                tv.justificationMode = LineBreaker.JUSTIFICATION_MODE_NONE
            }
        }

        // Asynchronously simplify text
        viewLifecycleOwner.lifecycleScope.launch {
            val simplifier = SimplifierProvider.getInstance()
            val result = simplifier.simplify(SimplificationRequest(originalText = originalText))
            tvSimplifiedText?.text = result.simplifiedText
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

