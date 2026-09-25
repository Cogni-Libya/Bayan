package ai.bayan.android.ui

import android.content.Context
import android.graphics.Typeface
import androidx.core.content.res.ResourcesCompat
import androidx.test.core.app.ApplicationProvider
import ai.bayan.android.R
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import java.io.File
import java.io.FileInputStream

@RunWith(RobolectricTestRunner::class)
class TypographyTest {

    @Test
    fun testFontAssets_existAndLoadSuccessfullyInResources() {
        val context = ApplicationProvider.getApplicationContext<Context>()

        // 1. Verify Noto Naskh Arabic font resource loads
        val naskhTypeface: Typeface? = ResourcesCompat.getFont(context, R.font.noto_naskh_arabic)
        assertNotNull("R.font.noto_naskh_arabic must resolve to a valid Typeface", naskhTypeface)

        // 2. Verify Noto Sans Arabic font resource loads
        val sansTypeface: Typeface? = ResourcesCompat.getFont(context, R.font.noto_sans_arabic)
        assertNotNull("R.font.noto_sans_arabic must resolve to a valid Typeface", sansTypeface)
    }

    @Test
    fun testFontTypefaces_haveValidProperties() {
        val context = ApplicationProvider.getApplicationContext<Context>()

        val naskhTypeface = ResourcesCompat.getFont(context, R.font.noto_naskh_arabic)
        val sansTypeface = ResourcesCompat.getFont(context, R.font.noto_sans_arabic)

        assertNotNull(naskhTypeface)
        assertNotNull(sansTypeface)

        assertFalse("Noto Naskh Regular typeface should not be italic", naskhTypeface!!.isItalic)
        assertFalse("Noto Sans Regular typeface should not be italic", sansTypeface!!.isItalic)
    }

    @Test
    fun testFontFiles_areGenuineBinaryFontsWithSufficientSize() {
        val possibleFontDirs = listOf(
            File("src/main/res/font"),
            File("app/src/main/res/font"),
            File("app/app/src/main/res/font")
        )
        val fontDir = possibleFontDirs.firstOrNull { it.exists() }
        assertNotNull("Font resource directory res/font must exist in the file tree", fontDir)

        val naskhFile = File(fontDir, "noto_naskh_arabic.ttf")
        val sansFile = File(fontDir, "noto_sans_arabic.ttf")

        assertTrue("noto_naskh_arabic.ttf must exist in res/font/", naskhFile.exists())
        assertTrue(
            "noto_naskh_arabic.ttf must be a genuine binary font (>50KB), but was ${naskhFile.length()} bytes",
            naskhFile.length() > 50_000
        )

        assertTrue("noto_sans_arabic.ttf must exist in res/font/", sansFile.exists())
        assertTrue(
            "noto_sans_arabic.ttf must be a genuine binary font (>50KB), but was ${sansFile.length()} bytes",
            sansFile.length() > 50_000
        )

        // Verify TrueType / OpenType header magic bytes
        // 0x00010000 (TrueType) or 0x4F54544F ('OTTO' for OpenType)
        verifyFontMagic(naskhFile)
        verifyFontMagic(sansFile)
    }

    private fun verifyFontMagic(file: File) {
        FileInputStream(file).use { input ->
            val header = ByteArray(4)
            val read = input.read(header)
            assertEquals("Font file must have at least 4 header bytes", 4, read)
            val isTrueType = header[0] == 0x00.toByte() && header[1] == 0x01.toByte() &&
                    header[2] == 0x00.toByte() && header[3] == 0x00.toByte()
            val isOpenType = header[0] == 0x4F.toByte() && header[1] == 0x54.toByte() &&
                    header[2] == 0x54.toByte() && header[3] == 0x4F.toByte()
            assertTrue(
                "File ${file.name} must start with TrueType (0x00010000) or OpenType ('OTTO') magic bytes, but found plain text or invalid header",
                isTrueType || isOpenType
            )
        }
    }
}
