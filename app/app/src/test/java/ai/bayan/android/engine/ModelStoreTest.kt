package ai.bayan.android.engine

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okio.Buffer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertSame
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.io.File
import java.security.MessageDigest

/**
 * Unit and component tests for [ModelStore], [DefaultModelStore], and [ModelStoreProvider].
 *
 * Verifies model readiness checks, SHA-256 streaming verification, corrupted file deletion,
 * directory creation, and provider singleton management.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class ModelStoreTest {

    @get:Rule
    val tempFolder = TemporaryFolder()

    private lateinit var context: Context

    @Before
    fun setUp() {
        context = ApplicationProvider.getApplicationContext<Context>()
        ModelStoreProvider.reset()
    }

    @After
    fun tearDown() {
        ModelStoreProvider.reset()
    }

    @Test
    fun testIsReady_whenModelFileDoesNotExist_returnsFalse() {
        val modelsDir = tempFolder.newFolder("models")
        val store = DefaultModelStore(
            context = context,
            customModelDir = modelsDir
        )

        assertFalse("Model file must not exist initially", store.getModelFile().exists())
        assertFalse("isReady() must return false when model file does not exist", store.isReady())
    }

    @Test
    fun testIsReady_whenOnlyPartFileExists_returnsFalse() {
        val modelsDir = tempFolder.newFolder("models")
        val store = DefaultModelStore(
            context = context,
            customModelDir = modelsDir
        )

        // Write partial download content
        store.getPartFile().writeBytes(byteArrayOf(1, 2, 3, 4, 5))

        assertTrue("Part file must exist", store.getPartFile().exists())
        assertFalse("Model file must not exist", store.getModelFile().exists())
        assertFalse("isReady() must return false when only part file exists", store.isReady())
        assertTrue(
            "Part file should not be removed by isReady when model file does not exist",
            store.getPartFile().exists()
        )
    }

    @Test
    fun testIsReady_whenModelFileExistsAndChecksumMatches_returnsTrue() {
        val modelsDir = tempFolder.newFolder("models")
        val testContent = "Bayan Arabic text simplification model weights test payload."
        val expectedSha = DefaultModelStore.calculateSha256(testContent.byteInputStream())

        val store = DefaultModelStore(
            context = context,
            expectedSha256 = expectedSha,
            customModelDir = modelsDir
        )

        store.getModelFile().writeText(testContent)

        assertTrue("Model file must exist", store.getModelFile().exists())
        assertTrue("isReady() must return true when checksum matches", store.isReady())
        assertTrue("Model file must still exist after successful verification", store.getModelFile().exists())
    }

    @Test
    fun testIsReady_whenModelFileExistsButChecksumMismatched_deletesFileAndReturnsFalse() {
        val modelsDir = tempFolder.newFolder("models")
        val corruptedContent = "Corrupted model weights payload"
        val expectedValidSha = "0000000000000000000000000000000000000000000000000000000000000000"

        val store = DefaultModelStore(
            context = context,
            expectedSha256 = expectedValidSha,
            customModelDir = modelsDir
        )

        store.getModelFile().writeText(corruptedContent)
        store.getPartFile().writeText("leftover partial content")

        assertTrue("Model file must exist before check", store.getModelFile().exists())
        assertTrue("Part file must exist before check", store.getPartFile().exists())

        val ready = store.isReady()

        assertFalse("isReady() must return false on checksum mismatch", ready)
        assertFalse("Corrupted model file must be deleted on checksum mismatch", store.getModelFile().exists())
        assertFalse("Part file must also be cleaned up on corruption detection", store.getPartFile().exists())
    }

    @Test
    fun testSha256ChecksumCalculation_matchesKnownStandardVectors() {
        // Standard NIST / RFC 6234 test vectors
        val vectors = mapOf(
            "" to "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "abc" to "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
            "The quick brown fox jumps over the lazy dog" to "d7a8fbb307d7809469ca9abcb0082e4f8d5651e46d3cdb762d02d0bf37c9e592"
        )

        for ((input, expectedDigest) in vectors) {
            val file = tempFolder.newFile()
            file.writeText(input)

            val fromFile = DefaultModelStore.calculateSha256(file)
            assertEquals(
                "File-based SHA-256 calculation must match test vector for input '$input'",
                expectedDigest,
                fromFile
            )

            val fromStream = DefaultModelStore.calculateSha256(input.byteInputStream())
            assertEquals(
                "Stream-based SHA-256 calculation must match test vector for input '$input'",
                expectedDigest,
                fromStream
            )
        }
    }

    @Test
    fun testModelDir_createsAndReturnsDirectory() {
        val nonExistentDir = File(tempFolder.root, "nested/path/to/models")
        assertFalse("Target directory must not exist prior to calling modelDir()", nonExistentDir.exists())

        val store = DefaultModelStore(
            context = context,
            customModelDir = nonExistentDir
        )

        val dir = store.modelDir()
        assertNotNull("modelDir() must not be null", dir)
        assertTrue("modelDir() must create directory if it does not exist", dir.exists())
        assertTrue("modelDir() must be a directory", dir.isDirectory)
        assertEquals(nonExistentDir.canonicalPath, dir.canonicalPath)
    }

    @Test
    fun testDeleteCorruptedFiles_removesBothPartAndFinalFiles() {
        val modelsDir = tempFolder.newFolder("models")
        val store = DefaultModelStore(
            context = context,
            customModelDir = modelsDir
        )

        store.getModelFile().writeText("final model content")
        store.getPartFile().writeText("partial download content")

        assertTrue("Model file must exist", store.getModelFile().exists())
        assertTrue("Part file must exist", store.getPartFile().exists())

        store.deleteCorruptedFiles()

        assertFalse("Model file must be deleted", store.getModelFile().exists())
        assertFalse("Part file must be deleted", store.getPartFile().exists())
    }

    @Test
    fun testModelStoreProvider_singletonManagementAndOverride() {
        ModelStoreProvider.reset()
        val defaultInstance = ModelStoreProvider.getInstance(context)
        assertNotNull("ModelStoreProvider must provide default instance", defaultInstance)
        assertTrue("Default instance must be DefaultModelStore", defaultInstance is DefaultModelStore)

        val sameInstance = ModelStoreProvider.getInstance(context)
        assertSame("Subsequent calls must return singleton instance", defaultInstance, sameInstance)

        val customStore = object : ModelStore {
            override fun isReady(): Boolean = true
            override suspend fun download(onProgress: (Float) -> Unit) {}
            override fun modelDir(): File = tempFolder.root
            override fun getModelFile(): File = File(tempFolder.root, "custom.bin")
            override fun getPartFile(): File = File(tempFolder.root, "custom.bin.part")
            override fun getExpectedSha256(): String = "custom_hash"
            override fun getDownloadUrl(): String = "https://example.com/custom.bin"
            override fun deleteCorruptedFiles() {}
        }

        ModelStoreProvider.setInstance(customStore)
        assertSame("Provider must return custom instance", customStore, ModelStoreProvider.getInstance(context))

        ModelStoreProvider.reset()
        val restoredInstance = ModelStoreProvider.getInstance(context)
        assertNotNull(restoredInstance)
        assertTrue("Instance must be reset to DefaultModelStore", restoredInstance is DefaultModelStore)
    }

    @Test
    fun testDefaultConfigurationConstants() {
        val store = DefaultModelStore(context = context)
        assertEquals(
            "Default download URL must match huggingface t5-efficient-tiny weights",
            "https://huggingface.co/google/t5-efficient-tiny/resolve/main/pytorch_model.bin",
            store.getDownloadUrl()
        )
        assertEquals(
            "Default expected SHA-256 must match specification",
            "b840cd5afdcc806b8175fed5a8800a5aa8be1beb60aab8ab7f650728b122dac2",
            store.getExpectedSha256()
        )
        assertEquals("pytorch_model.bin", store.getModelFile().name)
        assertEquals("pytorch_model.bin.part", store.getPartFile().name)
    }

    @Test
    fun testSha256ChecksumCalculation_bufferBoundaryConditions() {
        val testSizes = listOf(0, 1, 8191, 8192, 8193, 16384, 65536)
        val md = MessageDigest.getInstance("SHA-256")

        for (size in testSizes) {
            val bytes = ByteArray(size) { (it % 251).toByte() }
            val expectedSha = md.digest(bytes).joinToString("") { "%02x".format(it) }

            val file = tempFolder.newFile()
            file.writeBytes(bytes)

            val actualFromFile = DefaultModelStore.calculateSha256(file)
            val actualFromStream = DefaultModelStore.calculateSha256(bytes.byteInputStream())

            assertEquals("Boundary size $size mismatch from file", expectedSha, actualFromFile)
            assertEquals("Boundary size $size mismatch from stream", expectedSha, actualFromStream)
        }
    }

    @Test
    fun testDefaultModelStore_download_streamsAndCompletesSuccessfully() = runBlocking {
        val payload = "DefaultModelStore standalone download test payload."
        val expectedSha = DefaultModelStore.calculateSha256(payload.byteInputStream())
        val payloadBytes = payload.toByteArray(Charsets.UTF_8)

        val mockServer = MockWebServer()
        mockServer.start()
        mockServer.enqueue(
            MockResponse()
                .setResponseCode(200)
                .setHeader("Content-Length", payloadBytes.size.toLong())
                .setBody(Buffer().write(payloadBytes))
        )

        val modelsDir = tempFolder.newFolder("standalone_models")
        val store = DefaultModelStore(
            context = context,
            downloadUrl = mockServer.url("/model.bin").toString(),
            expectedSha256 = expectedSha,
            customModelDir = modelsDir
        )

        val progressReports = mutableListOf<Float>()
        store.download { progressReports.add(it) }

        assertTrue("isReady() must be true after store.download()", store.isReady())
        assertTrue("Target model file must exist", store.getModelFile().exists())
        assertEquals(payload, store.getModelFile().readText())
        assertFalse(".part file must not exist", store.getPartFile().exists())
        assertTrue("Progress reports must include 1.0f", progressReports.contains(1.0f))

        mockServer.shutdown()
    }
}

