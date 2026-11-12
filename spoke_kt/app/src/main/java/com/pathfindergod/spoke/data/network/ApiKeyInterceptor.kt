// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.network

import com.pathfindergod.spoke.data.security.CredentialVault
import okhttp3.Interceptor
import okhttp3.Response

class ApiKeyInterceptor(
    private val vault: CredentialVault,
) : Interceptor {

    override fun intercept(chain: Interceptor.Chain): Response {
        val original = chain.request()
        if (original.header(API_KEY_HEADER) != null) {
            return chain.proceed(original)
        }

        val requestUrl = original.url.toString()
        val apiKey = vault.getApiKey(requestUrl)
        if (apiKey.isNullOrEmpty()) {
            return chain.proceed(original)
        }

        if (!original.isHttps) {
            val host = original.url.host
            val isLocal = host == "localhost" || host == "127.0.0.1" || host == "10.0.2.2"
            if (!isLocal) {
                return chain.proceed(original)
            }
        }

        val authenticated = original.newBuilder()
            .header(API_KEY_HEADER, apiKey)
            .build()
        return chain.proceed(authenticated)
    }

    companion object {
        const val API_KEY_HEADER = "X-API-Key"
    }
}
