package ai.bayan.android.download

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import androidx.work.ListenableWorker
import androidx.work.NetworkType
import androidx.work.WorkInfo
import androidx.work.WorkManager
import androidx.work.testing.TestListenableWorkerBuilder
import androidx.work.testing.WorkManagerTestInitHelper
import androidx.work.workDataOf
import ai.bayan.android.engine.DefaultModelStore
import ai.bayan.android.engine.ModelStoreProvider
import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okio.Buffer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.io.File

/**
 * Robolectric and component tests for [DownloadModelWorker] and [ModelDownloadManager].
 *
 * Verifies full model downloads, HTTP Range resumable streaming (206 vs 200),
 * SHA-256 cryptographic verification, corrupted file cleanup, WorkManager unique
 * work KEEP policy, and Wi-Fi constraint enforcement.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class DownloadModelWorkerTest {

    @get:Rule
    val tempFolder = TemporaryFolder()

    private lateinit var context: Context
    private lateinit var mockWebServer: MockWebServer
    private lateinit var modelsDir: File
    private lateinit var downloadManager: ModelDownloadManager

    @Before
    fun setUp() {
        context = ApplicationProvider.getApplicationContext<Context>()
        mockWebServer = MockWebServer()
        mockWebServer.start()

        modelsDir = tempFolder.newFolder("models")
        ModelStoreProvider.reset()
        downloadManager = ModelDownloadManager.getInstance(context)

        // Initialize WorkManager test harness
        WorkManagerTestInitHelper.initializeTestWorkManager(context)
    }

    @After
    fun tearDown() {
        mockWebServer.shutdown()
        ModelStoreProvider.reset()
    }

    @Test
    fun testFullDownload_withMatchingSha256_savesModelFileAndReturnsSuccess() = runBlocking {
        val payload = "Bayan Arabic text simplification neural model weights payload."
        val expectedSha = DefaultModelStore.calculateSha256(payload.byteInputStream())
        val payloadBytes = payload.toByteArray(Charsets.UTF_8)

        mockWebServer.enqueue(
            MockResponse()
                .setResponseCode(200)
                .setHeader("Content-Length", payloadBytes.size)
                .setBody(Buffer().write(payloadBytes))
        )

        val targetFileName = "pytorch_model.bin"
        val worker = TestListenableWorkerBuilder<DownloadModelWorker>(context)
            .setInputData(
                workDataOf(
                    DownloadModelWorker.KEY_URL to mockWebServer.url("/model.bin").toString(),
                    DownloadModelWorker.KEY_EXPECTED_SHA256 to expectedSha,
                    DownloadModelWorker.KEY_MODEL_DIR to modelsDir.absolutePath,
                    DownloadModelWorker.KEY_TARGET_FILENAME to targetFileName
                )
            )
            .build()

        val result = worker.doWork()

        assertEquals("Full download with valid checksum must return success", ListenableWorker.Result.success(), result)

        val targetFile = File(modelsDir, targetFileName)
        val partFile = File(modelsDir, "$targetFileName.part")

        assertTrue("Model file must exist after successful download", targetFile.exists())
        assertEquals("Model file content must match downloaded payload", payload, targetFile.readText())
        assertEquals("Model file SHA-256 must match expected checksum", expectedSha, DefaultModelStore.calculateSha256(targetFile))
        assertFalse("Partial .part file must be cleaned up / renamed", partFile.exists())
    }

    @Test
    fun testResumableDownload_withExistingPartFile_sendsRangeHeaderAndAppends() = runBlocking {
        val fullPayload = "FirstSegment-1234567890---SecondSegment-0987654321---End"
        val fullBytes = fullPayload.toByteArray(Charsets.UTF_8)
        val splitIndex = 20
        val part1Bytes = fullBytes.copyOfRange(0, splitIndex)
        val part2Bytes = fullBytes.copyOfRange(splitIndex, fullBytes.size)

        val targetFileName = "pytorch_model.bin"
        val targetFile = File(modelsDir, targetFileName)
        val partFile = File(modelsDir, "$targetFileName.part")

        // Pre-create partial file with first segment
        partFile.writeBytes(part1Bytes)
        assertEquals(splitIndex.toLong(), partFile.length())

        val expectedSha = DefaultModelStore.calculateSha256(fullPayload.byteInputStream())

        // MockWebServer serves remaining bytes with 206 Partial Content
        mockWebServer.enqueue(
            MockResponse()
                .setResponseCode(206)
                .setHeader("Content-Range", "bytes $splitIndex-${fullBytes.size - 1}/${fullBytes.size}")
                .setHeader("Content-Length", part2Bytes.size)
                .setBody(Buffer().write(part2Bytes))
        )

        val worker = TestListenableWorkerBuilder<DownloadModelWorker>(context)
            .setInputData(
                workDataOf(
                    DownloadModelWorker.KEY_URL to mockWebServer.url("/model.bin").toString(),
                    DownloadModelWorker.KEY_EXPECTED_SHA256 to expectedSha,
                    DownloadModelWorker.KEY_MODEL_DIR to modelsDir.absolutePath,
                    DownloadModelWorker.KEY_TARGET_FILENAME to targetFileName
                )
            )
            .build()

        val result = worker.doWork()

        // Verify Range request header sent by worker
        val recordedRequest = mockWebServer.takeRequest()
        assertEquals("Range header must request bytes from existing part file length", "bytes=$splitIndex-", recordedRequest.getHeader("Range"))

        assertEquals("Resumed download with valid checksum must succeed", ListenableWorker.Result.success(), result)
        assertTrue("Final model file must exist", targetFile.exists())
        assertEquals("Combined payload must match full string", fullPayload, targetFile.readText())
        assertFalse(".part file must no longer exist", partFile.exists())
    }

    @Test
    fun testResumableDownload_serverReturns200InsteadOf206_overwritesPartFileFromZero() = runBlocking {
        val fullPayload = "Entire payload sent by server when Range request is ignored by backend."
        val fullBytes = fullPayload.toByteArray(Charsets.UTF_8)
        val expectedSha = DefaultModelStore.calculateSha256(fullPayload.byteInputStream())

        val targetFileName = "pytorch_model.bin"
        val targetFile = File(modelsDir, targetFileName)
        val partFile = File(modelsDir, "$targetFileName.part")

        // Pre-create partial file with stale garbage bytes
        partFile.writeText("STALE CORRUPT DATA THAT SHOULD BE DISCARDED AND OVERWRITTEN")

        // Server responds with 200 OK (restarting from offset 0)
        mockWebServer.enqueue(
            MockResponse()
                .setResponseCode(200)
                .setHeader("Content-Length", fullBytes.size)
                .setBody(Buffer().write(fullBytes))
        )

        val worker = TestListenableWorkerBuilder<DownloadModelWorker>(context)
            .setInputData(
                workDataOf(
                    DownloadModelWorker.KEY_URL to mockWebServer.url("/model.bin").toString(),
                    DownloadModelWorker.KEY_EXPECTED_SHA256 to expectedSha,
                    DownloadModelWorker.KEY_MODEL_DIR to modelsDir.absolutePath,
                    DownloadModelWorker.KEY_TARGET_FILENAME to targetFileName
                )
            )
            .build()

        val result = worker.doWork()

        assertEquals("Worker must succeed after cleanly restarting from 0", ListenableWorker.Result.success(), result)
        assertTrue("Final model file must exist", targetFile.exists())
        assertEquals("Model file must not have prepended stale bytes", fullPayload, targetFile.readText())
        assertFalse(".part file must be removed", partFile.exists())
    }

    @Test
    fun testCorruptedChecksum_deletesPartFileAndReturnsRetry() = runBlocking {
        val corruptedPayload = "Corrupted or tampered model weights payload."
        val fakeExpectedSha = "b840cd5afdcc806b8175fed5a8800a5aa8be1beb60aab8ab7f650728b122dac2"
        val payloadBytes = corruptedPayload.toByteArray(Charsets.UTF_8)

        mockWebServer.enqueue(
            MockResponse()
                .setResponseCode(200)
                .setHeader("Content-Length", payloadBytes.size)
                .setBody(Buffer().write(payloadBytes))
        )

        val targetFileName = "pytorch_model.bin"
        val targetFile = File(modelsDir, targetFileName)
        val partFile = File(modelsDir, "$targetFileName.part")

        val worker = TestListenableWorkerBuilder<DownloadModelWorker>(context)
            .setInputData(
                workDataOf(
                    DownloadModelWorker.KEY_URL to mockWebServer.url("/model.bin").toString(),
                    DownloadModelWorker.KEY_EXPECTED_SHA256 to fakeExpectedSha,
                    DownloadModelWorker.KEY_MODEL_DIR to modelsDir.absolutePath,
                    DownloadModelWorker.KEY_TARGET_FILENAME to targetFileName
                )
            )
            .build()

        val result = worker.doWork()

        assertTrue("Checksum mismatch must return Retry or Failure", result is ListenableWorker.Result.Retry || result is ListenableWorker.Result.Failure)
        assertFalse("Corrupted .part file MUST be deleted immediately to prevent poison-pill resume loops", partFile.exists())
        assertFalse("Target model file must NOT be created", targetFile.exists())
    }

    @Test
    fun testTargetFileAlreadyValid_skipsDownloadAndReturnsSuccess() = runBlocking {
        val payload = "Existing valid model file content."
        val expectedSha = DefaultModelStore.calculateSha256(payload.byteInputStream())

        val targetFileName = "pytorch_model.bin"
        val targetFile = File(modelsDir, targetFileName)
        targetFile.writeText(payload)

        val worker = TestListenableWorkerBuilder<DownloadModelWorker>(context)
            .setInputData(
                workDataOf(
                    DownloadModelWorker.KEY_URL to mockWebServer.url("/model.bin").toString(),
                    DownloadModelWorker.KEY_EXPECTED_SHA256 to expectedSha,
                    DownloadModelWorker.KEY_MODEL_DIR to modelsDir.absolutePath,
                    DownloadModelWorker.KEY_TARGET_FILENAME to targetFileName
                )
            )
            .build()

        val result = worker.doWork()

        assertEquals("Valid existing target file must return success without downloading", ListenableWorker.Result.success(), result)
        assertEquals("Server must not receive any requests when model is already valid", 0, mockWebServer.requestCount)
    }

    @Test
    fun testUniqueWorkConfiguration_usesKeepPolicy() {
        val request1 = downloadManager.enqueueDownload(wifiOnly = true)
        val workInfos1 = WorkManager.getInstance(context).getWorkInfosForUniqueWork(ModelDownloadManager.WORK_NAME).get()

        assertEquals("Exactly one work request must be enqueued", 1, workInfos1.size)
        val originalId = workInfos1[0].id
        assertEquals(request1.id, originalId)

        // Attempt second enqueue with KEEP policy
        val request2 = downloadManager.enqueueDownload(wifiOnly = true)
        val workInfos2 = WorkManager.getInstance(context).getWorkInfosForUniqueWork(ModelDownloadManager.WORK_NAME).get()

        assertEquals("WorkManager must retain unique work instance under KEEP policy", 1, workInfos2.size)
        assertEquals("Work ID must be preserved, not overwritten", originalId, workInfos2[0].id)
    }

    @Test
    fun testWorkConstraints_wifiConstraintApplied() {
        val requestWifiOnly = downloadManager.buildDownloadRequest(wifiOnly = true)
        assertEquals(
            "Wi-Fi only download must require UNMETERED network",
            NetworkType.UNMETERED,
            requestWifiOnly.workSpec.constraints.requiredNetworkType
        )

        val requestAnyNetwork = downloadManager.buildDownloadRequest(wifiOnly = false)
        assertEquals(
            "Non Wi-Fi download must require CONNECTED network",
            NetworkType.CONNECTED,
            requestAnyNetwork.workSpec.constraints.requiredNetworkType
        )
    }

    @Test
    fun testCancelDownload_cancelsUniqueWork() {
        downloadManager.enqueueDownload(wifiOnly = false)
        downloadManager.cancelDownload()

        val workInfos = WorkManager.getInstance(context).getWorkInfosForUniqueWork(ModelDownloadManager.WORK_NAME).get()
        assertTrue(
            "Cancelled work must transition to CANCELLED state",
            workInfos.all { it.state == WorkInfo.State.CANCELLED }
        )
    }

    @Test
    fun testDownload_http416RangeNotSatisfiable_deletesPartFileAndReturnsRetry() = runBlocking {
        val targetFileName = "pytorch_model.bin"
        val partFile = File(modelsDir, "$targetFileName.part")
        partFile.writeBytes(ByteArray(1024) { 0x11 })
        assertTrue(partFile.exists())

        mockWebServer.enqueue(
            MockResponse().setResponseCode(416)
        )

        val worker = TestListenableWorkerBuilder<DownloadModelWorker>(context)
            .setInputData(
                workDataOf(
                    DownloadModelWorker.KEY_URL to mockWebServer.url("/model.bin").toString(),
                    DownloadModelWorker.KEY_EXPECTED_SHA256 to "dummy_sha256",
                    DownloadModelWorker.KEY_MODEL_DIR to modelsDir.absolutePath,
                    DownloadModelWorker.KEY_TARGET_FILENAME to targetFileName
                )
            )
            .build()

        val result = worker.doWork()

        assertEquals(ListenableWorker.Result.retry(), result)
        assertFalse("HTTP 416 must delete invalid/out-of-range .part file", partFile.exists())
    }

    @Test
    fun testDownload_http500InternalServerError_preservesPartFileAndReturnsRetry() = runBlocking {
        val targetFileName = "pytorch_model.bin"
        val partFile = File(modelsDir, "$targetFileName.part")
        val initialBytes = ByteArray(500) { 0x22 }
        partFile.writeBytes(initialBytes)

        mockWebServer.enqueue(
            MockResponse().setResponseCode(500).setBody("Internal Server Error")
        )

        val worker = TestListenableWorkerBuilder<DownloadModelWorker>(context)
            .setInputData(
                workDataOf(
                    DownloadModelWorker.KEY_URL to mockWebServer.url("/model.bin").toString(),
                    DownloadModelWorker.KEY_EXPECTED_SHA256 to "dummy_sha256",
                    DownloadModelWorker.KEY_MODEL_DIR to modelsDir.absolutePath,
                    DownloadModelWorker.KEY_TARGET_FILENAME to targetFileName
                )
            )
            .build()

        val result = worker.doWork()

        assertEquals(ListenableWorker.Result.retry(), result)
        assertTrue("Transient HTTP 500 must NOT delete valid partial file", partFile.exists())
        assertEquals(500L, partFile.length())
    }

    @Test
    fun testDownload_http302Redirect_followsRedirectAndCompletesDownload() = runBlocking {
        val payload = "Redirected model weights payload content."
        val expectedSha = DefaultModelStore.calculateSha256(payload.byteInputStream())
        val payloadBytes = payload.toByteArray(Charsets.UTF_8)

        mockWebServer.enqueue(
            MockResponse()
                .setResponseCode(302)
                .setHeader("Location", mockWebServer.url("/cdn/final_weights.bin").toString())
        )
        mockWebServer.enqueue(
            MockResponse()
                .setResponseCode(200)
                .setHeader("Content-Length", payloadBytes.size.toLong())
                .setBody(Buffer().write(payloadBytes))
        )

        val targetFileName = "pytorch_model.bin"
        val worker = TestListenableWorkerBuilder<DownloadModelWorker>(context)
            .setInputData(
                workDataOf(
                    DownloadModelWorker.KEY_URL to mockWebServer.url("/model.bin").toString(),
                    DownloadModelWorker.KEY_EXPECTED_SHA256 to expectedSha,
                    DownloadModelWorker.KEY_MODEL_DIR to modelsDir.absolutePath,
                    DownloadModelWorker.KEY_TARGET_FILENAME to targetFileName
                )
            )
            .build()

        val result = worker.doWork()

        assertEquals(ListenableWorker.Result.success(), result)
        val targetFile = File(modelsDir, targetFileName)
        assertTrue(targetFile.exists())
        assertEquals(payload, targetFile.readText())
    }
}

