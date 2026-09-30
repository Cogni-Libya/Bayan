package ai.bayan.android.engine

import java.io.BufferedInputStream
import java.io.BufferedOutputStream
import java.io.DataInputStream
import java.io.DataOutputStream
import java.io.File
import java.text.Normalizer
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.double
import kotlinx.serialization.json.int
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive

/**
 * A pure-Kotlin reader for the SentencePiece tokenizers our models ship with, driven by their Hugging Face
 * `tokenizer.json`: AraBART uses a Unigram model, AraT5v2 a BPE model. Both use NFKC normalization and the Metaspace
 * pre-tokenizer ("▁" marks a word start). Encoding matches the Python tokenizer on our evaluation sentences
 * (see `SentencePieceTokenizerTest`).
 */
class SentencePieceTokenizer private constructor(
    private val model: SubwordModel,
    private val idToToken: Array<String>,
    private val specialIds: Set<Int>,
    private val prefixIds: IntArray,
    private val suffixIds: IntArray,
) {
    /** Token ids for [text], with the model's special tokens around it (e.g. `<s> … </s>`). */
    fun encode(text: String, maxTokens: Int = Int.MAX_VALUE): IntArray {
        val out = ArrayList<Int>()
        for (word in preTokenize(normalize(text))) model.tokenize(word, out)
        val budget = maxTokens - prefixIds.size - suffixIds.size
        val body = if (out.size > budget) out.subList(0, budget.coerceAtLeast(0)) else out
        return prefixIds + body.toIntArray() + suffixIds
    }

    /** Text for [ids], skipping special tokens. */
    fun decode(ids: IntArray): String {
        val sb = StringBuilder()
        for (id in ids) {
            if (id in specialIds || id !in idToToken.indices) continue
            sb.append(idToToken[id])
        }
        return sb.toString().replace(SPACE_MARK, ' ').trim()
    }

    private fun normalize(text: String): String =
        Normalizer.normalize(text, Normalizer.Form.NFKC).trimEnd().replace(WHITESPACE, " ")

    private fun preTokenize(text: String): List<String> {
        if (text.isEmpty()) return emptyList()
        val marked = SPACE_MARK + text.replace(' ', SPACE_MARK)
        val words = ArrayList<String>()
        var start = 0
        for (i in 1 until marked.length) {
            if (marked[i] == SPACE_MARK) {
                words += marked.substring(start, i)
                start = i
            }
        }
        words += marked.substring(start)
        return words
    }

    private interface SubwordModel {
        fun tokenize(word: String, out: MutableList<Int>)
    }

    /** Viterbi segmentation over the piece log-probabilities (SentencePiece Unigram). */
    private class Unigram(
        private val pieces: HashMap<String, Int>,
        private val scores: FloatArray,
        private val unkId: Int,
        private val maxPieceLength: Int,
    ) : SubwordModel {
        private val unkScore = (scores.minOrNull() ?: 0f) - 10f

        override fun tokenize(word: String, out: MutableList<Int>) {
            val n = word.length
            val best = FloatArray(n + 1) { Float.NEGATIVE_INFINITY }
            val from = IntArray(n + 1)
            val tokenAt = IntArray(n + 1)
            best[0] = 0f
            for (end in 1..n) {
                val lo = maxOf(0, end - maxPieceLength)
                for (start in lo until end) {
                    if (best[start] == Float.NEGATIVE_INFINITY) continue
                    val id = pieces[word.substring(start, end)] ?: continue
                    val s = best[start] + scores[id]
                    if (s > best[end]) { best[end] = s; from[end] = start; tokenAt[end] = id }
                }
                if (best[end] == Float.NEGATIVE_INFINITY && best[end - 1] != Float.NEGATIVE_INFINITY) {
                    best[end] = best[end - 1] + unkScore; from[end] = end - 1; tokenAt[end] = unkId
                }
            }
            val ids = ArrayList<Int>()
            var pos = n
            while (pos > 0) { ids += tokenAt[pos]; pos = from[pos] }
            ids.reverse()
            appendFusingUnk(ids, out, unkId)
        }
    }

    /** Greedy lowest-rank pair merging (SentencePiece BPE as converted by Hugging Face). */
    private class Bpe(
        private val vocab: HashMap<String, Int>,
        private val ranks: HashMap<String, Int>,
        private val unkId: Int,
    ) : SubwordModel {
        override fun tokenize(word: String, out: MutableList<Int>) {
            val symbols = word.codePoints().toArray().map { String(Character.toChars(it)) }.toMutableList()
            while (symbols.size > 1) {
                var bestRank = Int.MAX_VALUE
                var bestAt = -1
                for (i in 0 until symbols.size - 1) {
                    val r = ranks[symbols[i] + MERGE_SEP + symbols[i + 1]] ?: continue
                    if (r < bestRank) { bestRank = r; bestAt = i }
                }
                if (bestAt < 0) break
                val a = symbols[bestAt]
                val b = symbols[bestAt + 1]
                var i = 0
                while (i < symbols.size - 1) {
                    if (symbols[i] == a && symbols[i + 1] == b) {
                        symbols[i] = a + b
                        symbols.removeAt(i + 1)
                    }
                    i++
                }
            }
            appendFusingUnk(symbols.map { vocab[it] ?: unkId }, out, unkId)
        }
    }

    companion object {
        private const val SPACE_MARK = '▁'
        private const val MERGE_SEP = "\u0000"
        private val WHITESPACE = Regex("\\s+")

        private fun appendFusingUnk(ids: List<Int>, out: MutableList<Int>, unkId: Int) {
            for (id in ids) {
                if (id == unkId && out.isNotEmpty() && out.last() == unkId) continue
                out += id
            }
        }

        /**
         * Reads the tokenizer next to a model. Parsing a large `tokenizer.json` takes seconds on a phone (AraT5v2's
         * has 238k merges), so the first load also writes a compact binary copy that later loads read instead.
         */
        fun load(file: File): SentencePieceTokenizer {
            val cache = File(file.parentFile, file.name + ".bin")
            if (cache.isFile && cache.lastModified() >= file.lastModified()) {
                runCatching { return build(readCache(cache)) }
            }
            val parts = parseParts(file.readText())
            runCatching { writeCache(cache, parts) }.onFailure { cache.delete() }
            return build(parts)
        }

        fun parse(json: String): SentencePieceTokenizer = build(parseParts(json))

        /** Everything a tokenizer is built from, in a form that is quick to store and read back. */
        private class Parts(
            val bpe: Boolean,
            val idToToken: Array<String>,
            val specialIds: IntArray,
            val prefix: IntArray,
            val suffix: IntArray,
            val unkId: Int,
            val scores: FloatArray,
            /** BPE merges in rank order, each as "left\u0000right". */
            val merges: Array<String>,
        )

        private fun build(p: Parts): SentencePieceTokenizer {
            val model: SubwordModel = if (p.bpe) {
                val vocab = HashMap<String, Int>(p.idToToken.size * 2)
                p.idToToken.forEachIndexed { i, t -> if (t.isNotEmpty()) vocab.putIfAbsent(t, i) }
                val ranks = HashMap<String, Int>(p.merges.size * 2)
                p.merges.forEachIndexed { rank, pair -> ranks[pair] = rank }
                Bpe(vocab, ranks, p.unkId)
            } else {
                val pieces = HashMap<String, Int>(p.idToToken.size * 2)
                var maxLen = 1
                p.idToToken.forEachIndexed { i, t -> pieces[t] = i; if (t.length > maxLen) maxLen = t.length }
                Unigram(pieces, p.scores, p.unkId, maxLen)
            }
            return SentencePieceTokenizer(model, p.idToToken, p.specialIds.toSet(), p.prefix, p.suffix)
        }

        private const val CACHE_VERSION = 1

        private fun writeCache(file: File, p: Parts) {
            DataOutputStream(BufferedOutputStream(file.outputStream(), 1 shl 16)).use { out ->
                out.writeInt(CACHE_VERSION)
                out.writeBoolean(p.bpe)
                out.writeInt(p.idToToken.size); p.idToToken.forEach { out.writeUTF(it) }
                for (arr in listOf(p.specialIds, p.prefix, p.suffix)) { out.writeInt(arr.size); arr.forEach { out.writeInt(it) } }
                out.writeInt(p.unkId)
                out.writeInt(p.scores.size); p.scores.forEach { out.writeFloat(it) }
                out.writeInt(p.merges.size); p.merges.forEach { out.writeUTF(it) }
            }
        }

        private fun readCache(file: File): Parts =
            DataInputStream(BufferedInputStream(file.inputStream(), 1 shl 16)).use { input ->
                check(input.readInt() == CACHE_VERSION) { "Old tokenizer cache" }
                val bpe = input.readBoolean()
                val tokens = Array(input.readInt()) { input.readUTF() }
                val ints = List(3) { IntArray(input.readInt()) { input.readInt() } }
                val unk = input.readInt()
                val scores = FloatArray(input.readInt()) { input.readFloat() }
                val merges = Array(input.readInt()) { input.readUTF() }
                Parts(bpe, tokens, ints[0], ints[1], ints[2], unk, scores, merges)
            }

        private fun parseParts(json: String): Parts {
            val root = Json.parseToJsonElement(json).jsonObject
            val m = root.getValue("model").jsonObject
            val added = root["added_tokens"]?.jsonArray.orEmpty().map { it.jsonObject }
            val addedIds = added.associate { it.getValue("content").jsonPrimitive.content to it.getValue("id").jsonPrimitive.int }
            val specialIds = added.filter { it["special"]?.jsonPrimitive?.booleanOrNull != false }
                .map { it.getValue("id").jsonPrimitive.int }.toIntArray()

            // TemplateProcessing "single": special tokens around the sequence "A".
            val prefix = ArrayList<Int>()
            val suffix = ArrayList<Int>()
            var seenSequence = false
            val single = (root["post_processor"] as? JsonObject)?.get("single")?.jsonArray.orEmpty()
            for (step in single) {
                val o = step.jsonObject
                when {
                    "Sequence" in o -> seenSequence = true
                    "SpecialToken" in o -> {
                        val tok = o.getValue("SpecialToken").jsonObject.getValue("id").jsonPrimitive.content
                        val id = addedIds[tok] ?: continue
                        if (seenSequence) suffix += id else prefix += id
                    }
                }
            }

            return when (val type = m.getValue("type").jsonPrimitive.content) {
                "Unigram" -> {
                    val vocab = m.getValue("vocab").jsonArray
                    Parts(
                        bpe = false,
                        idToToken = Array(vocab.size) { vocab[it].jsonArray[0].jsonPrimitive.content },
                        specialIds = specialIds, prefix = prefix.toIntArray(), suffix = suffix.toIntArray(),
                        unkId = m["unk_id"]?.jsonPrimitive?.intOrNull ?: 0,
                        scores = FloatArray(vocab.size) { vocab[it].jsonArray[1].jsonPrimitive.double.toFloat() },
                        merges = emptyArray(),
                    )
                }
                "BPE" -> {
                    val vocab = HashMap<String, Int>()
                    for ((k, v) in m.getValue("vocab").jsonObject) vocab[k] = v.jsonPrimitive.int
                    for ((k, v) in addedIds) vocab.putIfAbsent(k, v)
                    val idToToken = Array((vocab.values.maxOrNull() ?: -1) + 1) { "" }
                    for ((k, v) in vocab) idToToken[v] = k
                    val merges = m.getValue("merges").jsonArray.map { e ->
                        if (e is JsonArray) e[0].jsonPrimitive.content + MERGE_SEP + e[1].jsonPrimitive.content
                        else e.jsonPrimitive.content.replaceFirst(' ', MERGE_SEP[0])
                    }.toTypedArray()
                    val unkToken = m["unk_token"]?.jsonPrimitive?.content
                    Parts(
                        bpe = true, idToToken = idToToken,
                        specialIds = specialIds, prefix = prefix.toIntArray(), suffix = suffix.toIntArray(),
                        unkId = unkToken?.let { vocab[it] } ?: 0, scores = FloatArray(0), merges = merges,
                    )
                }
                else -> error("Unsupported tokenizer model: $type")
            }
        }
    }
}
