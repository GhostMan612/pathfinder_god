// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.local

import android.content.Context
import com.pathfindergod.spoke.data.network.HubEndpoint

class AppPreferences(context: Context) {

    private val prefs = context.applicationContext.getSharedPreferences(
        FILE_NAME,
        Context.MODE_PRIVATE,
    )

    fun baseUrl(): String =
        prefs.getString(KEY_BASE_URL, DEFAULT_BASE_URL) ?: DEFAULT_BASE_URL

    fun updateBaseUrl(raw: String) {
        // Validate before writing. A malformed URL must not poison Settings.
        val normalized = HubEndpoint.normalize(raw).trimEnd('/')
        prefs.edit().putString(KEY_BASE_URL, normalized).apply()
    }

    fun restUrl(): String = HubEndpoint.normalize(baseUrl())

    fun streamUrl(): String = HubEndpoint.streamUrl(baseUrl())

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

    companion object {
        const val DEFAULT_BASE_URL = HubEndpoint.DEFAULT_BASE_URL

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
