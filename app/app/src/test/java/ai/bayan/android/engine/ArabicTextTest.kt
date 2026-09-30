package ai.bayan.android.engine

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ArabicTextTest {
    @Test
    fun innerFullStopsBecomeCommas() {
        val source = "يعد الاحتباس الحراري من أبرز التحديات، إذ يؤدي إلى ارتفاع منسوب مياه البحار."
        val output = "الاحتباس الحراري مشكلة كبيرة. هو يرفع مياه البحار."
        assertEquals("الاحتباس الحراري مشكلة كبيرة، هو يرفع مياه البحار.", ArabicText.fixPunctuation(source, output))
    }

    @Test
    fun causeClauseGetsSemicolon() {
        assertEquals(
            "بقي في البيت؛ لأنه كان مريضا.",
            ArabicText.fixPunctuation("بقي في البيت لأنه كان مريضا.", "بقي في البيت. لأنه كان مريضا."),
        )
    }

    @Test
    fun sourceWithSeveralSentencesIsLeftAlone() {
        val output = "جاء الولد. ذهب البنت."
        assertEquals(output, ArabicText.fixPunctuation("جاء الولد. ثم ذهبت البنت.", output))
    }

    @Test
    fun faithfulSimplificationKeepsMostWords() {
        val source = "يعد الاحتباس الحراري من أبرز التحديات التي تواجه البشرية في العصر الحديث"
        val output = "الاحتباس الحراري أحد التحديات البيئية في العصر الحديث"
        assertTrue(ArabicText.retention(source, output) >= 0.5f)
    }

    @Test
    fun inventedOutputIsCaught() {
        assertTrue(ArabicText.retention("إطلاق الأسماء على الأنواع", "إطلاق سراح مشروط") < 0.35f)
    }

    @Test
    fun cliticsAndHamzaAreNormalized() {
        assertEquals(ArabicText.normalizeWord("أنواع"), ArabicText.normalizeWord("والأنواع"))
        assertEquals(ArabicText.normalizeWord("مدرسه"), ArabicText.normalizeWord("المدرسةُ"))
    }

    @Test
    fun paragraphsSplitIntoSentences() {
        val p = ArabicText.paragraphs("جملة أولى. جملة ثانية؟\n\nفقرة ثانية!")
        assertEquals(listOf(listOf("جملة أولى.", "جملة ثانية؟"), listOf("فقرة ثانية!")), p)
    }
}
