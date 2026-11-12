// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.network

import com.pathfindergod.spoke.data.security.CredentialVault
import com.pathfindergod.spoke.data.security.VaultState
import com.sun.net.httpserver.HttpServer
import java.net.InetSocketAddress
import java.util.concurrent.atomic.AtomicReference
import okhttp3.OkHttpClient
import okhttp3.Request
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class ApiKeyInterceptorTest {

    private var httpServer: HttpServer? = null
    private var serverPort: Int = 0
    private val capturedApiKey = AtomicReference<String?>()

    private class MockVault(
        private val boundHubUrl: String? = null,
        private var apiKey: String? = null,
    ) : CredentialVault {
        override fun getState(): VaultState = if (apiKey != null || boundHubUrl != null) VaultState.READY else VaultState.EMPTY
        override fun getHubUrl(): String? = boundHubUrl
        override fun getApiKey(endpoint: String?): String? {
            if (endpoint != null && boundHubUrl != null && !endpoint.startsWith(boundHubUrl.trimEnd('/'))) {
                return null
            }
            return apiKey
        }
        override fun setApiKey(key: String?) { apiKey = key }
        override fun getCertificatePin(endpoint: String?): String? = null
        override fun setCertificatePin(pin: String?) {}
        override fun setCredentials(hubUrl: String, apiKey: String?, pin: String?) {
            this.apiKey = apiKey
        }
        override fun clear() { apiKey = null }
    }

    @Before
    fun setUp() {
        capturedApiKey.set(null)
        httpServer = HttpServer.create(InetSocketAddress("localhost", 0), 0).apply {
            createContext("/test") { exchange ->
                capturedApiKey.set(exchange.requestHeaders.getFirst(ApiKeyInterceptor.API_KEY_HEADER))
                val body = """{"ok":true}""".toByteArray()
                exchange.responseHeaders.set("Content-Type", "application/json")
                exchange.sendResponseHeaders(200, body.size.toLong())
                exchange.responseBody.write(body)
                exchange.close()
            }
            start()
        }
        serverPort = httpServer!!.address.port
    }

    @After
    fun tearDown() {
        httpServer?.stop(0)
    }

    @Test
    fun injectsApiKeyHeaderWhenVaultMatchesRequestUrl() {
        val vault = MockVault(
            boundHubUrl = "http://localhost:$serverPort/",
            apiKey = "spoke-secret-key-42",
        )
        val client = OkHttpClient.Builder()
            .addInterceptor(ApiKeyInterceptor(vault))
            .build()

        val request = Request.Builder()
            .url("http://localhost:$serverPort/test")
            .build()

        client.newCall(request).execute().use { response ->
            assertTrue(response.isSuccessful)
        }

        assertEquals("spoke-secret-key-42", capturedApiKey.get())
    }

    @Test
    fun omitsHeaderWhenRequestUrlDoesNotMatchBoundHubUrl() {
        val vault = MockVault(
            boundHubUrl = "http://otherhost:8000/",
            apiKey = "spoke-secret-key-42",
        )
        val client = OkHttpClient.Builder()
            .addInterceptor(ApiKeyInterceptor(vault))
            .build()

        val request = Request.Builder()
            .url("http://localhost:$serverPort/test")
            .build()

        client.newCall(request).execute().use { response ->
            assertTrue(response.isSuccessful)
        }

        assertNull(capturedApiKey.get())
    }

    @Test
    fun doesNotInjectHeaderWhenVaultIsEmptyOrNull() {
        val vault = MockVault(apiKey = null)
        val client = OkHttpClient.Builder()
            .addInterceptor(ApiKeyInterceptor(vault))
            .build()

        val request = Request.Builder()
            .url("http://localhost:$serverPort/test")
            .build()

        client.newCall(request).execute().use { response ->
            assertTrue(response.isSuccessful)
        }

        assertNull(capturedApiKey.get())
    }

    @Test
    fun doesNotOverwriteExistingHeader() {
        val vault = MockVault(
            boundHubUrl = "http://localhost:$serverPort/",
            apiKey = "vault-key",
        )
        val client = OkHttpClient.Builder()
            .addInterceptor(ApiKeyInterceptor(vault))
            .build()

        val request = Request.Builder()
            .url("http://localhost:$serverPort/test")
            .header(ApiKeyInterceptor.API_KEY_HEADER, "explicit-preexisting-key")
            .build()

        client.newCall(request).execute().use { response ->
            assertTrue(response.isSuccessful)
        }

        assertEquals("explicit-preexisting-key", capturedApiKey.get())
    }
}
