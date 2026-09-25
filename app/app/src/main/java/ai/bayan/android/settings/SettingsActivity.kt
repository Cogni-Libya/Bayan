package ai.bayan.android.settings

import android.graphics.Typeface
import android.os.Bundle
import android.util.TypedValue
import android.widget.RadioButton
import android.widget.RadioGroup
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.res.ResourcesCompat
import androidx.lifecycle.lifecycleScope
import com.google.android.material.appbar.MaterialToolbar
import com.google.android.material.materialswitch.MaterialSwitch
import com.google.android.material.slider.Slider
import ai.bayan.android.R
import ai.bayan.android.engine.SimplificationLevel
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import java.util.Locale

/**
 * Dedicated settings screen tailored for dyslexic readers and general accessibility,
 * persisting user typography preferences and download constraints via DataStore.
 */
class SettingsActivity : AppCompatActivity() {

    private lateinit var toolbar: MaterialToolbar
    private lateinit var tvPreviewText: TextView

    private lateinit var rgSimplificationStrength: RadioGroup
    private lateinit var rbStrengthLight: RadioButton
    private lateinit var rbStrengthMedium: RadioButton
    private lateinit var rbStrengthStrong: RadioButton

    private lateinit var tvFontSizeValue: TextView
    private lateinit var sliderFontSize: Slider

    private lateinit var tvLineSpacingValue: TextView
    private lateinit var sliderLineSpacing: Slider

    private lateinit var rgFontFamily: RadioGroup
    private lateinit var rbFontNotoNaskh: RadioButton
    private lateinit var rbFontNotoSans: RadioButton

    private lateinit var switchWifiOnly: MaterialSwitch

    internal var settingsRepository: SettingsRepository? = null

    private val repository: SettingsRepository
        get() = settingsRepository ?: SettingsRepository.getInstance(this)

    private var isUpdatingFromFlow = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_settings)

        bindViews()
        setupToolbar()
        setupListeners()
        observePreferences()
    }

    private fun bindViews() {
        toolbar = findViewById(R.id.toolbarSettings)
        tvPreviewText = findViewById(R.id.tvPreviewText)

        rgSimplificationStrength = findViewById(R.id.rgSimplificationStrength)
        rbStrengthLight = findViewById(R.id.rbStrengthLight)
        rbStrengthMedium = findViewById(R.id.rbStrengthMedium)
        rbStrengthStrong = findViewById(R.id.rbStrengthStrong)

        tvFontSizeValue = findViewById(R.id.tvFontSizeValue)
        sliderFontSize = findViewById(R.id.sliderFontSize)

        tvLineSpacingValue = findViewById(R.id.tvLineSpacingValue)
        sliderLineSpacing = findViewById(R.id.sliderLineSpacing)

        rgFontFamily = findViewById(R.id.rgFontFamily)
        rbFontNotoNaskh = findViewById(R.id.rbFontNotoNaskh)
        rbFontNotoSans = findViewById(R.id.rbFontNotoSans)

        switchWifiOnly = findViewById(R.id.switchWifiOnly)
    }

    private fun setupToolbar() {
        toolbar.setNavigationOnClickListener {
            finish()
        }
    }

    private fun setupListeners() {
        rgSimplificationStrength.setOnCheckedChangeListener { _, checkedId ->
            if (isUpdatingFromFlow) return@setOnCheckedChangeListener
            val level = when (checkedId) {
                R.id.rbStrengthLight -> SimplificationLevel.ADVANCED
                R.id.rbStrengthStrong -> SimplificationLevel.ELEMENTARY
                else -> SimplificationLevel.STANDARD
            }
            lifecycleScope.launch {
                repository.updateSimplificationLevel(level)
            }
        }

        sliderFontSize.addOnChangeListener { _, value, fromUser ->
            tvFontSizeValue.text = "${value.toInt()} sp"
            updatePreviewTypography(fontSizeSp = value)
            if (fromUser) {
                lifecycleScope.launch {
                    repository.updateFontSize(value)
                }
            }
        }

        sliderLineSpacing.addOnChangeListener { _, value, fromUser ->
            tvLineSpacingValue.text = String.format(Locale.US, "%.1fx", value)
            updatePreviewTypography(lineSpacingMultiplier = value)
            if (fromUser) {
                lifecycleScope.launch {
                    repository.updateLineSpacing(value)
                }
            }
        }

        rgFontFamily.setOnCheckedChangeListener { _, checkedId ->
            if (isUpdatingFromFlow) return@setOnCheckedChangeListener
            val family = if (checkedId == R.id.rbFontNotoSans) {
                BayanPreferences.FONT_FAMILY_NOTO_SANS
            } else {
                BayanPreferences.FONT_FAMILY_NOTO_NASKH
            }
            updatePreviewTypography(fontFamily = family)
            lifecycleScope.launch {
                repository.updateFontFamily(family)
            }
        }

        switchWifiOnly.setOnCheckedChangeListener { _, isChecked ->
            if (isUpdatingFromFlow) return@setOnCheckedChangeListener
            lifecycleScope.launch {
                repository.updateWifiOnlyDownload(isChecked)
            }
        }
    }

    private fun observePreferences() {
        lifecycleScope.launch {
            repository.preferencesFlow.collect { prefs ->
                isUpdatingFromFlow = true
                applyPreferencesToUi(prefs)
                isUpdatingFromFlow = false
            }
        }
    }

    private fun applyPreferencesToUi(prefs: BayanPreferences) {
        // 1. Simplification Strength
        when (prefs.simplificationLevel) {
            SimplificationLevel.ADVANCED -> rbStrengthLight.isChecked = true
            SimplificationLevel.STANDARD -> rbStrengthMedium.isChecked = true
            SimplificationLevel.ELEMENTARY -> rbStrengthStrong.isChecked = true
        }

        // 2. Font Size
        if (sliderFontSize.value != prefs.fontSizeSp) {
            sliderFontSize.value = prefs.fontSizeSp
        }
        tvFontSizeValue.text = "${prefs.fontSizeSp.toInt()} sp"

        // 3. Line Spacing
        if (sliderLineSpacing.value != prefs.lineSpacingMultiplier) {
            sliderLineSpacing.value = prefs.lineSpacingMultiplier
        }
        tvLineSpacingValue.text = String.format(Locale.US, "%.1fx", prefs.lineSpacingMultiplier)

        // 4. Font Family
        if (prefs.fontFamily == BayanPreferences.FONT_FAMILY_NOTO_SANS) {
            rbFontNotoSans.isChecked = true
        } else {
            rbFontNotoNaskh.isChecked = true
        }

        // 5. Wi-Fi Only Switch
        if (switchWifiOnly.isChecked != prefs.wifiOnlyDownload) {
            switchWifiOnly.isChecked = prefs.wifiOnlyDownload
        }

        // Update live preview card
        updatePreviewTypography(prefs.fontSizeSp, prefs.lineSpacingMultiplier, prefs.fontFamily)
    }

    private fun updatePreviewTypography(
        fontSizeSp: Float = sliderFontSize.value,
        lineSpacingMultiplier: Float = sliderLineSpacing.value,
        fontFamily: String? = null
    ) {
        tvPreviewText.setTextSize(TypedValue.COMPLEX_UNIT_SP, fontSizeSp)
        tvPreviewText.setLineSpacing(0f, lineSpacingMultiplier)

        val targetFamily = fontFamily ?: if (rgFontFamily.checkedRadioButtonId == R.id.rbFontNotoSans) {
            BayanPreferences.FONT_FAMILY_NOTO_SANS
        } else {
            BayanPreferences.FONT_FAMILY_NOTO_NASKH
        }

        val typeface = getFontTypeface(targetFamily)
        if (typeface != null) {
            tvPreviewText.typeface = typeface
        }
    }

    private fun getFontTypeface(fontFamily: String): Typeface? {
        return try {
            val fontResId = if (fontFamily == BayanPreferences.FONT_FAMILY_NOTO_SANS) {
                R.font.noto_sans_arabic
            } else {
                R.font.noto_naskh_arabic
            }
            ResourcesCompat.getFont(this, fontResId)
        } catch (e: Exception) {
            Typeface.DEFAULT
        }
    }
}
