// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.network

import com.pathfindergod.spoke.data.security.CredentialVault
import java.net.URI

object HubTransportSecurity {
    fun isCleartextPermitted(url: String): Boolean {
        val uri = try {
            URI(url)
        } catch (_: Exception) {
            return false
        }
        val scheme = uri.scheme?.lowercase() ?: return false
        if (scheme == "https" || scheme == "wss") {
            return true
        }
        if (scheme != "http" && scheme != "ws") {
            return false
        }
        val host = uri.host?.lowercase() ?: return false
        return host == "10.0.2.2" || host == "localhost" || host == "127.0.0.1"
    }

    fun getAuthorizedApiKey(url: String, vault: CredentialVault): String? {
        if (!isCleartextPermitted(url)) {
            return null
        }
        return vault.getApiKey(url)?.trim()?.ifEmpty { null }
    }
}
