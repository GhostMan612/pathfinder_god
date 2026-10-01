// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.settings

import android.content.Context
import android.content.Intent
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.pathfindergod.spoke.R
import com.pathfindergod.spoke.data.local.AppPreferences
import com.pathfindergod.spoke.service.AudioService
import com.pathfindergod.spoke.service.HubConnectionStatus
import com.pathfindergod.spoke.service.HubForegroundService
import com.pathfindergod.spoke.ui.designsystem.Dimens
import com.pathfindergod.spoke.ui.designsystem.GodCard
import com.pathfindergod.spoke.ui.designsystem.GodChip
import com.pathfindergod.spoke.ui.designsystem.GodLiveRegion
import com.pathfindergod.spoke.ui.designsystem.GodPrimaryButton
import com.pathfindergod.spoke.ui.designsystem.GodSectionHeader
import com.pathfindergod.spoke.ui.designsystem.GodTags
import com.pathfindergod.spoke.ui.designsystem.GodTextField
import com.pathfindergod.spoke.ui.designsystem.GodTone
import com.pathfindergod.spoke.ui.designsystem.Spacing
import com.pathfindergod.spoke.ui.theme.CritRed
import com.pathfindergod.spoke.ui.theme.GoldAccent
import com.pathfindergod.spoke.ui.theme.StatusGreen
import com.pathfindergod.spoke.ui.theme.TextPrimary
import com.pathfindergod.spoke.ui.theme.TextSecondary

@Composable
fun SettingsScreen(onOpenCredits: () -> Unit) {
    val context = LocalContext.current
    val prefs = remember { AppPreferences(context) }
    val audio = remember { AudioService.get(context) }
    var url by rememberSaveable { mutableStateOf(prefs.baseUrl()) }
    var music by rememberSaveable { mutableStateOf(prefs.musicEnabled()) }
    var sfx by rememberSaveable { mutableStateOf(prefs.sfxEnabled()) }
    var haptics by rememberSaveable { mutableStateOf(prefs.hapticsEnabled()) }
    var track by rememberSaveable { mutableStateOf(prefs.bgmTrack()) }
    var pit by rememberSaveable { mutableStateOf(prefs.pitEnabled()) }
    val status by HubForegroundService.status.collectAsStateWithLifecycle()

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(Dimens.cardPadding)
            .verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.spacedBy(Dimens.cardPaddingTight),
    ) {
        GodSectionHeader(
            text = stringResource(R.string.settings_title),
            prominent = true,
        )
        GodSectionHeader(text = stringResource(R.string.settings_section_tether))
        GodCard(
            title = {
                Text(
                    text = stringResource(R.string.settings_hub_url),
                    style = MaterialTheme.typography.titleMedium,
                    color = GoldAccent,
                )
            },
        ) {
            GodTextField(
                value = url,
                onValueChange = { url = it },
                placeholder = AppPreferences.DEFAULT_BASE_URL,
                modifier = Modifier.fillMaxWidth().padding(top = Spacing.sm),
            )
            GodPrimaryButton(
                text = stringResource(R.string.settings_connect),
                onClickLabel = stringResource(R.string.a11y_settings_connect),
                onClick = {
                    audio.buttonPress()
                    prefs.updateBaseUrl(url)
                    url = prefs.baseUrl()
                    restartLink(context, prefs.streamUrl())
                },
                testTag = GodTags.SETTINGS_CONNECT,
                modifier = Modifier.padding(top = Spacing.md),
            )
        }
        GodCard(
            testTag = GodTags.SETTINGS_HUB_STATUS,
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(
                    modifier = Modifier
                        .size(Dimens.statusDot)
                        .background(statusColor(status), CircleShape),
                )
                Column(modifier = Modifier.padding(start = Spacing.md)) {
                    Text(
                        text = status.name,
                        style = MaterialTheme.typography.titleMedium,
                        color = TextPrimary,
                    )
                    Text(
                        text = prefs.baseUrl(),
                        style = MaterialTheme.typography.bodyMedium,
                        color = TextSecondary,
                    )
                }
            }
        }
        GodLiveRegion(
            text = stringResource(R.string.a11y_hub_status, status.name),
            tag = GodTags.SETTINGS_HUB_STATUS + ":announce",
            modifier = Modifier.fillMaxWidth(),
        )

        GodSectionHeader(text = stringResource(R.string.settings_section_feedback))
        ToggleRow(
            key = "music",
            label = stringResource(R.string.settings_music),
            value = music,
        ) {
            music = it
            prefs.setMusicEnabled(it)
            audio.syncMusic()
            if (it) audio.buttonPress() else audio.playTap()
        }
        ToggleRow(
            key = "sfx",
            label = stringResource(R.string.settings_sound_effects),
            value = sfx,
        ) {
            sfx = it
            prefs.setSfxEnabled(it)
            if (it) audio.playTap()
        }
        ToggleRow(
            key = "haptics",
            label = stringResource(R.string.settings_haptics),
            value = haptics,
        ) {
            haptics = it
            prefs.setHapticsEnabled(it)
            if (it) audio.buttonPress()
        }
        GodCard(
            title = {
                Text(
                    text = stringResource(R.string.settings_music_track),
                    style = MaterialTheme.typography.titleMedium,
                    color = GoldAccent,
                )
            },
        ) {
            AudioService.BGM_TRACKS.forEach { option ->
                GodChip(
                    label = trackLabel(option),
                    selected = option == track,
                    onClick = {
                        track = option
                        prefs.setBgmTrack(option)
                        audio.playBgm(option)
                    },
                    onClickLabel = stringResource(R.string.a11y_settings_track, trackLabel(option)),
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(top = Spacing.md),
                    testTag = GodTags.settingsTrack(option),
                )
            }
        }

        GodSectionHeader(text = stringResource(R.string.settings_section_dice))
        ToggleRow(
            key = "pit",
            label = stringResource(R.string.settings_pit),
            value = pit,
        ) {
            pit = it
            prefs.setPitEnabled(it)
            if (it) audio.buttonPress() else audio.playTap()
        }

        GodSectionHeader(text = stringResource(R.string.settings_section_credits))
        GodPrimaryButton(
            text = stringResource(R.string.settings_audio_credits),
            onClickLabel = stringResource(R.string.a11y_settings_credits),
            onClick = {
                audio.buttonPress()
                onOpenCredits()
            },
            testTag = GodTags.SETTINGS_CREDITS,
        )
    }
}

@Composable
private fun ToggleRow(
    key: String,
    label: String,
    value: Boolean,
    onChange: (Boolean) -> Unit,
) {
    GodCard(
        contentPadding = PaddingValues(horizontal = Spacing.lg, vertical = Spacing.md),
        onToggle = onChange,
        toggleValue = value,
        testTag = GodTags.settingsToggle(key),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                text = label,
                style = MaterialTheme.typography.titleMedium,
                color = TextPrimary,
            )
            Text(
                text = stringResource(
                    if (value) R.string.settings_on else R.string.settings_off,
                ),
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
                color = if (value) StatusGreen else TextSecondary,
            )
        }
    }
}

@Composable
private fun trackLabel(track: String): String = when (track) {
    AudioService.BGM_INN -> stringResource(R.string.settings_track_inn)
    else -> stringResource(R.string.settings_track_tavern)
}

private fun statusColor(status: HubConnectionStatus) = when (status) {
    HubConnectionStatus.CONNECTED -> StatusGreen
    HubConnectionStatus.CONNECTING,
    HubConnectionStatus.RETRYING,
    -> GoldAccent
    HubConnectionStatus.DISCONNECTED -> CritRed
}

private fun restartLink(context: Context, streamUrl: String) {
    val packageName = HubForegroundService::class.java
    ContextCompat.startForegroundService(
        context,
        Intent(context, packageName).setAction(HubForegroundService.ACTION_DISCONNECT),
    )
    ContextCompat.startForegroundService(
        context,
        Intent(context, packageName)
            .setAction(HubForegroundService.ACTION_CONNECT)
            .putExtra(HubForegroundService.EXTRA_URL, streamUrl),
    )
}
