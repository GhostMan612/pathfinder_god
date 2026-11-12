// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.network

import com.pathfindergod.spoke.data.security.CredentialVault
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

    private class MockVault(private val key: String? = null) : CredentialVault {
        override fun getApiKey(): String? = key
        override fun setApiKey(key: String?) {}
        override fun getCertificatePin(): String? = null
        override fun setCertificatePin(pin: String?) {}
        override fun getHubUrl(): String? = null
        override fun setHubUrl(url: String?) {}
        override fun clear() {}
    }

    private fun createInterceptingClient(
        capturedHeader: AtomicReference<String?>,
        latch: CountDownLatch,
    ): OkHttpClient {
        return OkHttpClient.Builder()
            .addInterceptor { chain ->
                val request = chain.request()
                capturedHeader.set(request.header(ApiKeyInterceptor.API_KEY_HEADER))
                latch.countDown()
                Response.Builder()
                    .request(request)
                    .protocol(Protocol.HTTP_1_1)
                    .code(401)
                    .message("Unauthorized / Auth Captured")
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
        val vault = MockVault("secret-ws-token-123")
        val wsClient = HubWebSocketClient(client = client, vault = vault)

        val scope = CoroutineScope(Dispatchers.IO)
        val job = wsClient.stream("http://localhost:8000/stream", "test query")
            .catch { /* ignore connection failure from interceptor */ }
            .launchIn(scope)

        try {
            assertTrue("Expected interceptor to be reached", latch.await(5, TimeUnit.SECONDS))
            assertEquals("secret-ws-token-123", capturedHeader.get())
        } finally {
            job.cancel()
            scope.cancel()
        }
    }

    @Test
    fun streamOmitsApiKeyHeaderWhenVaultIsEmpty() {
        val capturedHeader = AtomicReference<String?>()
        val latch = CountDownLatch(1)
        val client = createInterceptingClient(capturedHeader, latch)
        val vault = MockVault(null)
        val wsClient = HubWebSocketClient(client = client, vault = vault)

        val scope = CoroutineScope(Dispatchers.IO)
        val job = wsClient.stream("http://localhost:8000/stream", "test query")
            .catch { /* ignore connection failure */ }
            .launchIn(scope)

        try {
            assertTrue("Expected interceptor to be reached", latch.await(5, TimeUnit.SECONDS))
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
        val vault = MockVault("secret-turn-token-456")
        val wsClient = HubWebSocketClient(client = client, vault = vault)

        val scope = CoroutineScope(Dispatchers.IO)
        val job = wsClient.streamTurn(
            url = "http://localhost:8000/ws/turn",
            campaignId = 1,
            action = "attack",
            actor = "player",
            seed = 42,
        )
            .catch { /* ignore connection failure */ }
            .launchIn(scope)

        try {
            assertTrue("Expected interceptor to be reached", latch.await(5, TimeUnit.SECONDS))
            assertEquals("secret-turn-token-456", capturedHeader.get())
        } finally {
            job.cancel()
            scope.cancel()
        }
    }
}
