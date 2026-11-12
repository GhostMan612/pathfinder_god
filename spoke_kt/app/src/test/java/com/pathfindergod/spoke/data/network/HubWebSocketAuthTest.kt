// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.network

import com.pathfindergod.spoke.data.security.CredentialVault
import com.pathfindergod.spoke.data.security.VaultState
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.flow.launchIn
import okhttp3.OkHttpClient
import okhttp3.Protocol
import okhttp3.Response
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class HubWebSocketAuthTest {

    private class MockVault(
        private val boundHubUrl: String? = null,
        private val key: String? = null,
    ) : CredentialVault {
        override fun getState(): VaultState = if (key != null || boundHubUrl != null) VaultState.READY else VaultState.EMPTY
        override fun getHubUrl(): String? = boundHubUrl
        override fun getApiKey(endpoint: String?): String? {
            if (endpoint != null && boundHubUrl != null && !endpoint.startsWith(boundHubUrl.trimEnd('/'))) {
                return null
            }
            return key
        }
        override fun setApiKey(key: String?) {}
        override fun getCertificatePin(endpoint: String?): String? = null
        override fun setCertificatePin(pin: String?) {}
        override fun setCredentials(hubUrl: String, apiKey: String?, pin: String?) {}
        override fun clear() {}
    }

    private fun createInterceptingClient(
        capturedHeader: AtomicReference<String?>,
        latch: CountDownLatch,
        responseCode: Int = 401,
    ): OkHttpClient {
        return OkHttpClient.Builder()
            .addInterceptor { chain ->
                val request = chain.request()
                capturedHeader.set(request.header(ApiKeyInterceptor.API_KEY_HEADER))
                latch.countDown()
                Response.Builder()
                    .request(request)
                    .protocol(Protocol.HTTP_1_1)
                    .code(responseCode)
                    .message("Handshake failure: $responseCode")
                    .body("".toResponseBody(null))
                    .build()
            }
            .build()
    }

    @Test
    fun streamAttachesApiKeyHeaderWhenPresentInVault() {
        val capturedHeader = AtomicReference<String?>()
        val latch = CountDownLatch(1)
        val client = createInterceptingClient(capturedHeader, latch)
        val vault = MockVault(boundHubUrl = "ws://localhost:8000/", key = "secret-ws-token-123")
        val wsClient = HubWebSocketClient(client = client, vault = vault)

        val scope = CoroutineScope(Dispatchers.IO)
        val job = wsClient.stream("ws://localhost:8000/stream", "test query")
            .catch { }
            .launchIn(scope)

        try {
            assertTrue(latch.await(5, TimeUnit.SECONDS))
            assertEquals("secret-ws-token-123", capturedHeader.get())
        } finally {
            job.cancel()
            scope.cancel()
        }
    }

    @Test
    fun streamOmitsApiKeyHeaderWhenUrlDoesNotMatchBoundHub() {
        val capturedHeader = AtomicReference<String?>()
        val latch = CountDownLatch(1)
        val client = createInterceptingClient(capturedHeader, latch)
        val vault = MockVault(boundHubUrl = "ws://otherhost:8000/", key = "secret-ws-token-123")
        val wsClient = HubWebSocketClient(client = client, vault = vault)

        val scope = CoroutineScope(Dispatchers.IO)
        val job = wsClient.stream("ws://localhost:8000/stream", "test query")
            .catch { }
            .launchIn(scope)

        try {
            assertTrue(latch.await(5, TimeUnit.SECONDS))
            assertNull(capturedHeader.get())
        } finally {
            job.cancel()
            scope.cancel()
        }
    }

    @Test
    fun streamTurnAttachesApiKeyHeaderWhenPresentInVault() {
        val capturedHeader = AtomicReference<String?>()
        val latch = CountDownLatch(1)
        val client = createInterceptingClient(capturedHeader, latch)
        val vault = MockVault(boundHubUrl = "ws://localhost:8000/", key = "secret-turn-token-456")
        val wsClient = HubWebSocketClient(client = client, vault = vault)

        val scope = CoroutineScope(Dispatchers.IO)
        val job = wsClient.streamTurn(
            url = "ws://localhost:8000/ws/turn",
            campaignId = 1,
            action = "attack",
            actor = "player",
            seed = 42,
        )
            .catch { }
            .launchIn(scope)

        try {
            assertTrue(latch.await(5, TimeUnit.SECONDS))
            assertEquals("secret-turn-token-456", capturedHeader.get())
        } finally {
            job.cancel()
            scope.cancel()
        }
    }

    @Test
    fun handshake401YieldsHubAuthenticationException() {
        val capturedHeader = AtomicReference<String?>()
        val latch = CountDownLatch(1)
        val client = createInterceptingClient(capturedHeader, latch, responseCode = 401)
        val vault = MockVault(boundHubUrl = "ws://localhost:8000/", key = "bad-key")
        val wsClient = HubWebSocketClient(client = client, vault = vault)

        val caughtError = AtomicReference<Throwable?>()
        val errorLatch = CountDownLatch(1)
        val scope = CoroutineScope(Dispatchers.IO)
        val job = wsClient.stream("ws://localhost:8000/stream", "status")
            .catch { err ->
                caughtError.set(err)
                errorLatch.countDown()
            }
            .launchIn(scope)

        try {
            assertTrue(errorLatch.await(5, TimeUnit.SECONDS))
            val err = caughtError.get()
            assertTrue(err is HubAuthenticationException)
            assertEquals(401, (err as HubAuthenticationException).code)
        } finally {
            job.cancel()
            scope.cancel()
        }
    }

    @Test
    fun handshake403YieldsHubAuthenticationException() {
        val capturedHeader = AtomicReference<String?>()
        val latch = CountDownLatch(1)
        val client = createInterceptingClient(capturedHeader, latch, responseCode = 403)
        val vault = MockVault(boundHubUrl = "ws://localhost:8000/", key = "forbidden-key")
        val wsClient = HubWebSocketClient(client = client, vault = vault)

        val caughtError = AtomicReference<Throwable?>()
        val errorLatch = CountDownLatch(1)
        val scope = CoroutineScope(Dispatchers.IO)
        val job = wsClient.stream("ws://localhost:8000/stream", "status")
            .catch { err ->
                caughtError.set(err)
                errorLatch.countDown()
            }
            .launchIn(scope)

        try {
            assertTrue(errorLatch.await(5, TimeUnit.SECONDS))
            val err = caughtError.get()
            assertTrue(err is HubAuthenticationException)
            assertEquals(403, (err as HubAuthenticationException).code)
        } finally {
            job.cancel()
            scope.cancel()
        }
    }
}
