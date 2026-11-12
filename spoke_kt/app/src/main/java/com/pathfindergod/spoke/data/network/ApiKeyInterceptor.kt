// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.network

import com.pathfindergod.spoke.data.security.CredentialVault
import okhttp3.Interceptor
import okhttp3.Response

/**
 * Injects the X-API-Key header into outgoing requests when an API key is configured
 * in the credential vault. Does not log or expose the key value.
 */
class ApiKeyInterceptor(
    private val vault: CredentialVault,
) : Interceptor {

    companion object {
        const val API_KEY_HEADER = "X-API-Key"
    }

    override fun intercept(chain: Interceptor.Chain): Response {
        val request = chain.request()
        val apiKey = vault.getApiKey()?.trim()

        val finalRequest = if (!apiKey.isNullOrEmpty() && request.header(API_KEY_HEADER) == null) {
            request.newBuilder()
                .header(API_KEY_HEADER, apiKey)
                .build()
        } else {
            request
        }

        return chain.proceed(finalRequest)
    }
}
