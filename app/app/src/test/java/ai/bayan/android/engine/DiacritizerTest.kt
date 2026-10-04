package ai.bayan.android.engine

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

class DiacritizerTest {
    @Serializable private data class Case(val `in`: String, val out: String)
    @Serializable private data class Fixtures(val text2tashkeel: String, val model: String, val cases: List<Case>)

    private val diacritizer by lazy {
        val dir = File("src/main/assets/tashkeel")
        Diacritizer(File(dir, "libtashkeel.onnx").readBytes(), File(dir, "libtashkeel.maps.json").readText())
    }

    /** The port gives text2tashkeel's own output, character for character (tools/tashkeel_fixtures.py). */
    @Test
    fun matchesText2tashkeelOnEveryFixture() {
        val fx = Json.decodeFromString(Fixtures.serializer(), javaClass.classLoader!!.getResource("tashkeel_fixtures.json")!!.readText())
        val wrong = fx.cases.filter { diacritizer.diacritize(it.`in`) != it.out }
        assertTrue("${wrong.size} of ${fx.cases.size} differ, e.g. ${wrong.take(2)}", wrong.isEmpty())
        assertTrue(fx.cases.size > 300)
    }

    /** Only marks are added: with them stripped, every output is its input with marks stripped. */
    @Test
    fun neverChangesALetter() {
        val fx = Json.decodeFromString(Fixtures.serializer(), javaClass.classLoader!!.getResource("tashkeel_fixtures.json")!!.readText())
        for (c in fx.cases) assertEquals(Diacritizer.strip(c.`in`), Diacritizer.strip(diacritizer.diacritize(c.`in`)))
    }
}
