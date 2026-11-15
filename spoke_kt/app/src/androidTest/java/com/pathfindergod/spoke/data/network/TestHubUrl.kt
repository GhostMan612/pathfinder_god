// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.network

import android.content.Context
import android.os.Build
import androidx.test.platform.app.InstrumentationRegistry
import com.pathfindergod.spoke.data.local.AppPreferences
import java.net.URI
import java.net.URISyntaxException

/** Resolve a Hub endpoint for real-device tests without hardcoded laptop IPs. */
object TestHubUrl {
    /**
     * Addresses that only ever reach the machine running them. On a physical handset
     * every one of these is the phone, so a saved "127.0.0.1" silently produced
     * `ConnectException: Failed to connect to /127.0.0.1:8000` instead of the
     * actionable misconfiguration message. `10.0.2.2` is the emulator's host alias
     * and is handled separately.
     */
    private val LOOPBACK_HOSTS = setOf("127.0.0.1", "localhost", "::1", "[::1]")

    fun resolve(context: Context? = null): String {
        val ctx = context ?: InstrumentationRegistry.getInstrumentation().targetContext
        return choose(
            InstrumentationRegistry.getArguments().getString("hubBaseUrl"),
            AppPreferences(ctx).baseUrl(),
            isEmulator(),
        )
    }

    internal fun choose(argument: String?, saved: String, isEmulator: Boolean): String {
        val explicit = argument?.trim().orEmpty()
        val candidate = explicit.ifBlank { saved.trim() }
            .ifBlank { AppPreferences.DEFAULT_BASE_URL }.trimEnd('/')
        val value = if (candidate.contains("://")) candidate else "http://$candidate"
        val uri = try {
            URI(value)
        } catch (exc: URISyntaxException) {
            throw IllegalArgumentException("Malformed test Hub URL", exc)
        }
        require(
            (uri.scheme == "http" || uri.scheme == "https") &&
                !uri.host.isNullOrBlank() && uri.rawUserInfo == null &&
                uri.rawQuery == null && uri.rawFragment == null &&
                (uri.rawPath.isNullOrEmpty() || uri.rawPath == "/")
        ) { "Test Hub URL must be an http(s) server root without credentials" }

        if (!isEmulator) {
            val host = uri.host?.lowercase().orEmpty()
            if (host == "10.0.2.2") {
                error(
                    "Physical-device smoke tests require hubBaseUrl=<laptop LAN URL> " +
                        "as instrumentation argument or a custom Hub URL in Settings; " +
                        "10.0.2.2 is emulator-only."
                )
            }
            if (host in LOOPBACK_HOSTS) {
                error(
                    "Physical-device smoke tests cannot target $host: on a handset that " +
                        "address is the phone itself, never the laptop. Pass " +
                        "hubBaseUrl=http://<laptop-LAN-IP>:8000 as an instrumentation " +
                        "argument, or set a custom Hub URL in Settings."
                )
            }
        }
        return value.trimEnd('/')
    }

    private fun isEmulator(): Boolean {
        val hardware = Build.HARDWARE.lowercase()
        val model = Build.MODEL.lowercase()
        // Requiring a recognized emulator hardware or model avoids treating
        // an unusual/unknown vendor fingerprint as proof of an emulator.
        return hardware.contains("ranchu") ||
            hardware.contains("goldfish") ||
            model.contains("emulator")
    }
}
