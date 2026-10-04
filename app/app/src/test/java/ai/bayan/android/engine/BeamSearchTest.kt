package ai.bayan.android.engine

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.random.Random

class BeamSearchTest {

    @Serializable
    private data class Case(
        val seed: Long, val pull: Float, val vocab: Int, val max_length: Int, val beams: Int, val length_penalty: Float,
        val early_stopping: String, val no_repeat_ngram: Int, val near_tie: Boolean, val output: List<Int>,
    )

    @Serializable
    private data class Fixtures(val transformers: String, val eos: Int, val start: Int, val cases: List<Case>)

    /** The toy model of tools/beam_fixtures.py, in the same integer and Float arithmetic. */
    private fun toyLogits(seed: Long, prefix: IntArray, vocab: Int, pull: Float, eos: Int): FloatArray {
        var h = seed
        for (t in prefix) h = (h * 1_000_003 + t + 1) % 2_147_483_647
        val out = FloatArray(vocab) { v -> ((h * 2_654_435_761 + v * 40_503L + v.toLong() * v * 97) % 1_000_003).toFloat() / 250_000f }
        out[eos] += prefix.size.toFloat() * pull
        return out
    }

    /** A Step that keeps each beam's sequence itself and reorders it by `parents`, as the engine reorders its cache. */
    private class ToyStep(beams: Int, start: Int, val logits: (IntArray) -> FloatArray) : BeamSearch.Step {
        var seqs = Array(beams) { intArrayOf(start) }
        override fun logits(lastTokens: IntArray, parents: IntArray?): FloatArray {
            if (parents != null) seqs = Array(seqs.size) { seqs[parents[it]] + lastTokens[it] }
            return seqs.map { logits(it) }.reduce { a, b -> a + b }
        }
    }

    /**
     * Every case whose decisions are clear of float rounding must match transformers token for token. Cases with a
     * near tie (two candidates within 1e-5 at a decision, see tools/beam_fixtures.py) can legitimately go either way,
     * since torch's float32 log_softmax cannot be reproduced bit for bit; most of them still match.
     */
    @Test
    fun matchesTransformersOnEveryFixture() {
        val text = javaClass.classLoader!!.getResource("beam_fixtures.json")!!.readText()
        val fx = Json.decodeFromString(Fixtures.serializer(), text)
        assertEquals("4.57.6", fx.transformers)
        val strict = ArrayList<String>()
        var tiesMatched = 0
        for (c in fx.cases) {
            val search = BeamSearch(c.beams, fx.eos, c.max_length, c.no_repeat_ngram, c.length_penalty, BeamSearch.EarlyStopping.valueOf(c.early_stopping))
            val got = search.run(fx.start, ToyStep(c.beams, fx.start) { toyLogits(c.seed, it, c.vocab, c.pull, fx.eos) })
            val same = got.toList() == c.output
            if (c.near_tie) { if (same) tiesMatched++ } else if (!same) strict += "$c\n  got ${got.toList()}"
        }
        val ties = fx.cases.count { it.near_tie }
        println("beam fixtures: ${fx.cases.size - ties} clear cases all match; near ties $tiesMatched of $ties match")
        assertTrue("${strict.size} of ${fx.cases.size - ties} clear cases differ from transformers:\n" + strict.take(5).joinToString("\n"), strict.isEmpty())
        assertTrue("too few clear cases: ${fx.cases.size - ties}", fx.cases.size - ties >= 500)
        assertTrue("only $tiesMatched of $ties near-tie cases match", tiesMatched * 2 > ties)
    }

    @Test
    fun scoringBeamsInParallelGivesTheSameResult() {
        val pool = java.util.concurrent.Executors.newFixedThreadPool(3)
        try {
            repeat(60) { seed ->
                val model = { p: IntArray -> toyLogits(seed.toLong(), p, 29, 0.1f, 1) }
                val alone = BeamSearch(4, 1, 25, 3).run(0, ToyStep(4, 0, model))
                val parallel = BeamSearch(4, 1, 25, 3, pool = pool).run(0, ToyStep(4, 0, model))
                assertEquals(alone.toList(), parallel.toList())
            }
        } finally {
            pool.shutdown()
        }
    }

    @Test
    fun noRepeatedNgramsInTheOutput() {
        repeat(50) { seed ->
            val out = BeamSearch(4, 1, 40, 3).run(0, ToyStep(4, 0) { toyLogits(seed.toLong(), it, 9, 0.02f, 1) })
            val grams = out.toList().windowed(3)
            assertEquals("seed $seed: ${out.toList()}", grams.size, grams.toSet().size)
        }
    }

    @Test
    fun cancellingReturnsTheBestRunningBeam() {
        var calls = 0
        val out = BeamSearch(4, 1, 100, 0).run(0, ToyStep(4, 0) { toyLogits(3, it, 50, 0f, 1).also { l -> l[1] = -100f } }) { calls++ >= 3 }
        assertEquals(4, out.size)   // start + three decoded tokens
    }

    @Test
    fun theFirstStepSeesOnlyStartTokens() {
        var first: IntArray? = null
        BeamSearch(3, 1, 10, 0).run(5, BeamSearch.Step { last, parents ->
            if (parents == null) first = last
            FloatArray(3 * 8) { i -> if (i % 8 == 1) 10f else 0f }
        })
        assertArrayEquals(intArrayOf(5, 5, 5), first)
    }

    @Test
    fun topKAgreesWithAFullSort() {
        val rnd = Random(11)
        repeat(200) {
            val n = rnd.nextInt(1, 400)
            val k = rnd.nextInt(1, 12)
            // a coarse grid makes ties common, to check that the lower index wins them
            val values = FloatArray(n) { rnd.nextInt(-20, 20) / 4f }
            val top = TopK(k).apply { values.forEachIndexed { i, v -> offer(v, i.toLong()) } }.sorted().map { it.second.toInt() }
            assertEquals(BeamSearch.topIndices(values, k).toList(), top)
        }
    }

}
