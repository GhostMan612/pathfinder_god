// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.network

import com.pathfindergod.spoke.data.security.CredentialVault
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

    private class MockVault(private var apiKey: String? = null) : CredentialVault {
        override fun getApiKey(): String? = apiKey
        override fun setApiKey(key: String?) { apiKey = key }
        override fun getCertificatePin(): String? = null
        override fun setCertificatePin(pin: String?) {}
        override fun getHubUrl(): String? = null
        override fun setHubUrl(url: String?) {}
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
    fun injectsApiKeyHeaderWhenVaultHasKey() {
        val vault = MockVault(apiKey = "spoke-secret-key-42")
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
        val vault = MockVault(apiKey = "vault-key")
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
