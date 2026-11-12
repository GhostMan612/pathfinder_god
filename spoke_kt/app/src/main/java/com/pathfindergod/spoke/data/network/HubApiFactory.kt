// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.network

import com.pathfindergod.spoke.data.security.CredentialVault
import com.pathfindergod.spoke.data.security.SpokeCredentialVault
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory

object HubApiFactory {
    private val json = Json { ignoreUnknownKeys = true }

    @Volatile
    private var client: OkHttpClient? = null

    @Volatile
    private var vault: CredentialVault? = null

    @Volatile
    private var cached: Pair<String, HubApi>? = null

    fun init(credentialVault: CredentialVault) {
        synchronized(this) {
            vault = credentialVault
            client?.let { http ->
                http.dispatcher.cancelAll()
                http.connectionPool.evictAll()
            }
            client = null
            cached = null
        }
    }

    fun refreshClient() {
        synchronized(this) {
            cached = null
            client?.let { http ->
                http.dispatcher.cancelAll()
                http.connectionPool.evictAll()
            }
            client = null
        }
    }

    fun get(baseUrl: String): HubApi {
        val url = normalize(baseUrl)
        cached?.let { (key, api) -> if (key == url) return api }
        return synchronized(this) {
            cached?.let { (key, api) -> if (key == url) return api }
            build(url).also { cached = url to it }
        }
    }

    fun shutdown() {
        synchronized(this) {
            cached = null
            client?.let { http ->
                http.dispatcher.cancelAll()
                http.connectionPool.evictAll()
                http.dispatcher.executorService.shutdown()
                http.cache?.close()
            }
            client = null
        }
    }

    private fun build(url: String): HubApi =
        Retrofit.Builder()
            .baseUrl(url)
            .client(client(url))
            .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
            .build()
            .create(HubApi::class.java)

    val okHttpClient: OkHttpClient
        get() = client()

    private fun client(targetUrl: String? = null): OkHttpClient = client ?: synchronized(this) {
        client ?: run {
            val activeVault = vault ?: SpokeCredentialVault.instanceOrNull()
            val interceptors = mutableListOf<okhttp3.Interceptor>()
            if (activeVault != null) {
                interceptors.add(ApiKeyInterceptor(activeVault))
            }
            val endpoint = targetUrl ?: activeVault?.getHubUrl()
            val pin = endpoint?.let { activeVault?.getCertificatePin(it) }?.trim()?.takeIf { it.isNotEmpty() }
                ?: HubTlsClient.HUB_CERT_PIN
            HubTlsClient.createOkHttpClient(
                pin = pin,
                interceptors = interceptors,
            ).also { client = it }
        }
    }

    private fun normalize(baseUrl: String): String = HubEndpoint.normalize(baseUrl)
}
