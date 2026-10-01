// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.network

import java.util.concurrent.TimeUnit
import kotlinx.serialization.json.Json
import okhttp3.ConnectionPool
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory

object HubApiFactory {
    private const val CONNECT_SECONDS = 10L
    private const val READ_SECONDS = 60L
    private const val WRITE_SECONDS = 30L
    private const val KEEP_ALIVE_MINUTES = 5L
    private const val MAX_IDLE_CONNECTIONS = 4

    private val json = Json { ignoreUnknownKeys = true }

    @Volatile
    private var client: OkHttpClient? = null

    @Volatile
    private var cached: Pair<String, HubApi>? = null

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
            .client(client())
            .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
            .build()
            .create(HubApi::class.java)

    private fun client(): OkHttpClient = client ?: OkHttpClient.Builder()
        .connectTimeout(CONNECT_SECONDS, TimeUnit.SECONDS)
        .readTimeout(READ_SECONDS, TimeUnit.SECONDS)
        .writeTimeout(WRITE_SECONDS, TimeUnit.SECONDS)
        .connectionPool(
            ConnectionPool(MAX_IDLE_CONNECTIONS, KEEP_ALIVE_MINUTES, TimeUnit.MINUTES),
        )
        .build()
        .also { client = it }

    private fun normalize(baseUrl: String): String {
        val trimmed = baseUrl.trim().trimEnd('/')
        val rooted = if (trimmed.isEmpty()) "http://10.0.2.2:8000" else trimmed
        return "$rooted/"
    }
}
