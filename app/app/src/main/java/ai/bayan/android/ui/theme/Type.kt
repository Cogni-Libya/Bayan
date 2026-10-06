package ai.bayan.android.ui.theme

import androidx.compose.ui.text.TextStyle
import androidx.compose.material3.Typography
import androidx.compose.ui.text.ExperimentalTextApi
import androidx.compose.ui.text.font.FontVariation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextDirection
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.em
import androidx.compose.ui.unit.sp
import ai.bayan.android.R
import ai.bayan.android.data.ReaderFont
import ai.bayan.android.data.ReaderStyle

/** Readex Pro (variable, SIL OFL): the Arabic expansion of Lexend, drawn for reading fluency; Bayan's typeface. */
@OptIn(ExperimentalTextApi::class)
val ReadexPro = FontFamily(
    Font(R.font.readex_pro, FontWeight.Normal, variationSettings = FontVariation.Settings(FontVariation.weight(400))),
    Font(R.font.readex_pro, FontWeight.Medium, variationSettings = FontVariation.Settings(FontVariation.weight(500))),
    Font(R.font.readex_pro, FontWeight.SemiBold, variationSettings = FontVariation.Settings(FontVariation.weight(600))),
    Font(R.font.readex_pro, FontWeight.Light, variationSettings = FontVariation.Settings(FontVariation.weight(300))),
)

/** Material's type scale set in Readex Pro, for the Bayan style. */
fun Typography.inReadexPro(): Typography = Typography(
    displayLarge = displayLarge.copy(fontFamily = ReadexPro), displayMedium = displayMedium.copy(fontFamily = ReadexPro),
    displaySmall = displaySmall.copy(fontFamily = ReadexPro), headlineLarge = headlineLarge.copy(fontFamily = ReadexPro),
    headlineMedium = headlineMedium.copy(fontFamily = ReadexPro), headlineSmall = headlineSmall.copy(fontFamily = ReadexPro),
    titleLarge = titleLarge.copy(fontFamily = ReadexPro), titleMedium = titleMedium.copy(fontFamily = ReadexPro),
    titleSmall = titleSmall.copy(fontFamily = ReadexPro), bodyLarge = bodyLarge.copy(fontFamily = ReadexPro),
    bodyMedium = bodyMedium.copy(fontFamily = ReadexPro), bodySmall = bodySmall.copy(fontFamily = ReadexPro),
    labelLarge = labelLarge.copy(fontFamily = ReadexPro), labelMedium = labelMedium.copy(fontFamily = ReadexPro),
    labelSmall = labelSmall.copy(fontFamily = ReadexPro),
)

/** Noto Naskh Arabic, the classic book style, offered as a reading option next to the system font. */
val NotoNaskhArabic = FontFamily(
    Font(R.font.noto_naskh_arabic, FontWeight.Normal),
    Font(R.font.noto_naskh_arabic, FontWeight.Medium),
)

/**
 * Arabic content is right-to-left whatever the app's language: with the phone in English the layout is left-to-right,
 * and text aligned to its "start" would sit on the left. Direction and alignment follow the text itself.
 */
val ContentDirection = TextStyle(textDirection = TextDirection.ContentOrRtl, textAlign = TextAlign.Start)

/** The simplified text: large and generously spaced; Compose has no word spacing, so it widens letter spacing slightly. */
fun ReaderStyle.textStyle(): TextStyle = ContentDirection.merge(
    TextStyle(
        fontFamily = when (font) {
            ReaderFont.Readex -> ReadexPro
            ReaderFont.Naskh -> NotoNaskhArabic
            ReaderFont.System -> FontFamily.Default
        },
        fontSize = sizeSp.sp,
        lineHeight = (sizeSp * lineHeight).sp,
        letterSpacing = (wordSpacing / 6f).em,
    ),
)
