package ai.bayan.android

import ai.bayan.android.engine.EngineInfo
import ai.bayan.android.engine.MockTextSimplifier
import ai.bayan.android.engine.SimplificationLevel
import ai.bayan.android.engine.SimplificationRequest
import ai.bayan.android.engine.SimplificationResult
import ai.bayan.android.engine.SimplifierProvider
import ai.bayan.android.engine.TextSimplifier
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertSame
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/**
 * Unit and component tests for [MockTextSimplifier] and [SimplifierProvider].
 *
 * Verifies rule-based lexical substitution on complex Arabic vocabulary (SAMER dataset),
 * diacritic tolerance (tashkeel/harakat), paragraph break preservation, non-Arabic detection,
 * latency tracking, replaced word counting, and engine metadata.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class MockTextSimplifierTest {

    private lateinit var simplifier: MockTextSimplifier

    @Before
    fun setUp() {
        simplifier = MockTextSimplifier()
        SimplifierProvider.reset()
    }

    @After
    fun tearDown() {
        SimplifierProvider.reset()
    }

    @Test
    fun testIsModelReady_returnsTrue() {
        assertTrue("MockTextSimplifier must report ready status", simplifier.isModelReady())
    }

    @Test
    fun testGetEngineInfo_reportsAccurateMetadata() {
        val info: EngineInfo = simplifier.getEngineInfo()
        assertNotNull("EngineInfo must not be null", info)
        assertEquals("AraT5v2-base-1024 int8 ~164MB", info.name)
        assertEquals("1.0.0-demo", info.version)
        assertTrue("Status must indicate readiness for testing", info.status.contains("جاهز للاختبار"))
        assertEquals("~164 MB (CPU On-Device)", info.memoryFootprint)
        assertTrue("isOnnxReady flag must be true", info.isOnnxReady)
    }

    @Test
    fun testRuleBasedLexicalSubstitution_samerVocabularyPairs() = runBlocking {
        // Test key SAMER vocabulary replacements individually
        val testCases = mapOf(
            "يمتطي الفارس جواده" to "يركب الفارس جواده",
            "أرض مترامي الأطراف" to "أرض واسع جداً",
            "النزاع يحتدم بينهما" to "النزاع يشتد بينهما",
            "حضر الناس قاطبة" to "حضر الناس جميعاً",
            "تجنب الإخفاق في المهمة" to "تجنب الفشل في المهمة",
            "أضحت القرية هادئة" to "أصبحت القرية هادئة",
            "نطلب مؤازرة الأصدقاء" to "نطلب مساعدة الأصدقاء",
            "في حلكة الليل" to "في ظلام الليل",
            "مسألة شائكة للغاية" to "مسألة صعبة للغاية",
            "يبتغي الطالب النجاح" to "يريد الطالب النجاح",
            "يتعيّن على الجميع الحضور" to "يجب على الجميع الحضور",
            "أمر شديد التعقيد" to "أمر صعب جداً",
            "تغير بصورة ملحوظة" to "تغير بشكل واضح",
            "علاوة على ذلك تقدمنا" to "أيضاً تقدمنا",
            "في الآونة الأخيرة حدث تطور" to "مؤخراً حدث تطور",
            "نظراً لـ صعوبة الأمر" to "بسبب صعوبة الأمر",
            "استطرد قائلاً كلاماً مهماً" to "أكمل قائلاً كلاماً مهماً",
            "أُخذ قسراً من مكانه" to "أُخذ إجبارياً من مكانه",
            "الأشجار الباسقة في الغابة" to "الأشجار العالية في الغابة",
            "أثر يندثر مع الزمن" to "أثر يختفي مع الزمن"
        )

        for ((input, expectedOutput) in testCases) {
            val request = SimplificationRequest(originalText = input)
            val result = simplifier.simplify(request)
            assertEquals("Substitution failed for input: $input", expectedOutput, result.simplifiedText)
            assertTrue("Replaced word count should be >= 1 for input: $input", result.replacedWordsCount >= 1)
            assertTrue("Result must indicate success", result.isSuccess)
        }
    }

    @Test
    fun testRuleBasedLexicalSubstitution_combinedPassage() = runBlocking {
        // Multi-term paragraph exercising 6 SAMER replacements simultaneously:
        // 1. يبتغي -> يريد
        // 2. مؤازرة -> مساعدة
        // 3. قاطبة -> جميعاً
        // 4. نظراً لـ -> بسبب
        // 5. حلكة -> ظلام
        // 6. في الآونة الأخيرة -> مؤخراً
        val input = "يبتغي الكاتب مؤازرة القراء قاطبة نظراً لـ حلكة الظروف في الآونة الأخيرة."
        val expected = "يريد الكاتب مساعدة القراء جميعاً بسبب ظلام الظروف مؤخراً."

        val request = SimplificationRequest(
            originalText = input,
            targetLevel = SimplificationLevel.STANDARD,
            preserveDiacritics = false
        )
        val result: SimplificationResult = simplifier.simplify(request)

        assertEquals("Multi-term simplification mismatch", expected, result.simplifiedText)
        assertEquals("Replaced word count must match exact number of substitutions", 6, result.replacedWordsCount)
        assertEquals(input, result.originalText)
        assertEquals(SimplificationLevel.STANDARD, result.level)
        assertTrue(result.isSuccess)
        assertTrue(result.isModelOnDevice)
    }

    @Test
    fun testClauseSimplification_replacesConjunctivePhrases() = runBlocking {
        val input = "واصلت القافلة مسيرها بالرغم من أن العاصفة كانت شديدة."
        val expected = "واصلت القافلة مسيرها مع أن العاصفة كانت شديدة."

        val result = simplifier.simplify(SimplificationRequest(originalText = input))
        assertEquals(expected, result.simplifiedText)
        assertEquals(1, result.replacedWordsCount)
    }

    @Test
    fun testMultipleOccurrencesOfSameTerm() = runBlocking {
        val input = "يبتغي زيد العلم كما يبتغي عمرو الحكمة."
        val expected = "يريد زيد العلم كما يريد عمرو الحكمة."

        val result = simplifier.simplify(SimplificationRequest(originalText = input))
        assertEquals(expected, result.simplifiedText)
        assertEquals(2, result.replacedWordsCount)
    }

    @Test
    fun testNonArabicDetection_leavesTextUnchanged() = runBlocking {
        val englishInput = "Dyslexia-friendly text simplification engine for Arabic script."
        val result = simplifier.simplify(SimplificationRequest(originalText = englishInput))

        assertEquals("Non-Arabic text must be returned unmodified", englishInput, result.simplifiedText)
        assertEquals("Replaced count for non-Arabic text must be 0", 0, result.replacedWordsCount)
        assertTrue("Non-Arabic fallback must still succeed", result.isSuccess)
    }

    @Test
    fun testNonArabicDetection_numericAndPunctuationOnly() = runBlocking {
        val input = "1234567890 !@#$%^&*()_+=-"
        val result = simplifier.simplify(SimplificationRequest(originalText = input))

        assertEquals("Non-Arabic text must remain unchanged", input, result.simplifiedText)
        assertEquals(0, result.replacedWordsCount)
        assertTrue(result.isSuccess)
    }

    @Test
    fun testEmptyInput_returnsImmediately() = runBlocking {
        val result = simplifier.simplify(SimplificationRequest(originalText = ""))

        assertEquals("", result.simplifiedText)
        assertEquals(0, result.replacedWordsCount)
        assertEquals(0L, result.processingTimeMs)
        assertTrue(result.isSuccess)
    }

    @Test
    fun testWhitespaceInput_returnsImmediately() = runBlocking {
        val whitespace = "    \t\n   "
        val result = simplifier.simplify(SimplificationRequest(originalText = whitespace))

        assertEquals(whitespace, result.simplifiedText)
        assertEquals(0, result.replacedWordsCount)
        assertEquals(0L, result.processingTimeMs)
        assertTrue(result.isSuccess)
    }

    @Test
    fun testLatencyMeasurement_recordsNonNegativeProcessingTime() = runBlocking {
        val input = "أضحت المسألة شائكة نظراً لـ شديد التعقيد."
        val result = simplifier.simplify(SimplificationRequest(originalText = input))

        assertTrue("Processing time in ms must be non-negative", result.processingTimeMs >= 0L)
    }

    @Test
    fun testSimplifierProvider_singletonManagementAndOverride() {
        val defaultInstance = SimplifierProvider.getInstance()
        assertNotNull("SimplifierProvider must provide default instance", defaultInstance)
        assertTrue("Default instance must be MockTextSimplifier", defaultInstance is MockTextSimplifier)

        val sameInstance = SimplifierProvider.getInstance()
        assertSame("Subsequent calls must return singleton instance", defaultInstance, sameInstance)

        // Test custom mock override
        val customSimplifier = object : TextSimplifier {
            override suspend fun simplify(request: SimplificationRequest): SimplificationResult {
                return SimplificationResult(
                    originalText = request.originalText,
                    simplifiedText = "نص مخصص",
                    replacedWordsCount = 1
                )
            }
            override fun isModelReady(): Boolean = true
            override fun getEngineInfo(): EngineInfo = EngineInfo(
                name = "CustomEngine",
                version = "2.0",
                status = "Active",
                memoryFootprint = "0MB",
                isOnnxReady = false
            )
        }

        SimplifierProvider.setInstance(customSimplifier)
        assertSame("Provider must return overridden instance", customSimplifier, SimplifierProvider.getInstance())

        // Reset restores default
        SimplifierProvider.reset()
        val restoredInstance = SimplifierProvider.getInstance()
        assertNotNull(restoredInstance)
        assertTrue(restoredInstance is MockTextSimplifier)
    }

    // =========================================================================
    // Iteration 2 Regression Tests: Paragraph Preservation & Tashkeel Tolerance
    // =========================================================================

    @Test
    fun testParagraphPreservation_preservesNewlinesAndParagraphBreaks() = runBlocking {
        val input = "يمتطي الفارس جواده في الصباح.\n\nأضحت القرية هادئة بعد العاصفة."
        val expected = "يركب الفارس جواده في الصباح.\n\nأصبحت القرية هادئة بعد العاصفة."

        val result = simplifier.simplify(SimplificationRequest(originalText = input))
        assertEquals("Paragraph breaks (\\n\\n) must not be collapsed into spaces", expected, result.simplifiedText)
        assertEquals(2, result.replacedWordsCount)
    }

    @Test
    fun testParagraphPreservation_normalizesExcessiveNewlines() = runBlocking {
        val input = "الفقرة الأولى.\n\n\n\nالفقرة الثانية."
        val expected = "الفقرة الأولى.\n\nالفقرة الثانية."

        val result = simplifier.simplify(SimplificationRequest(originalText = input))
        assertEquals("Excessive newlines (>2) must be normalized to standard paragraph break (\\n\\n)", expected, result.simplifiedText)
    }

    @Test
    fun testTashkeelTolerance_matchesFullyVowelizedArabicWords() = runBlocking {
        // "يَمْتَطِي" (fully diacritized) -> must match dictionary key "يمتطي" and replace with "يركب"
        val input = "يَمْتَطِي الفَارِسُ جَوَادَهُ"
        val result = simplifier.simplify(SimplificationRequest(originalText = input))

        assertTrue("Should substitute vowelized complex word with simple word", result.simplifiedText.startsWith("يركب"))
        assertEquals(1, result.replacedWordsCount)
        assertTrue("Surrounding diacritized words must remain intact", result.simplifiedText.contains("الفَارِسُ"))
    }

    @Test
    fun testTashkeelTolerance_shaddahAndTanweenKeys() = runBlocking {
        // "يَتَعَيَّنُ عَلَى" (with fatha, shaddah, damma) -> matches "يتعيّن على" -> "يجب على"
        val inputShaddah = "يَتَعَيَّنُ عَلَى الجميع الحضور"
        val resultShaddah = simplifier.simplify(SimplificationRequest(originalText = inputShaddah))
        assertEquals("يجب على الجميع الحضور", resultShaddah.simplifiedText)
        assertEquals(1, resultShaddah.replacedWordsCount)

        // "قَسْراً" (vowelized with fatha, sukun, tanween) -> matches "قسراً" -> "إجبارياً"
        val inputTanween = "أُخِذَ قَسْراً مِنْ مَكَانِهِ"
        val resultTanween = simplifier.simplify(SimplificationRequest(originalText = inputTanween))
        assertTrue("Should replace vowelized word with إجبارياً", resultTanween.simplifiedText.contains("إجبارياً"))
        assertEquals(1, resultTanween.replacedWordsCount)
    }

    @Test
    fun testClauseSimplification_vowelizedConjunctivePhrase() = runBlocking {
        val input = "واصلت القافلة مسيرها بِالرَّغْمِ مِنْ أَنَّ العاصفة كانت شديدة."
        val expected = "واصلت القافلة مسيرها مع أن العاصفة كانت شديدة."

        val result = simplifier.simplify(SimplificationRequest(originalText = input))
        assertEquals("Vowelized conjunctive phrase must be recognized and simplified", expected, result.simplifiedText)
        assertEquals(1, result.replacedWordsCount)
    }
}
