package ai.bayan.android.engine

import java.util.concurrent.ExecutorService
import kotlin.math.exp
import kotlin.math.ln
import kotlin.math.pow

/**
 * Beam search for one input, ported step for step from Hugging Face transformers 4.57's `_beam_search` (deterministic,
 * one end-of-sequence token, one returned sequence), so that a model decoded on the phone gives the outputs it was
 * evaluated with: `generate(num_beams=…, no_repeat_ngram_size=…, max_length=…)` with the default length penalty and
 * early stopping. It knows nothing about ONNX: [Step] runs the model.
 *
 * Scores are kept in Float like transformers' float32 tensors. Every decision clear of float rounding matches
 * transformers token for token (BeamSearchTest, against transformers itself; EngineParityTest, on the real model); where
 * two candidates are within a float step, torch's own rounding, which cannot be reproduced bit for bit, decides.
 *
 * @param maxLength the decoder's whole length cap, start token included (transformers' `max_length`).
 * @param pool when given, the beams are scored in parallel on it (the result is the same: candidates are ranked by
 *   score, then by index, a total order).
 */
class BeamSearch(
    val numBeams: Int,
    private val eosTokenId: Int,
    private val maxLength: Int,
    private val noRepeatNgramSize: Int,
    private val lengthPenalty: Float = 1f,
    private val earlyStopping: EarlyStopping = EarlyStopping.Heuristic,
    private val pool: ExecutorService? = null,
) {
    init {
        require(numBeams >= 2) { "beam search needs at least 2 beams; use greedy decoding for 1" }
        require(maxLength >= 2) { "maxLength counts the start token, so it must leave room for one more" }
    }

    /** transformers' `early_stopping`: `False` (the default), `True` and `"never"`. */
    enum class EarlyStopping { Heuristic, WhenFull, Never }

    /** Runs the model one step for all running beams. */
    fun interface Step {
        /**
         * [lastTokens] holds each running beam's newest token. [parents] says, for each running beam, which beam of the
         * previous call it continues, so the model's cache can be reordered first; it is null on the first call, when
         * every beam is the start token alone. Returns the next-token logits of every beam, one row after the other
         * (numBeams × vocabulary). The search may overwrite the array.
         */
        fun logits(lastTokens: IntArray, parents: IntArray?): FloatArray
    }

    /** One candidate continuation: [beam] is the running beam it extends, [token] the token it adds. */
    private class Candidate(val beam: Int, val token: Int, val score: Float)

    /**
     * Decodes from [startToken] and returns the best sequence, start token first, ending with the end-of-sequence token
     * unless the length cap or [isCancelled] stopped it first.
     */
    fun run(startToken: Int, step: Step, isCancelled: () -> Boolean = { false }): IntArray {
        val promptLength = 1
        val keep = 2 * numBeams   // transformers' beams_to_keep = max(2, 1 + number of EOS tokens) * num_beams
        // Running beams: sequences and accumulated log-probabilities. Only the first beam starts live, so the first
        // step does not pick the same token on every beam.
        var running = Array(numBeams) { intArrayOf(startToken) }
        var runningScores = FloatArray(numBeams) { if (it == 0) 0f else -1e9f }
        var parents: IntArray? = null
        // Finished hypotheses: num_beams slots, sorted best first.
        var finished = Array(numBeams) { intArrayOf(startToken) }
        var finishedScores = FloatArray(numBeams) { -1e9f }
        var finishedFlags = BooleanArray(numBeams)
        var improvementPossible = true
        var curLen = promptLength

        while (true) {
            if (isCancelled()) break
            val logits = step.logits(IntArray(numBeams) { running[it].last() }, parents)
            check(logits.isNotEmpty() && logits.size % numBeams == 0) { "the model returned ${logits.size} logits for $numBeams beams" }
            val vocab = logits.size / numBeams

            // b. log_softmax in torch's form, (x - max) - log(sum(exp(x - max))) with the sum in Double; then banned
            // n-grams; plus each beam's running score. c. The top `keep` over all beams: each beam's own top `keep`,
            // merged. Done in place on the model's array: this sees every logit of every beam at every step.
            val perBeam = arrayOfNulls<TopK>(numBeams)
            val score = { b: Int -> perBeam[b] = scoreBeam(logits, b * vocab, vocab, running[b], runningScores[b], keep) }
            if (pool == null) {
                for (b in 0 until numBeams) score(b)
            } else {
                val others = (1 until numBeams).map { b -> pool.submit { score(b) } }
                score(0)
                others.forEach { it.get() }
            }
            val top = TopK(keep)
            for (beam in perBeam) for ((s, i) in beam!!.sorted()) top.offer(s, i)
            val candidates = top.sorted().map { (score, index) -> Candidate((index / vocab).toInt(), (index % vocab).toInt(), score) }

            // d. Which candidates stop here: the end-of-sequence token, or the length cap.
            val stops = BooleanArray(candidates.size) { candidates[it].token == eosTokenId || curLen + 1 >= maxLength }

            // e. The best `numBeams` candidates that did not stop keep running.
            val runningOrder = topIndices(FloatArray(candidates.size) { candidates[it].score + if (stops[it]) -1e9f else 0f }, numBeams)
            val nextRunning = Array(numBeams) { k -> candidates[runningOrder[k]].let { running[it.beam] + it.token } }
            val nextScores = FloatArray(numBeams) { k -> runningOrder[k].let { candidates[it].score + if (stops[it]) -1e9f else 0f } }
            val nextParents = IntArray(numBeams) { k -> candidates[runningOrder[k]].beam }

            // f. Candidates among the top `numBeams` that stopped become finished hypotheses, scored with the length
            // penalty; the best `numBeams` of the old and new ones are kept.
            val norm = ((curLen + 1 - promptLength).toDouble().pow(lengthPenalty.toDouble())).toFloat()
            val full = finishedFlags.all { it } && earlyStopping == EarlyStopping.WhenFull
            val mergedSeqs = ArrayList<IntArray>(numBeams + candidates.size)
            val mergedScores = FloatArray(numBeams + candidates.size)
            val mergedFlags = BooleanArray(numBeams + candidates.size)
            for (j in 0 until numBeams) { mergedSeqs += finished[j]; mergedScores[j] = finishedScores[j]; mergedFlags[j] = finishedFlags[j] }
            for ((k, c) in candidates.withIndex()) {
                val justFinished = stops[k] && k < numBeams
                var s = c.score / norm
                if (full) s += -1e9f
                if (!improvementPossible) s += -1e9f
                if (!justFinished) s += -1e9f
                mergedSeqs += running[c.beam] + c.token
                mergedScores[numBeams + k] = s
                mergedFlags[numBeams + k] = justFinished
            }
            val kept = topIndices(mergedScores, numBeams)
            finished = Array(numBeams) { mergedSeqs[kept[it]] }
            finishedScores = FloatArray(numBeams) { mergedScores[kept[it]] }
            finishedFlags = BooleanArray(numBeams) { mergedFlags[kept[it]] }

            running = nextRunning
            runningScores = nextScores
            parents = nextParents

            // g. Can a running beam still beat the worst finished one? (transformers' early-stop heuristic)
            curLen += 1
            val bestLength = if (earlyStopping == EarlyStopping.Never && lengthPenalty > 0f) maxLength - promptLength else curLen - promptLength
            val bestPossible = runningScores[0] / bestLength.toDouble().pow(lengthPenalty.toDouble()).toFloat()
            val worstFinished = finishedScores.min()
            improvementPossible = improvementPossible && finishedFlags.any { flag -> bestPossible > (if (flag) worstFinished else -1e9f) }

            val openBeam = !(finishedFlags.all { it } && earlyStopping == EarlyStopping.WhenFull)
            val validContinuations = !stops.all { it }
            if (!(improvementPossible && openBeam && validContinuations)) break
        }
        // The best finished hypothesis; if decoding was cancelled before any finished, the best running beam.
        return if (finishedFlags[0]) finished[0] else running[0]
    }

    /** One beam's best [keep] continuations, indexed into the whole logits array. */
    private fun scoreBeam(logits: FloatArray, off: Int, vocab: Int, seq: IntArray, base: Float, keep: Int): TopK {
        var max = Float.NEGATIVE_INFINITY
        for (i in off until off + vocab) if (logits[i] > max) max = logits[i]
        var sum = 0.0
        for (i in off until off + vocab) sum += exp((logits[i] - max).toDouble())
        val logSum = ln(sum).toFloat()
        for (t in Seq2SeqEngine.bannedNextTokens(seq.asList(), noRepeatNgramSize)) {
            if (t in 0 until vocab) logits[off + t] = Float.NEGATIVE_INFINITY
        }
        val top = TopK(keep)
        for (t in 0 until vocab) top.offer(((logits[off + t] - max) - logSum) + base, off.toLong() + t)
        return top
    }

    companion object {
        /** Indices of the [k] largest values, largest first; equal values keep the lower index first. */
        fun topIndices(values: FloatArray, k: Int): IntArray =
            values.indices.sortedWith(compareByDescending<Int> { values[it] }.thenBy { it }).take(k).toIntArray()
    }
}

/**
 * The [capacity] largest (score, index) pairs offered, without sorting everything: a small min-heap. Equal scores keep
 * the lower index, so the result does not depend on the order of offers.
 */
internal class TopK(private val capacity: Int) {
    private val scores = FloatArray(capacity)
    private val indices = LongArray(capacity)
    private var size = 0

    /** True when (a, ia) ranks below (b, ib): a lower score, or the same score and a higher index. */
    private fun below(a: Float, ia: Long, b: Float, ib: Long) = a < b || (a == b && ia > ib)

    fun offer(score: Float, index: Long) {
        if (size == capacity && score < scores[0]) return   // the common case: below the worst kept
        if (score.isNaN()) return
        if (size < capacity) {
            scores[size] = score; indices[size] = index; size++
            var i = size - 1
            while (i > 0) {
                val p = (i - 1) / 2
                if (!below(scores[i], indices[i], scores[p], indices[p])) break
                swap(i, p); i = p
            }
        } else if (below(scores[0], indices[0], score, index)) {
            scores[0] = score; indices[0] = index
            var i = 0
            while (true) {
                val l = 2 * i + 1
                val r = l + 1
                var m = i
                if (l < size && below(scores[l], indices[l], scores[m], indices[m])) m = l
                if (r < size && below(scores[r], indices[r], scores[m], indices[m])) m = r
                if (m == i) break
                swap(i, m); i = m
            }
        }
    }

    /** The pairs held, best first. */
    fun sorted(): List<Pair<Float, Long>> =
        (0 until size).map { scores[it] to indices[it] }.sortedWith(compareByDescending<Pair<Float, Long>> { it.first }.thenBy { it.second })

    private fun swap(a: Int, b: Int) {
        val s = scores[a]; scores[a] = scores[b]; scores[b] = s
        val x = indices[a]; indices[a] = indices[b]; indices[b] = x
    }
}
