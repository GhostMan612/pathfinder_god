// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.local

import android.content.Context

class AppPreferences(context: Context) {

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

    fun musicEnabled(): Boolean = prefs.getBoolean(KEY_MUSIC, true)

    fun setMusicEnabled(value: Boolean) {
        prefs.edit().putBoolean(KEY_MUSIC, value).apply()
    }

    fun sfxEnabled(): Boolean = prefs.getBoolean(KEY_SFX, true)

    fun setSfxEnabled(value: Boolean) {
        prefs.edit().putBoolean(KEY_SFX, value).apply()
    }

    fun hapticsEnabled(): Boolean = prefs.getBoolean(KEY_HAPTICS, true)

    fun setHapticsEnabled(value: Boolean) {
        prefs.edit().putBoolean(KEY_HAPTICS, value).apply()
    }

    fun bgmTrack(): String = prefs.getString(KEY_BGM_TRACK, DEFAULT_BGM_TRACK)
        ?: DEFAULT_BGM_TRACK

    fun setBgmTrack(track: String) {
        prefs.edit().putString(KEY_BGM_TRACK, track).apply()
    }

    fun pitEnabled(): Boolean = prefs.getBoolean(KEY_PIT, true)

    fun setPitEnabled(value: Boolean) {
        prefs.edit().putBoolean(KEY_PIT, value).apply()
    }

    private fun normalize(raw: String): String {
        var value = raw.trim().trimEnd('/')
        if (!value.startsWith("http://") && !value.startsWith("https://")) {
            value = "http://$value"
        }
        return value.ifEmpty { DEFAULT_BASE_URL }
    }

    companion object {
        const val DEFAULT_BASE_URL = "http://10.0.2.2:8000"

        private const val DEFAULT_BGM_TRACK = "audio/bgm_tavern.mp3"
        private const val FILE_NAME = "pathfinder_network"
        private const val KEY_BASE_URL = "hub_base_url"
        private const val KEY_MUSIC = "music_enabled"
        private const val KEY_SFX = "sfx_enabled"
        private const val KEY_HAPTICS = "haptics_enabled"
        private const val KEY_BGM_TRACK = "bgm_track"
        private const val KEY_PIT = "pit_enabled"
    }
}
