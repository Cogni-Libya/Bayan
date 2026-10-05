package ai.bayan.android.engine

import java.text.Normalizer

/**
 * Text handling around the model: what goes in, and what may come out.
 *
 * Before the model, a selection is cleaned the way people actually copy text (PDF line breaks, presentation and
 * Persian letter forms, runs of dots, digits glued to letters, list bullets), Arabic-Indic and Persian digits become
 * Western digits, and scripture or set poetry never reaches the model. After it, a sentence falls back to the source
 * when the rewrite drifts, drops a number or a Latin-script word, or changes a negation or a stated limit.
 * BayanBench mirrors this file (data/processed/bench/appguard.py), so the benchmark scores what the reader sees.
 */
object ArabicText {
    private val TASHKEEL = Regex("[\\u0610-\\u061A\\u064B-\\u065F\\u0670\\u06D6-\\u06ED\\u0640]")
    private val SPACES = Regex("[ \\t\\u00A0]+")
    private val SENTENCE_END = Regex("(?<=[.!?؟])\\s+(?=\\S)")
    private val INNER_STOP = Regex("(?<![.\\d])\\.(?!\\.)(\\s+)(?=\\S)")
    private val CAUSE = Regex("^(لأن|لأنه|لأنها|لأنهم|لأني|لأننا|إذ)")
    private val END = Regex("[.!?؟]+[»\"')\\]]*\\s*$")

    private val NON_WORD = Regex("[^\\p{L}\\p{N}]")
    private val CLITICS = listOf("وال", "بال", "كال", "فال", "لل", "ال", "و", "ف", "ب", "ل")

    private const val DIGIT = "[0-9\\u0660-\\u0669\\u06F0-\\u06F9]"
    private const val AR_INDIC = "٠١٢٣٤٥٦٧٨٩"
    private const val PERSIAN = "۰۱۲۳۴۵۶۷۸۹"
    private val LETTER = Regex("[\\u0621-\\u064A]")
    private val MARK = Regex("[\\u064B-\\u0652]")
    private val BULLET = Regex("^\\s*([•●▪◦·∙‣\\-–—*]|[0-9\\u0660-\\u0669]{1,2}[.)\\-]|\\(?[0-9\\u0660-\\u0669]{1,2}\\)|[أ-ي][.)\\-])\\s+")
    private val INLINE_BULLET = Regex("[ \\t]+([•●▪◦‣])\\s+")
    private val QURANIC_SIGNS = Regex("[\\uFD3E\\uFD3F\\u0671\\u06D6-\\u06ED]")
    private val QUOTE_FORMULA = Regex("بسم الله الرحمن الرحيم|قال تعالى|قوله تعالى|صدق الله العظيم")
    private val VERSE_NUMBER_END = Regex("[(\\[]\\s*$DIGIT+\\s*[)\\]]\\s*[.؟!]?\\s*$")
    private val VERSE_NUMBER_START = Regex("^\\s*$DIGIT+\\s+\\S")
    private val HALF_LINES = Regex("\\S(?:\\s{3,}|\\t)\\S")

    private val NUMBER = Regex("\\d+(?:[.,]\\d+)?")
    private val SOURCE_NUMBER = Regex("$DIGIT+(?:[.,]$DIGIT+)?")
    private val LATIN = Regex("[A-Za-z][A-Za-z0-9]*(?:[-.][A-Za-z0-9]+)*")
    /** Latin tokens as the safety net of #61 counts them (`predict_net.py`): each one, case kept. */
    private val LATIN_TOKEN = Regex("[A-Za-z][A-Za-z0-9\\-.]*")
    private val NEGATION = Regex("(?:^|\\s)[وف]?(لا|لم|لن|ليس|ليست|ليسوا|لست|غير|دون|بدون|بلا)(?=\\s|$)")
    private const val A = "[أإآا]"
    private const val Y = "[ىي]"
    private const val E = "(?=[\\s،,.؛;:!?؟»)\\]]|$)"
    /** Condition words (BayanBench's `CONDITION`); bare «إن» is left out, since unvowelled it is mostly the emphatic «إنّ». */
    private val CONDITION = Regex("(?:^|\\s)[وف]?(إذا|اذا|لو|لولا|كلما|متى|مهما|ما\\s+لم|بشرط|شريطة)$E")
    private val LIMITS = listOf(
        "at least" to Regex("على\\s+ال${A}قل$E|لا\\s+[يت]قل$E|(?:^|\\s)[وك]?(?:ال)?حد\\s+(?:ال)?${A}دن$Y$E"),
        "at most" to Regex("على\\s+ال${A}كثر$E|لا\\s+[يت]زيد$E|(?:^|\\s)[وك]?(?:ال)?حد\\s+(?:ال)?${A}قص$Y$E"),
        "more than" to Regex("(?:^|\\s)[و]?${A}كثر\\s+من$E"),
        "less than" to Regex("(?:^|\\s)[و]?${A}قل\\s+من$E"),
        "only" to Regex("(?:^|\\s)[و]?(?:فقط|[إا]لا|سو$Y)$E"),
    )

    fun stripTashkeel(text: String): String = TASHKEEL.replace(text, "")

    fun wordCount(text: String): Int = text.split(' ', '\n').count { it.isNotBlank() }

    /** A word without tashkeel, hamza forms, taa marbuta or one leading clitic, so «والأنواع» matches «أنواع». */
    fun normalizeWord(word: String): String {
        var w = NON_WORD.replace(stripTashkeel(word), "")
            .replace('إ', 'ا').replace('أ', 'ا').replace('آ', 'ا').replace('ة', 'ه').replace('ى', 'ي')
        CLITICS.firstOrNull { w.startsWith(it) && w.length - it.length >= 3 }?.let { w = w.substring(it.length) }
        return w
    }

    /**
     * Share of the source's content words (3+ letters) that survive in the output. Faithful simplifications keep
     * at least half (1st percentile of our validated rewrites: 0.50, minimum 0.30); an invented sentence keeps almost none.
     */
    fun retention(source: String, output: String): Float {
        val src = source.split(' ').map(::normalizeWord).filter { it.length >= 3 }
        if (src.isEmpty()) return 1f
        val out = output.split(' ').map(::normalizeWord).toHashSet()
        return src.count { it in out }.toFloat() / src.size
    }

    /** Paragraphs, then sentences inside each paragraph; empty lines are kept as paragraph breaks. */
    fun paragraphs(text: String): List<List<String>> =
        text.trim().split(Regex("\\n\\s*\\n|\\n")).map(::sentences).filter { it.isNotEmpty() }

    private fun sentences(paragraph: String): List<String> =
        SENTENCE_END.split(SPACES.replace(paragraph.trim(), " ")).map { it.trim() }.filter { it.isNotEmpty() }

    /**
     * Arabic punctuation (grammar_ref/CHECKLIST.md): a full stop ends a complete meaning only. When the source sentence
     * had no inner full stop, inner full stops in the model's output become «،» (or «؛» before a clause of cause).
     */
    fun fixPunctuation(source: String, output: String): String {
        if (source.trimEnd().dropLast(1).contains(Regex("[.!?؟]\\s"))) return output
        val sb = StringBuilder()
        var last = 0
        for (m in INNER_STOP.findAll(output)) {
            val before = output.substring(0, m.range.first).trimEnd().substringAfterLast(' ')
            if (before.length == 1) continue // abbreviation such as ق. م.
            val rest = output.substring(m.range.last + 1)
            sb.append(output, last, m.range.first).append(if (CAUSE.containsMatchIn(rest)) "؛" else "،").append(m.groupValues[1])
            last = m.range.last + 1
        }
        sb.append(output.substring(last))
        return sb.toString()
    }

    // ------------------------------------------------------------------------------------------ before the model --

    /** Presentation forms (text copied from PDFs) to plain letters, and Persian letter forms to Arabic ones. */
    fun normalizeForms(text: String): String {
        val sb = StringBuilder(text.length)
        for (ch in text) {
            val c = ch.code
            when {
                (c in 0xFB50..0xFDFF || c in 0xFE70..0xFEFF) && ch != '﴾' && ch != '﴿' ->
                    sb.append(Normalizer.normalize(ch.toString(), Normalizer.Form.NFKC))
                ch == 'ی' -> sb.append('ي')
                ch == 'ک' -> sb.append('ك')
                ch == 'ۀ' -> sb.append('ة')
                ch == 'ھ' || ch == 'ہ' -> sb.append('ه')
                else -> sb.append(ch)
            }
        }
        return sb.toString()
    }

    /** Scripture and set poetry, which are never rewritten: Quranic signs and verse brackets, the usual quotation
     *  formulas, kashida-set verse, or a fully vowelled passage numbered like a verse or laid out in two half-lines. */
    fun isProtected(paragraph: String): Boolean {
        if (QURANIC_SIGNS.containsMatchIn(paragraph)) return true
        if (QUOTE_FORMULA.containsMatchIn(stripTashkeel(paragraph))) return true
        if (paragraph.count { it == 'ـ' } >= 3) return true
        val letters = LETTER.findAll(paragraph).count()
        if (letters > 0 && MARK.findAll(paragraph).count().toFloat() / letters >= 0.5f) {
            if (VERSE_NUMBER_END.containsMatchIn(paragraph) || VERSE_NUMBER_START.containsMatchIn(paragraph)) return true
            if (HALF_LINES.containsMatchIn(paragraph.trim())) return true
        }
        return false
    }

    /** A selection as people copy it from PDFs and web pages, made readable for the model. */
    fun clean(selection: String): String {
        var t = normalizeForms(selection).replace("\r\n", "\n").replace('\r', '\n')
        t = INLINE_BULLET.replace(t) { "\n${it.groupValues[1]} " }
        val joined = mutableListOf<String>()
        val keep = mutableListOf<Boolean>()
        for (line in t.split('\n')) { // a PDF breaks lines mid-sentence: join them back
            val prot = isProtected(line)
            val prev = joined.lastOrNull()
            if (prev != null && prev.isNotBlank() && line.isNotBlank() && !keep.last() && !prot && !END.containsMatchIn(prev) &&
                !prev.trimEnd().endsWith(":") && !prev.trimEnd().endsWith("…") && !BULLET.containsMatchIn(line)
            ) {
                joined[joined.lastIndex] = prev.trimEnd() + " " + line.trim()
            } else {
                joined += line
                keep += prot
            }
        }
        t = joined.joinToString("\n")
        t = Regex("\\.{2,}|…+").replace(t, "…")
        t = Regex("([\\u0621-\\u064A])($DIGIT)").replace(t, "$1 $2")
        t = Regex("($DIGIT)([\\u0621-\\u064A])").replace(t, "$1 $2")
        return t
    }

    fun toWesternDigits(text: String): String = buildString(text.length) {
        for (ch in text) {
            val i = AR_INDIC.indexOf(ch).takeIf { it >= 0 } ?: PERSIAN.indexOf(ch)
            append(if (i >= 0) '0' + i else ch)
        }
    }

    /** One step of the plan: a protected passage, a list marker, or a sentence ([input] is what the model sees). */
    sealed interface Step {
        val paragraph: Int
        data class Protected(override val paragraph: Int, val text: String) : Step
        data class Bullet(override val paragraph: Int, val marker: String) : Step
        data class Sentence(override val paragraph: Int, val text: String, val input: String, val toModel: Boolean) : Step
    }

    /** What the app does with each part of a selection, in reading order. */
    fun plan(selection: String, minWords: Int): List<Step> {
        val steps = mutableListOf<Step>()
        clean(selection).trim().split('\n').filter { it.isNotBlank() }.forEachIndexed { i, line ->
            if (isProtected(line)) {
                steps += Step.Protected(i, line.trim())
                return@forEachIndexed
            }
            var p = line
            BULLET.find(p)?.let { m ->
                steps += Step.Bullet(i, m.value.trim())
                p = p.substring(m.range.last + 1)
            }
            for (s in sentences(stripTashkeel(p))) steps += Step.Sentence(i, s, toWesternDigits(s), wordCount(s) >= minWords)
        }
        return steps
    }

    /** True when the selection stops mid-sentence: its ending stays open, and no full stop is added to it. */
    fun isOpenEnded(selection: String): Boolean {
        val t = selection.trim()
        return !END.containsMatchIn(t) && !t.endsWith("…") && !t.endsWith(":") && !t.endsWith("»") && !t.endsWith("\"")
    }

    // ------------------------------------------------------------------------------------------- after the model --

    enum class Fallback { Empty, Drifted, Numbers, LatinWords, Negation, Limits, Conditions }

    private fun limitsOf(text: String): List<String> {
        val t = stripTashkeel(text)
        return LIMITS.flatMap { (name, re) -> List(re.findAll(t).count()) { name } }.sorted()
    }

    /** Null when the rewrite may be shown; otherwise the guard that keeps the source sentence instead. */
    fun fallback(source: String, output: String, minRetention: Float): Fallback? = when {
        output.isBlank() -> Fallback.Empty
        retention(source, output) < minRetention -> Fallback.Drifted
        NUMBER.findAll(toWesternDigits(source)).map { it.value }.sorted().toList() !=
            NUMBER.findAll(toWesternDigits(output)).map { it.value }.sorted().toList() -> Fallback.Numbers
        !LATIN.findAll(output).map { it.value.lowercase() }.toSet()
            .containsAll(LATIN.findAll(source).map { it.value.lowercase() }.toSet()) -> Fallback.LatinWords
        NEGATION.findAll(stripTashkeel(source)).count() != NEGATION.findAll(stripTashkeel(output)).count() -> Fallback.Negation
        limitsOf(source) != limitsOf(output) -> Fallback.Limits
        // The checks below come from the safety net Model 3 was benchmarked with (#61), so the app is the system that
        // was measured; a sentence is kept as the source when either set of checks stops it.
        latinCountsDropped(source, output) -> Fallback.LatinWords
        conditionsOf(source) != conditionsOf(output) -> Fallback.Conditions
        else -> null
    }

    private fun conditionsOf(text: String): Int = CONDITION.findAll(stripTashkeel(text).replace(Regex("\\s+"), " ")).count()

    /** True when a Latin token appears fewer times in the output than in the source (case kept). */
    private fun latinCountsDropped(source: String, output: String): Boolean {
        val have = LATIN_TOKEN.findAll(output).groupingBy { it.value }.eachCount()
        return LATIN_TOKEN.findAll(source).groupingBy { it.value }.eachCount().any { (token, n) -> (have[token] ?: 0) < n }
    }

    /** Each number comes back written as the source wrote it (Arabic-Indic, Persian or Western digits). */
    fun matchDigitStyle(source: String, output: String): String {
        val forms = SOURCE_NUMBER.findAll(source).associate { toWesternDigits(it.value) to it.value }
        if (forms.isEmpty()) return output
        return NUMBER.replace(output) { forms[it.value] ?: it.value }
    }

    /**
     * A selection cut mid-sentence ends where the source ends: no full stop, and no words the model added after the
     * source's last word. If that word is gone from the rewrite, the source sentence is kept.
     */
    fun keepOpenEnding(source: String, output: String): String {
        val trailingStop = Regex("\\s*[.!?؟]+\\s*$")
        val last = source.split(' ').lastOrNull { it.isNotBlank() }?.let(::normalizeWord) ?: return output
        val words = trailingStop.replace(output, "").split(' ').filter { it.isNotBlank() }
        val i = words.indexOfLast { normalizeWord(it) == last }
        return if (i >= 0) words.subList(0, i + 1).joinToString(" ") else trailingStop.replace(source, "")
    }
}
