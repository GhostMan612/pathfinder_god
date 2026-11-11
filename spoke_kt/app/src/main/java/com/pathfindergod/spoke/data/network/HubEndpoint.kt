// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.network

import java.net.URI
import java.net.URISyntaxException

/** A single, explicit hub root for Retrofit, saved settings, and WebSocket. */
object HubEndpoint {
    const val DEFAULT_BASE_URL = "http://10.0.2.2:8000"

    fun normalize(raw: String): String {
        // Preserve trailing scheme slashes until URI validation: trimming
        // "http://" first turns it into "http:" and can disguise a bad URL
        // as the valid host "http".
        val input = raw.trim()
        if (input.isEmpty()) return "$DEFAULT_BASE_URL/"
        val candidate = if (input.contains("://")) input else "http://$input"
        val uri = try {
            URI(candidate)
        } catch (exc: URISyntaxException) {
            throw IllegalArgumentException("Invalid hub URL", exc)
        }
        val scheme = uri.scheme?.lowercase()
        require(scheme == "http" || scheme == "https") {
            "Hub URL must use http or https"
        }
        require(!uri.host.isNullOrBlank() && uri.rawUserInfo == null) {
            "Hub URL requires a host and cannot contain credentials"
        }
        require(uri.port in -1..65535 && uri.port != 0) {
            "Hub URL has an invalid port"
        }
        require(uri.rawPath.isNullOrEmpty() || uri.rawPath == "/") {
            "Hub URL must point to the server root, not a path"
        }
        require(uri.rawQuery == null && uri.rawFragment == null) {
            "Hub URL cannot contain query parameters or fragments"
        }
        return "$scheme://${uri.rawAuthority}/"
    }

    fun streamUrl(raw: String): String =
        normalize(raw).replaceFirst("http", "ws") + "stream"

    /** Release network config only allows emulator cleartext at 10.0.2.2. */
    fun requiresHttpsInRelease(raw: String): Boolean {
        val uri = URI(normalize(raw))
        return uri.scheme == "http" && uri.host != "10.0.2.2"
    }
}
