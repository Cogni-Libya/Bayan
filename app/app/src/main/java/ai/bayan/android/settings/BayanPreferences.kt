package ai.bayan.android.settings

import ai.bayan.android.engine.SimplificationLevel

/**
 * Data model holding user reading preferences and download policies
 * tailored for Arabic text simplification and dyslexia accessibility.
 */
data class BayanPreferences(
    val simplificationLevel: SimplificationLevel = SimplificationLevel.STANDARD,
    val fontSizeSp: Float = 22f,
    val lineSpacingMultiplier: Float = 1.6f,
    val fontFamily: String = "Noto Naskh Arabic",
    val wifiOnlyDownload: Boolean = true
) {
    companion object {
        const val DEFAULT_FONT_SIZE_SP = 22f
        const val MIN_FONT_SIZE_SP = 18f
        const val MAX_FONT_SIZE_SP = 32f

        const val DEFAULT_LINE_SPACING_MULTIPLIER = 1.6f
        const val MIN_LINE_SPACING_MULTIPLIER = 1.2f
        const val MAX_LINE_SPACING_MULTIPLIER = 2.0f

        const val FONT_FAMILY_NOTO_NASKH = "Noto Naskh Arabic"
        const val FONT_FAMILY_NOTO_SANS = "Noto Sans Arabic"
        const val DEFAULT_FONT_FAMILY = FONT_FAMILY_NOTO_NASKH

        const val DEFAULT_WIFI_ONLY_DOWNLOAD = true
    }
}
