package ai.bayan.android

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.os.Bundle
import android.widget.Button
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.google.android.material.textfield.TextInputEditText
import com.google.android.material.textfield.TextInputLayout
import ai.bayan.android.engine.SimplifierProvider
import ai.bayan.android.ui.SimplifiedBottomSheetDialogFragment

/**
 * Standalone launcher home activity for testing Arabic text simplification and checking model status.
 */
class MainActivity : AppCompatActivity() {

    private lateinit var tilInputText: TextInputLayout
    private lateinit var etInputText: TextInputEditText
    private lateinit var btnPaste: Button
    private lateinit var btnSimplify: Button
    private lateinit var tvModelStatusName: TextView
    private lateinit var tvModelStatusDesc: TextView
    private lateinit var tvModelStatusSpecs: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        tilInputText = findViewById(R.id.tilInputText)
        etInputText = findViewById(R.id.etInputText)
        btnPaste = findViewById(R.id.btnPaste)
        btnSimplify = findViewById(R.id.btnSimplify)
        tvModelStatusName = findViewById(R.id.tvModelStatusName)
        tvModelStatusDesc = findViewById(R.id.tvModelStatusDesc)
        tvModelStatusSpecs = findViewById(R.id.tvModelStatusSpecs)

        updateModelStatusCard()
        setupListeners()
    }

    private fun updateModelStatusCard() {
        val engineInfo = SimplifierProvider.getInstance().getEngineInfo()
        tvModelStatusName.text = engineInfo.name
        tvModelStatusDesc.text = engineInfo.status
        tvModelStatusSpecs.text = getString(R.string.model_status_specs)
    }

    private fun setupListeners() {
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
}

