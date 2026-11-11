// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.network

import com.sun.net.httpserver.HttpServer
import com.sun.net.httpserver.HttpsConfigurator
import com.sun.net.httpserver.HttpsServer
import java.io.File
import java.io.FileInputStream
import java.net.InetSocketAddress
import java.security.KeyStore
import java.security.SecureRandom
import java.security.cert.X509Certificate
import javax.net.ssl.KeyManagerFactory
import javax.net.ssl.SSLContext
import javax.net.ssl.SSLException
import okhttp3.CertificatePinner
import okhttp3.Request
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class HubTlsClientTest {
    private var httpsServer: HttpsServer? = null
    private var httpServer: HttpServer? = null
    private var serverPin: String = ""
    private var httpsPort: Int = 0
    private var httpPort: Int = 0

    @Before
    fun setUp() {
        val tmpKeystore = File.createTempFile("test_keystore", ".p12")
        tmpKeystore.delete() // keytool expects file to not exist when creating a new keystore
        tmpKeystore.deleteOnExit()
        val password = "changeit"
        val alias = "testhub"

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
        assertTrue("Pin must start with sha256/", serverPin.startsWith("sha256/"))

        val kmf = KeyManagerFactory.getInstance(KeyManagerFactory.getDefaultAlgorithm())
        kmf.init(ks, password.toCharArray())
        val sslContext = SSLContext.getInstance("TLS")
        sslContext.init(kmf.keyManagers, null, SecureRandom())

        // Start HTTPS test server
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

        // Start HTTP test server
        httpServer = HttpServer.create(InetSocketAddress("localhost", 0), 0).apply {
            createContext("/health") { exchange ->
                val body = """{"status":"ok"}""".toByteArray()
                exchange.responseHeaders.set("Content-Type", "application/json")
                exchange.sendResponseHeaders(200, body.size.toLong())
                exchange.responseBody.write(body)
                exchange.close()
            }
            start()
        }
        httpPort = httpServer!!.address.port
    }

    @After
    fun tearDown() {
        httpsServer?.stop(0)
        httpServer?.stop(0)
    }

    @Test
    fun connectionSucceedsWhenServerPresentsPinnedCertificate() {
        val client = HubTlsClient.createOkHttpClient(pin = serverPin, hosts = arrayOf("localhost"))
        val request = Request.Builder()
            .url("https://localhost:$httpsPort/health")
            .build()

        client.newCall(request).execute().use { response ->
            assertTrue("Expected successful HTTPS response", response.isSuccessful)
            assertEquals(200, response.code)
            assertNotNull(response.body)
            assertEquals("""{"status":"ok"}""", response.body!!.string())
        }
    }

    @Test
    fun connectionFailsWhenServerPresentsDifferentCertificate() {
        val wrongPin = "sha256/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
        val client = HubTlsClient.createOkHttpClient(pin = wrongPin, hosts = arrayOf("localhost"))
        val request = Request.Builder()
            .url("https://localhost:$httpsPort/health")
            .build()

        assertThrows(SSLException::class.java) {
            client.newCall(request).execute().use { }
        }
    }

    @Test
    fun plainHttpUrlWorksThroughSameClientConfiguration() {
        val client = HubTlsClient.createOkHttpClient(pin = serverPin, hosts = arrayOf("localhost"))
        val request = Request.Builder()
            .url("http://localhost:$httpPort/health")
            .build()

        client.newCall(request).execute().use { response ->
            assertTrue("Expected successful HTTP response", response.isSuccessful)
            assertEquals(200, response.code)
            assertNotNull(response.body)
            assertEquals("""{"status":"ok"}""", response.body!!.string())
        }
    }

    @Test
    fun certificatePinnerHoldsHubCertPin() {
        val client = HubTlsClient.createOkHttpClient(pin = serverPin, hosts = arrayOf("localhost"))
        val pinner = client.certificatePinner
        assertTrue("Pinner must have registered pins", pinner.pins.isNotEmpty())
        assertTrue(
            "Pinner must hold the configured pin",
            pinner.pins.any { it.toString().contains(serverPin) },
        )
    }
}
