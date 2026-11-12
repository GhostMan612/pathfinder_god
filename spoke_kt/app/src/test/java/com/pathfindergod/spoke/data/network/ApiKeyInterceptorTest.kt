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
        override fun setChangeListener(listener: (() -> Unit)?) {}
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
    fun stripsPreexistingApiKeyWhenTargetOriginIsNotAuthorized() {
        val vault = MockVault(
            boundHubUrl = "http://localhost:$serverPort/",
            apiKey = "spoke-secret-key-42",
        )
        val capturedHeaderOnOtherHost = AtomicReference<String?>()
        val client = OkHttpClient.Builder()
            .addInterceptor(ApiKeyInterceptor(vault))
            .addNetworkInterceptor { chain ->
                capturedHeaderOnOtherHost.set(chain.request().header(ApiKeyInterceptor.API_KEY_HEADER))
                chain.proceed(chain.request())
            }
            .build()

        val unauthorizedRequest = Request.Builder()
            .url("http://localhost:$serverPort/test")
            .header(ApiKeyInterceptor.API_KEY_HEADER, "leaked-secret")
            .build()

        val vaultWithoutMatch = MockVault(boundHubUrl = "http://authorized.hub:8000/", apiKey = "key")
        val sanitizingClient = OkHttpClient.Builder()
            .addInterceptor(ApiKeyInterceptor(vaultWithoutMatch))
            .build()

        sanitizingClient.newCall(unauthorizedRequest).execute().use { response ->
            assertTrue(response.isSuccessful)
        }

        assertNull(capturedApiKey.get())
    }

    @Test
    fun remoteCleartextUrlSuppressesApiKey() {
        val vault = MockVault(
            boundHubUrl = "http://192.168.1.50:8000/",
            apiKey = "remote-lan-key",
        )
        val interceptor = ApiKeyInterceptor(vault)
        val request = Request.Builder()
            .url("http://192.168.1.50:8000/api/characters")
            .build()

        var forwardedHeader: String? = "uninitialized"
        val chain = object : okhttp3.Interceptor.Chain {
            override fun request(): Request = request
            override fun proceed(req: Request): okhttp3.Response {
                forwardedHeader = req.header(ApiKeyInterceptor.API_KEY_HEADER)
                return okhttp3.Response.Builder()
                    .request(req)
                    .protocol(okhttp3.Protocol.HTTP_1_1)
                    .code(200)
                    .message("OK")
                    .body(okhttp3.ResponseBody.create(null, ""))
                    .build()
            }
            override fun connection(): okhttp3.Connection? = null
            override fun call(): okhttp3.Call = throw UnsupportedOperationException()
            override fun connectTimeoutMillis(): Int = 0
            override fun withConnectTimeout(timeout: Int, unit: java.util.concurrent.TimeUnit): okhttp3.Interceptor.Chain = this
            override fun readTimeoutMillis(): Int = 0
            override fun withReadTimeout(timeout: Int, unit: java.util.concurrent.TimeUnit): okhttp3.Interceptor.Chain = this
            override fun writeTimeoutMillis(): Int = 0
            override fun withWriteTimeout(timeout: Int, unit: java.util.concurrent.TimeUnit): okhttp3.Interceptor.Chain = this
        }

        interceptor.intercept(chain)
        assertNull(forwardedHeader)
    }
}
