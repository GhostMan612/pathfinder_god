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

        if (!isEmulator && uri.host == "10.0.2.2") {
            error(
                "Physical-device smoke tests require hubBaseUrl=<laptop LAN URL> " +
                    "as instrumentation argument or a custom Hub URL in Settings; " +
                    "10.0.2.2 is emulator-only."
            )
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
