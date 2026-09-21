package ai.bayan.android

import android.content.Intent
import android.os.Bundle
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import ai.bayan.android.ui.SimplifiedBottomSheetDialogFragment

/**
 * Trampoline activity triggered by Android system text selection action (ACTION_PROCESS_TEXT).
 * Uses a translucent theme to float above host apps without overlay permissions.
 */
class ProcessTextActivity : AppCompatActivity(), SimplifiedBottomSheetDialogFragment.OnDismissListener {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val rawText = intent?.getCharSequenceExtra(Intent.EXTRA_PROCESS_TEXT)?.toString()
        val isReadOnly = intent?.getBooleanExtra(Intent.EXTRA_PROCESS_TEXT_READONLY, false) ?: false

        if (rawText.isNullOrBlank()) {
            Toast.makeText(this, R.string.empty_text_warning, Toast.LENGTH_SHORT).show()
            finish()
            overridePendingTransition(0, 0)
            return
        }

        if (savedInstanceState == null) {
            val sheet = SimplifiedBottomSheetDialogFragment.newInstance(rawText, isReadOnly)
            sheet.setOnDismissListener(this)
            sheet.show(supportFragmentManager, SimplifiedBottomSheetDialogFragment.TAG)
        } else {
            // Re-attach dismiss listener after configuration change, or finish if sheet was destroyed/dismissed
            val existingSheet = supportFragmentManager.findFragmentByTag(
                SimplifiedBottomSheetDialogFragment.TAG
            ) as? SimplifiedBottomSheetDialogFragment
            if (existingSheet != null) {
                existingSheet.setOnDismissListener(this)
            } else {
                finish()
                overridePendingTransition(0, 0)
            }
        }
    }

    override fun onDismissed() {
        finish()
        overridePendingTransition(0, 0)
    }
}

