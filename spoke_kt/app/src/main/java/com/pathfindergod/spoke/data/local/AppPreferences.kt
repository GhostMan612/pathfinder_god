// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.local

import android.content.Context
import android.content.SharedPreferences
import com.pathfindergod.spoke.data.network.HubEndpoint

class AppPreferences(context: Context) {

    private val prefs = context.applicationContext.getSharedPreferences(
        FILE_NAME,
        Context.MODE_PRIVATE,
    )

    fun baseUrl(): String {
        val saved = prefs.getString(KEY_BASE_URL, DEFAULT_BASE_URL) ?: DEFAULT_BASE_URL
        // Old versions could save "http://" when Connect was tapped on an
        // empty field. Recover instead of crashing every Hub client on launch.
        return try {
            HubEndpoint.normalize(saved).trimEnd('/')
        } catch (_: IllegalArgumentException) {
            DEFAULT_BASE_URL
        }
    }

    fun currentHubIdentity(): String =
        HubEndpoint.canonicalOrigin(baseUrl())

    fun updateBaseUrl(raw: String) {
        // Validate before writing. A malformed URL must not poison Settings.
        val previousOrigin = try {
            HubEndpoint.canonicalOrigin(baseUrl())
        } catch (_: IllegalArgumentException) {
            null
        }
        val normalized = HubEndpoint.normalize(raw).trimEnd('/')
        val nextOrigin = HubEndpoint.canonicalOrigin(normalized)
        prefs.edit().apply {
            putString(KEY_BASE_URL, normalized)
            if (previousOrigin != nextOrigin) {
                remove(KEY_SELECTED_CAMPAIGN_ID)
                remove(KEY_SELECTED_CAMPAIGN_HUB)
            }
            apply()
        }
    }

    fun observeChanges(listener: () -> Unit): () -> Unit {
        val prefListener = SharedPreferences.OnSharedPreferenceChangeListener { _, key ->
            if (key == KEY_BASE_URL || key == KEY_SELECTED_CAMPAIGN_ID || key == KEY_SELECTED_CAMPAIGN_HUB) {
                listener()
            }
        }
        prefs.registerOnSharedPreferenceChangeListener(prefListener)
        return {
            prefs.unregisterOnSharedPreferenceChangeListener(prefListener)
        }
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

    fun selectedCampaignId(): Int? {
        val id = prefs.getInt(KEY_SELECTED_CAMPAIGN_ID, -1)
        if (id < 1) return null
        val boundHub = prefs.getString(KEY_SELECTED_CAMPAIGN_HUB, null) ?: return null
        return if (boundHub == currentHubIdentity()) id else null
    }

    fun setSelectedCampaignId(campaignId: Int) {
        require(campaignId >= 1) { "campaignId must be positive" }
        prefs.edit()
            .putInt(KEY_SELECTED_CAMPAIGN_ID, campaignId)
            .putString(KEY_SELECTED_CAMPAIGN_HUB, currentHubIdentity())
            .apply()
    }

    fun clearSelectedCampaignId() {
        prefs.edit()
            .remove(KEY_SELECTED_CAMPAIGN_ID)
            .remove(KEY_SELECTED_CAMPAIGN_HUB)
            .apply()
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
        private const val KEY_SELECTED_CAMPAIGN_ID = "selected_campaign_id"
        private const val KEY_SELECTED_CAMPAIGN_HUB = "selected_campaign_hub"
    }
}
