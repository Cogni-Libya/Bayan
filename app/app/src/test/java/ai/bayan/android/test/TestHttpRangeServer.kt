package ai.bayan.android.test

import com.sun.net.httpserver.HttpExchange
import com.sun.net.httpserver.HttpHandler
import com.sun.net.httpserver.HttpServer
import java.net.InetSocketAddress
import java.util.concurrent.Executors

/**
 * Lightweight, in-process HTTP test server providing deterministic HTTP Range request
 * handling, partial content streaming (HTTP 206), full downloads (HTTP 200), and
 * corruption simulation for Tier 4 end-to-end user journey testing.
 */
class TestHttpRangeServer(
    private val payload: ByteArray
) {
    private var server: HttpServer? = null
    var port: Int = 0
        private set
    var lastRequestedRange: String? = null
        private set
    var requestCount: Int = 0
        private set
    var forceHttp200: Boolean = false
    var serveCorruptedPayload: Boolean = false

    fun start() {
        val server = HttpServer.create(InetSocketAddress("127.0.0.1", 0), 0)
        port = server.address.port
        server.executor = Executors.newCachedThreadPool()
        server.createContext("/model.bin", HttpHandler { exchange ->
            handleRequest(exchange)
        })
        server.start()
        this.server = server
    }

    private fun handleRequest(exchange: HttpExchange) {
        requestCount++
        val rangeHeader = exchange.requestHeaders.getFirst("Range")
        lastRequestedRange = rangeHeader

        val dataToServe = if (serveCorruptedPayload) {
            payload.map { (it.toInt() xor 0xFF).toByte() }.toByteArray()
        } else {
            payload
        }

        if (rangeHeader != null && rangeHeader.startsWith("bytes=") && !forceHttp200) {
            val rangeSpec = rangeHeader.removePrefix("bytes=").trim()
            val parts = rangeSpec.split("-")
            val start = parts[0].toIntOrNull() ?: 0
            val end = if (parts.size > 1 && parts[1].isNotEmpty()) {
                parts[1].toIntOrNull() ?: (dataToServe.size - 1)
            } else {
                dataToServe.size - 1
            }

            if (start >= dataToServe.size) {
                exchange.sendResponseHeaders(416, -1) // Range Not Satisfiable
                exchange.close()
                return
            }

            val length = (end - start + 1).coerceAtMost(dataToServe.size - start)
            exchange.responseHeaders.set(
                "Content-Range",
                "bytes $start-${start + length - 1}/${dataToServe.size}"
            )
            exchange.responseHeaders.set("Content-Type", "application/octet-stream")
            exchange.sendResponseHeaders(206, length.toLong())

            exchange.responseBody.use { os ->
                os.write(dataToServe, start, length)
                os.flush()
            }
        } else {
            exchange.responseHeaders.set("Content-Type", "application/octet-stream")
            exchange.sendResponseHeaders(200, dataToServe.size.toLong())
            exchange.responseBody.use { os ->
                os.write(dataToServe)
                os.flush()
            }
        }
    }

    fun url(): String = "http://127.0.0.1:$port/model.bin"

    fun stop() {
        server?.stop(0)
        server = null
    }
}
