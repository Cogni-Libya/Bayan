package ai.bayan.android.engine

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
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

    // ---- text step v2: protected text, messy input, guards ----

    @Test
    fun scriptureAndSetPoetryAreProtected() {
        assertTrue(ArabicText.isProtected("وَلَئِنْ مُتُّمْ أَوْ قُتِلْتُمْ لَإِلَى اللَّهِ تُحْشَرُونَ (158)"))
        assertTrue(ArabicText.isProtected("26 لأَنَّهُ مَاذَا يَنْتَفِعُ الإِنْسَانُ لَوْ رَبحَ الْعَالَمَ كُلَّهُ وَخَسِرَ نَفْسَهُ؟"))
        assertTrue(ArabicText.isProtected("إلاّ مــقــالــة َ أقــوامٍ شَــقــــيــتُ بــهـــا"))
        assertTrue(ArabicText.isProtected("وَقَفْتُ بِهَا مِنْ بَعْدِ عِشْرِينَ حِجَّةً     فَـلأيَاً عَرَفْتُ الدَّارَ بَعْدَ تَوَهُّـمِ"))
        assertFalse(ArabicText.isProtected("ذَهَبَ الْوَلَدُ إِلَى الْمَدْرَسَةِ مُبَكِّرًا فِي الصَّبَاحِ."))
        assertFalse(ArabicText.isProtected("ارتفعت درجات الحرارة بمقدار 1.1 درجة منذ عام 1900."))
    }

    @Test
    fun protectedLinesKeepTheirTashkeelAndAreNotJoined() {
        val steps = ArabicText.plan("وَلَئِنْ مُتُّمْ أَوْ قُتِلْتُمْ لَإِلَى اللَّهِ تُحْشَرُونَ (158)\nويتم تحديد صحة المفاهيم من خلال", 6)
        assertEquals(ArabicText.Step.Protected(0, "وَلَئِنْ مُتُّمْ أَوْ قُتِلْتُمْ لَإِلَى اللَّهِ تُحْشَرُونَ (158)"), steps[0])
        assertTrue(steps[1] is ArabicText.Step.Sentence)
    }

    @Test
    fun pdfLineBreaksAreJoinedAndBulletsKept() {
        val steps = ArabicText.plan("إن زيادة درجات الحرارة\nالعالمية ستؤدي إلى ارتفاع منسوب البحر.\n• النقطة الأولى في القائمة هنا\n- النقطة الثانية", 6)
        val sentence = steps[0] as ArabicText.Step.Sentence
        assertEquals("إن زيادة درجات الحرارة العالمية ستؤدي إلى ارتفاع منسوب البحر.", sentence.text)
        assertEquals(ArabicText.Step.Bullet(1, "•"), steps[1])
        assertEquals(ArabicText.Step.Bullet(2, "-"), steps[3])
    }

    @Test
    fun messyFormsDigitsAndDotsAreCleaned() {
        assertEquals("رئيس", ArabicText.clean("رئیس"))
        assertEquals("في عام 2050 …", ArabicText.clean("في عام2050 ...."))
        assertEquals("لا", ArabicText.normalizeForms("\uFEFB"))
    }

    @Test
    fun digitsGoInWesternAndComeBackInTheSourceStyle() {
        val s = ArabicText.plan("ارتفعت الحرارة بمقدار ٣ درجات في عام ٢٠٢٠ في العالم كله.", 6)[0] as ArabicText.Step.Sentence
        assertEquals("ارتفعت الحرارة بمقدار 3 درجات في عام 2020 في العالم كله.", s.input)
        assertEquals("زادت الحرارة ٣ درجات في ٢٠٢٠.", ArabicText.matchDigitStyle(s.text, "زادت الحرارة 3 درجات في 2020."))
        assertEquals("لا يزيد على 30 في ٢٠٢٠", ArabicText.matchDigitStyle("يزيد على 30 طالبا عام ٢٠٢٠", "لا يزيد على 30 في 2020"))
    }

    @Test
    fun guardsKeepTheSourceWhenMeaningIsAtRisk() {
        val src = "لا يجوز أن يزيد عدد الطلاب على الأكثر عن 30 طالبا في الفصل الواحد حسب نظام WHO الجديد."
        assertEquals(ArabicText.Fallback.Numbers, ArabicText.fallback(src, "لا يجوز أن يزيد عدد الطلاب على الأكثر عن 20 طالبا في الفصل حسب نظام WHO.", 0.35f))
        assertEquals(ArabicText.Fallback.LatinWords, ArabicText.fallback(src, "لا يجوز أن يزيد عدد الطلاب على الأكثر عن 30 طالبا في الفصل حسب النظام الجديد.", 0.35f))
        assertEquals(ArabicText.Fallback.Negation, ArabicText.fallback(src, "يجوز أن يزيد عدد الطلاب على الأكثر عن 30 طالبا في الفصل حسب نظام WHO.", 0.35f))
        assertEquals(ArabicText.Fallback.Limits, ArabicText.fallback(src, "لا يجوز أن يزيد عدد الطلاب على الأقل عن 30 طالبا في الفصل حسب نظام WHO.", 0.35f))
        assertNull(ArabicText.fallback(src, "لا يجوز أن يزيد عدد الطلاب في الفصل على الأكثر عن 30 طالبا، حسب نظام WHO الجديد.", 0.35f))
    }

    @Test
    fun theSafetyNetChecksOfIssue61AreAddedToTheGuards() {
        // condition words: a dropped «إذا» changes what the sentence says
        val cond = "يحق للموظف أن يأخذ إجازة إضافية إذا عمل أكثر من عشر سنوات في الشركة نفسها دون انقطاع."
        assertEquals(ArabicText.Fallback.Conditions, ArabicText.fallback(cond, "يحق للموظف أن يأخذ إجازة إضافية. وقد عمل أكثر من عشر سنوات في الشركة نفسها دون انقطاع.", 0.35f))
        assertNull(ArabicText.fallback(cond, "يحق للموظف إجازة إضافية إذا عمل أكثر من عشر سنوات في الشركة نفسها دون انقطاع.", 0.35f))
        assertEquals(ArabicText.Fallback.Conditions, ArabicText.fallback("سنخرج إلى الحديقة غدا في الصباح الباكر بشرط أن يتوقف المطر كما تتوقع الأرصاد.", "سنخرج إلى الحديقة غدا في الصباح الباكر، وسيتوقف المطر كما تتوقع الأرصاد.", 0.35f))
        // Latin tokens are counted one by one and case is kept: a repeated name or a changed case is caught
        val latin = "يستخدم نظام GPS في الهاتف، ويعمل GPS حتى دون اتصال بالإنترنت في معظم الأماكن."
        assertEquals(ArabicText.Fallback.LatinWords, ArabicText.fallback(latin, "يستخدم نظام GPS في الهاتف، ويعمل حتى دون اتصال بالإنترنت في معظم الأماكن.", 0.35f))
        assertEquals(ArabicText.Fallback.LatinWords, ArabicText.fallback(latin, "يستخدم نظام gps في الهاتف، ويعمل gps حتى دون اتصال بالإنترنت في معظم الأماكن.", 0.35f))
        assertNull(ArabicText.fallback(latin, "يستخدم الهاتف نظام GPS، ويعمل GPS حتى دون اتصال بالإنترنت في معظم الأماكن.", 0.35f))
    }

    @Test
    fun aCutOffSelectionKeepsItsOpenEnding() {
        assertTrue(ArabicText.isOpenEnded("ويتم تحديد صحة المفاهيم من خلال"))
        assertFalse(ArabicText.isOpenEnded("ويتم تحديد صحة المفاهيم بالاختبار."))
        assertEquals("ويتم تحديد صحة المفاهيم من خلال", ArabicText.keepOpenEnding("ويتم تحديد صحة المفاهيم من خلال", "ويتم تحديد صحة المفاهيم من خلال فحص المعلومات."))
        assertEquals("ويتم تحديد صحة المفاهيم من خلال", ArabicText.keepOpenEnding("ويتم تحديد صحة المفاهيم من خلال", "يتم تحديد المفاهيم بالفحص."))
    }
}
