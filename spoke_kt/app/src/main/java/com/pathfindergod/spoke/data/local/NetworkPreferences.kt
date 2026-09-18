// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.local

import android.content.Context

class NetworkPreferences(context: Context) {

    private val prefs = context.applicationContext.getSharedPreferences(
        FILE_NAME,
        Context.MODE_PRIVATE,
    )

    fun baseUrl(): String =
        prefs.getString(KEY_BASE_URL, DEFAULT_BASE_URL) ?: DEFAULT_BASE_URL

    fun updateBaseUrl(raw: String) {
        prefs.edit().putString(KEY_BASE_URL, normalize(raw)).apply()
    }

    fun restUrl(): String = baseUrl().trimEnd('/') + "/"

    fun streamUrl(): String =
        baseUrl().replaceFirst("http", "ws").trimEnd('/') + "/stream"

    private fun normalize(raw: String): String {
        var value = raw.trim().trimEnd('/')
        if (!value.startsWith("http://") && !value.startsWith("https://")) {
            value = "http://$value"
        }
        return value.ifEmpty { DEFAULT_BASE_URL }
    }

    companion object {
        const val DEFAULT_BASE_URL = "http://10.0.2.2:8000"

        private const val FILE_NAME = "pathfinder_network"
        private const val KEY_BASE_URL = "hub_base_url"
    }
}
