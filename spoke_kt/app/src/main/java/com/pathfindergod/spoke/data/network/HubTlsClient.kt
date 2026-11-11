// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.network

import java.security.SecureRandom
import java.security.cert.CertificateException
import java.security.cert.X509Certificate
import java.util.concurrent.TimeUnit
import javax.net.ssl.SSLContext
import javax.net.ssl.SSLSocketFactory
import javax.net.ssl.X509TrustManager
import okhttp3.CertificatePinner
import okhttp3.ConnectionPool
import okhttp3.OkHttpClient

/**
 * Shared pinned OkHttp client for Pathfinder God Hub communication.
 *
 * Enforces strict SHA-256 SPKI public key pinning for release HTTPS and WSS connections.
 * Hostname verification is relaxed only because the public key pin is strictly enforced
 * (see docs/HTTPS_RELEASE_BLUEPRINT.md §0). This client is hub-only.
 */
object HubTlsClient {
    // SHA-256 SubjectPublicKeyInfo pin printed by hub/scripts/make_hub_cert.py
    const val HUB_CERT_PIN = "sha256/TCE3TU8VNTncT1r68SgIrCJm9lQhZYzxvb49tbofuHc="

    private const val CONNECT_SECONDS = 10L
    private const val READ_SECONDS = 60L
    private const val WRITE_SECONDS = 30L
    private const val KEEP_ALIVE_MINUTES = 5L
    private const val MAX_IDLE_CONNECTIONS = 4
    private const val WS_PING_SECONDS = 15L

    class PinnedTrustManager(
        private val expectedPin: String,
    ) : X509TrustManager {
        override fun checkClientTrusted(chain: Array<out X509Certificate>?, authType: String?) {}

        override fun checkServerTrusted(chain: Array<out X509Certificate>?, authType: String?) {
            if (chain.isNullOrEmpty()) {
                throw CertificateException("Server certificate chain is empty")
            }
            val serverCert = chain[0]
            val pin = CertificatePinner.pin(serverCert)
            if (pin != expectedPin) {
                throw CertificateException(
                    "Certificate pin mismatch: presented cert SPKI pin $pin does not match expected $expectedPin",
                )
            }
        }

        override fun getAcceptedIssuers(): Array<X509Certificate> = emptyArray()
    }

    fun createTrustManager(pin: String = HUB_CERT_PIN): X509TrustManager =
        PinnedTrustManager(pin)

    fun createSslSocketFactory(trustManager: X509TrustManager): SSLSocketFactory {
        val sslContext = SSLContext.getInstance("TLS")
        sslContext.init(null, arrayOf(trustManager), SecureRandom())
        return sslContext.socketFactory
    }

    fun createCertificatePinner(
        pin: String = HUB_CERT_PIN,
        vararg hosts: String,
    ): CertificatePinner {
        val builder = CertificatePinner.Builder()
            .add("localhost", pin)
            .add("127.0.0.1", pin)
            .add("10.0.2.2", pin)
            .add("*.local", pin)
            .add("**.local", pin)
        for (host in hosts) {
            if (host.isNotBlank() && !host.contains("*")) {
                builder.add(host, pin)
            }
        }
        return builder.build()
    }

    fun createOkHttpClient(
        pin: String = HUB_CERT_PIN,
        pingIntervalSeconds: Long = WS_PING_SECONDS,
        retryOnConnectionFailure: Boolean = true,
        vararg hosts: String,
    ): OkHttpClient {
        val trustManager = createTrustManager(pin)
        val sslSocketFactory = createSslSocketFactory(trustManager)
        val certificatePinner = createCertificatePinner(pin, *hosts)

        val builder = OkHttpClient.Builder()
            .connectTimeout(CONNECT_SECONDS, TimeUnit.SECONDS)
            .readTimeout(READ_SECONDS, TimeUnit.SECONDS)
            .writeTimeout(WRITE_SECONDS, TimeUnit.SECONDS)
            .pingInterval(pingIntervalSeconds, TimeUnit.SECONDS)
            .retryOnConnectionFailure(retryOnConnectionFailure)
            // An HTTPS Hub must not silently downgrade to HTTP via redirect.
            .followSslRedirects(false)
            .connectionPool(
                ConnectionPool(MAX_IDLE_CONNECTIONS, KEEP_ALIVE_MINUTES, TimeUnit.MINUTES),
            )
            .sslSocketFactory(sslSocketFactory, trustManager)
            // Hostname verification is relaxed strictly on this hub-only client because LAN IPs change
            // via DHCP while CertificatePinner & PinnedTrustManager enforce exact public key identity.
            .hostnameVerifier { _, _ -> true }
            .certificatePinner(certificatePinner)

        // Install pass-through cleaner so self-signed certs pass to CertificatePinner without
        // being rejected by the platform root cleaner.
        OkHttpTlsCompat.setPassThroughCertificateChainCleaner(builder)

        return builder.build()
    }

    val sharedClient: OkHttpClient by lazy {
        createOkHttpClient()
    }
}
