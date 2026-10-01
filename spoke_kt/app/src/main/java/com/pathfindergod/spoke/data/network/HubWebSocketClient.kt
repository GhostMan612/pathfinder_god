// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.network

import java.util.concurrent.TimeUnit
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonElement
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener

/** Body the Hub's /stream handler blocks on before it emits anything. */
@Serializable
data class StreamAskRequest(
    val query: String,
    val edition: String = "both",
    val mode: String? = null,
    val history: List<List<String>> = emptyList(),
)

/** One frame from the Hub: start | chunk | end | error. */
@Serializable
data class StreamEvent(
    val type: String,
    val backend: String? = null,
    val mode: String? = null,
    val edition: String? = null,
    val text: String? = null,
    val message: String? = null,
    val sources: List<JsonElement> = emptyList(),
)

class HubWebSocketClient(
    private val client: OkHttpClient = OkHttpClient.Builder()
        .pingInterval(15, TimeUnit.SECONDS)
        .retryOnConnectionFailure(true)
        .build(),
) {
    private val json = Json { ignoreUnknownKeys = true; explicitNulls = false }

    // Written by the callbackFlow producer and read from other threads.
    @Volatile
    private var socket: WebSocket? = null

    private val _events = MutableSharedFlow<StreamEvent>(extraBufferCapacity = 64)
    val events: SharedFlow<StreamEvent> = _events.asSharedFlow()

    /**
     * Connect and emit the parsed [StreamEvent] frames the Hub sends for [query].
     *
     * This previously opened a socket and said nothing. The Hub's handler
     * `await`s `receive_json()` before it sends anything, so not one frame was
     * ever received, the status stayed CONNECTING forever, and the reconnect
     * loop described in AGENTS.md could not work. It also forwarded raw
     * strings that nothing ever deserialized, so the StreamEvent envelope was
     * never read.
     */
    fun stream(url: String, query: String, edition: String = "both"): Flow<StreamEvent> =
        callbackFlow {
            val request = Request.Builder().url(url).build()
            val listener = object : WebSocketListener() {
                override fun onOpen(webSocket: WebSocket, response: Response) {
                    // The Hub blocks on receive_json(); we must speak first.
                    val hello = json.encodeToString(
                        StreamAskRequest.serializer(),
                        StreamAskRequest(query = query, edition = edition),
                    )
                    webSocket.send(hello)
                }

                override fun onMessage(webSocket: WebSocket, text: String) {
                    val event = runCatching {
                        json.decodeFromString(StreamEvent.serializer(), text)
                    }.getOrNull()
                    if (event != null) {
                        trySend(event)
                        _events.tryEmit(event)
                    }
                }

                override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                    // Complete the close handshake, otherwise the Hub logs an
                    // abnormal closure on every disconnect.
                    webSocket.close(1000, null)
                }

                override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                    close(t)
                }

                override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                    close()
                }
            }
            val ws = client.newWebSocket(request, listener)
            socket = ws
            // Only tear down OUR socket. Cancelling a collector is asynchronous,
            // so a stale awaitClose used to fire after a reconnect had already
            // opened a new socket and close() it.
            awaitClose {
                if (socket === ws) {
                    ws.close(1000, "collector gone")
                    socket = null
                }
            }
        }

    fun send(text: String): Boolean {
        val active = socket ?: return false
        return active.send(text)
    }

    fun close(code: Int = 1000, reason: String = "done") {
        socket?.close(code, reason)
        socket = null
    }

    /** Releases the dispatcher threads and the connection pool.

     * START_STICKY guarantees the owning service is recreated, so without this
     * each recreation leaked two dispatcher threads plus a keep-alive thread.
     */
    fun shutdown() {
        close()
        client.dispatcher.cancelAll()
        client.dispatcher.executorService.shutdown()
        client.connectionPool.evictAll()
    }
}