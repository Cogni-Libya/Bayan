package ai.bayan.android.engine

/** Text handling around the model: the models were trained on sentences without tashkeel. */
object ArabicText {
    private val TASHKEEL = Regex("[\\u0610-\\u061A\\u064B-\\u065F\\u0670\\u06D6-\\u06ED\\u0640]")
    private val SPACES = Regex("[ \\t\\u00A0]+")
    private val SENTENCE_END = Regex("(?<=[.!?؟])\\s+(?=\\S)")
    private val INNER_STOP = Regex("(?<![.\\d])\\.(?!\\.)(\\s+)(?=\\S)")
    private val CAUSE = Regex("^(لأن|لأنه|لأنها|لأنهم|لأني|لأننا|إذ)")

    private val NON_WORD = Regex("[^\\p{L}\\p{N}]")
    private val CLITICS = listOf("وال", "بال", "كال", "فال", "لل", "ال", "و", "ف", "ب", "ل")

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
        text.trim().split(Regex("\\n\\s*\\n|\\n")).map { p ->
            SENTENCE_END.split(SPACES.replace(p.trim(), " ")).map { it.trim() }.filter { it.isNotEmpty() }
        }.filter { it.isNotEmpty() }

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
}
