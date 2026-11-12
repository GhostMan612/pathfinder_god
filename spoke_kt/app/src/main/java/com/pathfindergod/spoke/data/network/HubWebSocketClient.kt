// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.network

import com.pathfindergod.spoke.data.security.CredentialVault
import com.pathfindergod.spoke.data.security.SpokeCredentialVault
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

class HubAuthenticationException(
    val code: Int,
    message: String,
) : Exception(message)

@Serializable
data class StreamAskRequest(
    val query: String,
    val edition: String = "both",
    val mode: String? = null,
    val history: List<List<String>> = emptyList(),
)

@Serializable
data class StreamTurnRequest(
    val type: String = "turn",
    @SerialName("campaign_id") val campaignId: Int,
    val action: String,
    val actor: String = "player",
    val seed: Int? = null,
)

@Serializable
data class StreamEvent(
    val type: String,
    val backend: String? = null,
    val mode: String? = null,
    val edition: String? = null,
    val text: String? = null,
    val message: String? = null,
    val sources: List<JsonElement> = emptyList(),
    @SerialName("campaign_id") val campaignId: Int? = null,
    @SerialName("turn_num") val turnNum: Int? = null,
    val phase: String? = null,
    val round: Int? = null,
    @SerialName("dice_rolls") val diceRolls: List<Map<String, JsonElement>> = emptyList(),
    @SerialName("hp_changes") val hpChanges: List<Map<String, JsonElement>> = emptyList(),
    val conditions: List<Map<String, JsonElement>> = emptyList(),
    val result: TurnResponse? = null,
)

fun interface GmStreamSource {
    fun streamTurn(
        url: String,
        campaignId: Int,
        action: String,
        actor: String,
        seed: Int?,
    ): Flow<StreamEvent>
}

class HubWebSocketClient(
    private val client: OkHttpClient? = null,
    private val vault: CredentialVault? = null,
) : GmStreamSource {
    private val json = Json { ignoreUnknownKeys = true; explicitNulls = false }

    @Volatile
    private var socket: WebSocket? = null

    private val _events = MutableSharedFlow<StreamEvent>(extraBufferCapacity = 64)
    val events: SharedFlow<StreamEvent> = _events.asSharedFlow()

    private fun resolveClient(): OkHttpClient = client ?: HubApiFactory.okHttpClient

    fun stream(url: String, query: String, edition: String = "both"): Flow<StreamEvent> =
        callbackFlow {
            val okHttp = resolveClient()
            val activeVault = vault ?: SpokeCredentialVault.instanceOrNull()
            val requestBuilder = Request.Builder().url(url)
            activeVault?.getApiKey(url)?.trim()?.takeIf { it.isNotEmpty() }?.let { key ->
                requestBuilder.header(ApiKeyInterceptor.API_KEY_HEADER, key)
            }
            val request = requestBuilder.build()
            val listener = object : WebSocketListener() {
                override fun onOpen(webSocket: WebSocket, response: Response) {
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
                    webSocket.close(1000, null)
                }

                override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                    val code = response?.code
                    val isAuth = code in listOf(401, 403) ||
                        t.message?.contains("401") == true ||
                        t.message?.contains("403") == true
                    if (isAuth) {
                        close(HubAuthenticationException(code ?: 401, "Authentication failed: HTTP ${code ?: 401}"))
                    } else {
                        close(t)
                    }
                }

                override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                    close()
                }
            }
            val ws = okHttp.newWebSocket(request, listener)
            socket = ws
            awaitClose {
                if (socket === ws) {
                    ws.close(1000, "collector gone")
                    socket = null
                }
            }
        }

    override fun streamTurn(
        url: String,
        campaignId: Int,
        action: String,
        actor: String,
        seed: Int?,
    ): Flow<StreamEvent> = callbackFlow {
        val okHttp = resolveClient()
        val activeVault = vault ?: SpokeCredentialVault.instanceOrNull()
        val requestBuilder = Request.Builder().url(url)
        activeVault?.getApiKey(url)?.trim()?.takeIf { it.isNotEmpty() }?.let { key ->
            requestBuilder.header(ApiKeyInterceptor.API_KEY_HEADER, key)
        }
        val request = requestBuilder.build()
        val listener = object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                val payload = json.encodeToString(
                    StreamTurnRequest.serializer(),
                    StreamTurnRequest(
                        campaignId = campaignId,
                        action = action,
                        actor = actor,
                        seed = seed,
                    ),
                )
                webSocket.send(payload)
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
                webSocket.close(1000, null)
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                val code = response?.code
                val isAuth = code in listOf(401, 403) ||
                    t.message?.contains("401") == true ||
                    t.message?.contains("403") == true
                if (isAuth) {
                    close(HubAuthenticationException(code ?: 401, "Authentication failed: HTTP ${code ?: 401}"))
                } else {
                    close(t)
                }
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                close()
            }
        }
        val ws = okHttp.newWebSocket(request, listener)
        socket = ws
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

    fun shutdown() {
        close()
        client?.let {
            it.dispatcher.cancelAll()
            it.dispatcher.executorService.shutdown()
            it.connectionPool.evictAll()
        }
    }
}
