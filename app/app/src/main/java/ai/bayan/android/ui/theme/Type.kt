package ai.bayan.android.ui.theme

import androidx.compose.ui.text.TextStyle
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
        fontFamily = if (font == ReaderFont.Naskh) NotoNaskhArabic else FontFamily.Default,
        fontSize = sizeSp.sp,
        lineHeight = (sizeSp * lineHeight).sp,
        letterSpacing = (wordSpacing / 6f).em,
    ),
)
