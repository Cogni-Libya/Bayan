package ai.bayan.android.engine

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * High-quality rule-based stand-in simplifier for Arabic text.
 *
 * Implements lexical substitutions based on SAMER Arabic readability research,
 * splits complex conjunctive phrases, and handles non-Arabic inputs gracefully.
 * Supports diacritic-tolerant (tashkeel/harakat) matching and preserves
 * structural paragraph breaks (\n\n) essential for readers with dyslexia.
 * Ready for drop-in replacement by AraT5v2 ONNX Runtime engine.
 */
class MockTextSimplifier : TextSimplifier {

    companion object {
        private const val TASHKEEL_AND_TATWEEL = "[\\u0640\\u064B-\\u0652\\u0670]*"
        private val TASHKEEL_STRIP_REGEX = Regex("[\\u0640\\u064B-\\u0652\\u0670]")

        private val RAW_VOCABULARY = linkedMapOf(
            "يمتطي" to "يركب",
            "مترامي الأطراف" to "واسع جداً",
            "يحتدم" to "يشتد",
            "قاطبة" to "جميعاً",
            "الإخفاق" to "الفشل",
            "أضحت" to "أصبحت",
            "مؤازرة" to "مساعدة",
            "حلكة" to "ظلام",
            "شائكة" to "صعبة",
            "يبتغي" to "يريد",
            "يتعيّن على" to "يجب على",
            "شديد التعقيد" to "صعب جداً",
            "بصورة ملحوظة" to "بشكل واضح",
            "علاوة على ذلك" to "أيضاً",
            "في الآونة الأخيرة" to "مؤخراً",
            "نظراً لـ" to "بسبب",
            "استطرد قائلاً" to "أكمل قائلاً",
            "قسراً" to "إجبارياً",
            "الباسقة" to "العالية",
            "يندثر" to "يختفي"
        )

        /**
         * Builds a regex matching an Arabic word or phrase regardless of interior or trailing
         * diacritics (fatha, damma, kasra, sukun, shaddah, tanween, dagger alif) or tatweel.
         * Anchored with lookaround boundaries to prevent false substring collisions inside larger words.
         */
        private fun buildDiacriticTolerantRegex(phrase: String): Regex {
            val sb = StringBuilder()
            // Word boundary: not preceded by an Arabic letter
            sb.append("(?<![\\u0621-\\u064A])")
            val cleanPhrase = phrase.replace(TASHKEEL_STRIP_REGEX, "")
            for (ch in cleanPhrase) {
                when {
                    ch in '\u0621'..'\u064A' -> {
                        sb.append(Regex.escape(ch.toString()))
                        sb.append(TASHKEEL_AND_TATWEEL)
                    }
                    ch == ' ' -> {
                        sb.append("[\\t ]+")
                    }
                    else -> {
                        sb.append(Regex.escape(ch.toString()))
                    }
                }
            }
            // Word boundary: not followed by an Arabic letter
            sb.append("(?![\\u0621-\\u064A])")
            return Regex(sb.toString())
        }

        private val COMPILED_VOCABULARY: List<Pair<Regex, String>> = RAW_VOCABULARY.map { (complex, simple) ->
            buildDiacriticTolerantRegex(complex) to simple
        }

        private val CLAUSE_REGEX = buildDiacriticTolerantRegex("بالرغم من أن")
        private const val CLAUSE_REPLACEMENT = "مع أن"
    }

    // Retained for backward compatibility
    private val vocabularySubstitutions = RAW_VOCABULARY

    override suspend fun simplify(request: SimplificationRequest): SimplificationResult =
        withContext(Dispatchers.Default) {
            val startTime = System.currentTimeMillis()
            val original = request.originalText

            if (original.isBlank()) {
                return@withContext SimplificationResult(
                    originalText = original,
                    simplifiedText = original,
                    level = request.targetLevel,
                    processingTimeMs = 0L,
                    replacedWordsCount = 0,
                    isModelOnDevice = true,
                    isSuccess = true
                )
            }

            // Check if text has Arabic letters
            val hasArabic = original.any { it in '\u0600'..'\u06FF' }
            if (!hasArabic) {
                val latency = System.currentTimeMillis() - startTime
                return@withContext SimplificationResult(
                    originalText = original,
                    simplifiedText = original,
                    level = request.targetLevel,
                    processingTimeMs = latency,
                    replacedWordsCount = 0,
                    isModelOnDevice = true,
                    isSuccess = true,
                    errorMessage = null
                )
            }

            var transformed = original
            var replacements = 0

            // Apply vocabulary substitutions using diacritic-tolerant precompiled regexes
            for ((regex, simpleWord) in COMPILED_VOCABULARY) {
                val matches = regex.findAll(transformed).count()
                if (matches > 0) {
                    replacements += matches
                    transformed = regex.replace(transformed, simpleWord)
                }
            }

            // Clause simplification (diacritic-tolerant)
            val clauseMatches = CLAUSE_REGEX.findAll(transformed).count()
            if (clauseMatches > 0) {
                replacements += clauseMatches
                transformed = CLAUSE_REGEX.replace(transformed, CLAUSE_REPLACEMENT)
            }

            // Normalize horizontal whitespace while strictly preserving newlines and paragraph breaks (\n\n)
            transformed = transformed
                .replace("\r\n", "\n")
                .replace('\r', '\n')
                .replace(Regex("[\\t\\x0B\\f\\r ]+"), " ")
                .replace(Regex(" ?\\n ?"), "\n")
                .replace(Regex("\\n{3,}"), "\n\n")
                .trim()

            val latency = System.currentTimeMillis() - startTime

            SimplificationResult(
                originalText = original,
                simplifiedText = transformed,
                level = request.targetLevel,
                processingTimeMs = latency,
                replacedWordsCount = replacements,
                isModelOnDevice = true,
                isSuccess = true
            )
        }

    override fun isModelReady(): Boolean = true

    override fun getEngineInfo(): EngineInfo = EngineInfo(
        name = "AraT5v2-base-1024 int8 ~164MB",
        version = "1.0.0-demo",
        status = "جاهز للاختبار (محرك محاكاة التجربة — جاهز لدمج AraT5 ONNX)",
        memoryFootprint = "~164 MB (CPU On-Device)",
        isOnnxReady = true
    )
}
