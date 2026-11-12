// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.network

import com.pathfindergod.spoke.data.security.CredentialVault
import com.pathfindergod.spoke.data.security.VaultState
import com.sun.net.httpserver.HttpsConfigurator
import com.sun.net.httpserver.HttpsServer
import java.io.File
import java.io.FileInputStream
import java.net.InetSocketAddress
import java.security.KeyStore
import java.security.SecureRandom
import java.security.cert.X509Certificate
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference
import javax.net.ssl.KeyManagerFactory
import javax.net.ssl.SSLContext
import javax.net.ssl.SSLException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.flow.launchIn
import okhttp3.CertificatePinner
import okhttp3.Request
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class HubUnifiedTlsTest {

    private var httpsServer: HttpsServer? = null
    private var httpsPort: Int = 0
    private var serverPin: String = ""

    private class MockVault(
        private var boundHubUrl: String,
        private var pin: String?,
    ) : CredentialVault {
        private var listener: (() -> Unit)? = null
        override fun getState(): VaultState = VaultState.READY
        override fun getHubUrl(): String = boundHubUrl
        override fun getApiKey(endpoint: String?): String? = null
        override fun setApiKey(key: String?) {}
        override fun getCertificatePin(endpoint: String?): String? = pin
        override fun setCertificatePin(pin: String?) {
            this.pin = pin
            listener?.invoke()
        }
        override fun setCredentials(hubUrl: String, apiKey: String?, pin: String?) {
            this.boundHubUrl = hubUrl
            this.pin = pin
            listener?.invoke()
        }
        override fun setChangeListener(listener: (() -> Unit)?) {
            this.listener = listener
        }
        override fun clear() {
            this.pin = null
            listener?.invoke()
        }
    }

    @Before
    fun setUp() {
        val tmpKeystore = File.createTempFile("unified_tls_keystore", ".p12")
        tmpKeystore.delete()
        tmpKeystore.deleteOnExit()
        val password = "changeit"
        val alias = "unifiedtls"

        val javaHome = System.getProperty("java.home") ?: ""
        val isWindows = System.getProperty("os.name")?.lowercase()?.contains("win") == true
        val keytoolBin = if (isWindows) File(javaHome, "bin/keytool.exe") else File(javaHome, "bin/keytool")
        val keytoolPath = if (keytoolBin.exists()) keytoolBin.absolutePath else "keytool"

        val pb = ProcessBuilder(
            keytoolPath,
            "-genkeypair",
            "-alias", alias,
            "-keyalg", "RSA",
            "-keysize", "2048",
            "-validity", "1",
            "-keystore", tmpKeystore.absolutePath,
            "-storetype", "PKCS12",
            "-storepass", password,
            "-dname", "CN=localhost",
        )
        val proc = pb.start()
        val errorText = proc.errorStream.bufferedReader().readText()
        val exitCode = proc.waitFor()
        assertEquals("keytool error: $errorText", 0, exitCode)

        val ks = KeyStore.getInstance("PKCS12")
        FileInputStream(tmpKeystore).use { fis ->
            ks.load(fis, password.toCharArray())
        }
        val cert = ks.getCertificate(alias) as X509Certificate
        serverPin = CertificatePinner.pin(cert)
        assertTrue(serverPin.startsWith("sha256/"))

        val kmf = KeyManagerFactory.getInstance(KeyManagerFactory.getDefaultAlgorithm())
        kmf.init(ks, password.toCharArray())
        val sslContext = SSLContext.getInstance("TLS")
        sslContext.init(kmf.keyManagers, null, SecureRandom())

        httpsServer = HttpsServer.create(InetSocketAddress("localhost", 0), 0).apply {
            httpsConfigurator = HttpsConfigurator(sslContext)
            createContext("/health") { exchange ->
                val body = """{"status":"ok"}""".toByteArray()
                exchange.responseHeaders.set("Content-Type", "application/json")
                exchange.sendResponseHeaders(200, body.size.toLong())
                exchange.responseBody.write(body)
                exchange.close()
            }
            start()
        }
        httpsPort = httpsServer!!.address.port
    }

    @After
    fun tearDown() {
        HubApiFactory.shutdown()
        httpsServer?.stop(0)
    }

    @Test
    fun customPinAppliesToBothHttpAndWebSocketTransports() {
        val vault = MockVault("https://localhost:$httpsPort", serverPin)
        HubApiFactory.init(vault)

        val httpRequest = Request.Builder()
            .url("https://localhost:$httpsPort/health")
            .build()

        HubApiFactory.okHttpClient.newCall(httpRequest).execute().use { response ->
            assertTrue(response.isSuccessful)
            assertEquals("""{"status":"ok"}""", response.body?.string())
        }

        val wsClient = HubWebSocketClient()
        val connectedOrRefusedByHttpHandler = CountDownLatch(1)
        val caughtError = AtomicReference<Throwable?>()
        val scope = CoroutineScope(Dispatchers.IO)
        val job = wsClient.stream("wss://localhost:$httpsPort/health", "query")
            .catch { err ->
                caughtError.set(err)
                connectedOrRefusedByHttpHandler.countDown()
            }
            .launchIn(scope)

        assertTrue(connectedOrRefusedByHttpHandler.await(5, TimeUnit.SECONDS))
        val err = caughtError.get()
        assertNotNull(err)
        assertTrue(err !is SSLException)
        job.cancel()
        scope.cancel()
    }

    @Test
    fun mismatchedPinFailsBothHttpAndWebSocketTransports() {
        val wrongPin = "sha256/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
        val vault = MockVault("https://localhost:$httpsPort", wrongPin)
        HubApiFactory.init(vault)

        val httpRequest = Request.Builder()
            .url("https://localhost:$httpsPort/health")
            .build()

        assertThrows(SSLException::class.java) {
            HubApiFactory.okHttpClient.newCall(httpRequest).execute().use { }
        }

        val wsClient = HubWebSocketClient()
        val failedLatch = CountDownLatch(1)
        val caughtError = AtomicReference<Throwable?>()
        val scope = CoroutineScope(Dispatchers.IO)
        val job = wsClient.stream("wss://localhost:$httpsPort/health", "query")
            .catch { err ->
                caughtError.set(err)
                failedLatch.countDown()
            }
            .launchIn(scope)

        assertTrue(failedLatch.await(5, TimeUnit.SECONDS))
        val err = caughtError.get()
        assertNotNull(err)
        assertTrue(err is SSLException || err?.cause is SSLException)
        job.cancel()
        scope.cancel()
    }

    @Test
    fun clientRefreshRotatesPinAndRebuildsTlsConfiguration() {
        val vault = MockVault("https://localhost:$httpsPort", serverPin)
        HubApiFactory.init(vault)
        vault.setChangeListener { HubApiFactory.refreshClient() }

        val request = Request.Builder().url("https://localhost:$httpsPort/health").build()
        HubApiFactory.okHttpClient.newCall(request).execute().use { response ->
            assertTrue(response.isSuccessful)
        }

        vault.setCertificatePin("sha256/ZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ=")

        assertThrows(SSLException::class.java) {
            HubApiFactory.okHttpClient.newCall(request).execute().use { }
        }

        vault.setCertificatePin(serverPin)
        HubApiFactory.okHttpClient.newCall(request).execute().use { response ->
            assertTrue(response.isSuccessful)
        }
    }
}
