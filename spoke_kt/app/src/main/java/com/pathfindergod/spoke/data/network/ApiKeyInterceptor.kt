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
        val requestUrl = original.url.toString()
        val authorizedKey = HubTransportSecurity.getAuthorizedApiKey(requestUrl, vault)

        if (authorizedKey == null) {
            if (original.header(API_KEY_HEADER) != null) {
                val sanitized = original.newBuilder().removeHeader(API_KEY_HEADER).build()
                return chain.proceed(sanitized)
            }
            return chain.proceed(original)
        }

        if (original.header(API_KEY_HEADER) != null) {
            return chain.proceed(original)
        }

        val authenticated = original.newBuilder()
            .header(API_KEY_HEADER, authorizedKey)
            .build()
        return chain.proceed(authenticated)
    }

    companion object {
        const val API_KEY_HEADER = "X-API-Key"
    }
}
