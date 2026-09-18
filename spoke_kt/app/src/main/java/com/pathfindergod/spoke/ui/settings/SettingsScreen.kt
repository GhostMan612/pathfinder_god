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
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Text
import androidx.compose.material3.TextField
import androidx.compose.material3.TextFieldDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.pathfindergod.spoke.data.local.NetworkPreferences
import com.pathfindergod.spoke.service.HubConnectionStatus
import com.pathfindergod.spoke.service.HubForegroundService
import com.pathfindergod.spoke.ui.theme.CritRed
import com.pathfindergod.spoke.ui.theme.GodTypography
import com.pathfindergod.spoke.ui.theme.GoldAccent
import com.pathfindergod.spoke.ui.theme.StatusGreen
import com.pathfindergod.spoke.ui.theme.TextPrimary
import com.pathfindergod.spoke.ui.theme.TextSecondary
import com.pathfindergod.spoke.ui.theme.rpgPanel

@Composable
fun SettingsScreen() {
    val context = LocalContext.current
    val prefs = remember { NetworkPreferences(context) }
    var url by rememberSaveable { mutableStateOf(prefs.baseUrl()) }
    val status by HubForegroundService.status.collectAsStateWithLifecycle()
    Column(
        modifier = Modifier.fillMaxSize().padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text(
            text = "Tether",
            style = GodTypography.titleLarge,
            fontWeight = FontWeight.Bold,
            color = GoldAccent,
        )
        Column(modifier = Modifier.rpgPanel().fillMaxWidth().padding(16.dp)) {
            Text(
                text = "Hub URL",
                style = GodTypography.titleMedium,
                color = GoldAccent,
            )
            TextField(
                value = url,
                onValueChange = { url = it },
                singleLine = true,
                placeholder = { Text(text = NetworkPreferences.DEFAULT_BASE_URL) },
                colors = TextFieldDefaults.colors(
                    focusedTextColor = TextPrimary,
                    unfocusedTextColor = TextPrimary,
                    focusedContainerColor = Color.Transparent,
                    unfocusedContainerColor = Color.Transparent,
                    cursorColor = GoldAccent,
                ),
                modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
            )
            Box(
                modifier = Modifier
                    .rpgPanel()
                    .clickable {
                        prefs.updateBaseUrl(url)
                        url = prefs.baseUrl()
                        restartLink(context, prefs.streamUrl())
                    }
                    .fillMaxWidth()
                    .padding(top = 12.dp),
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    text = "CONNECT",
                    style = GodTypography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    color = GoldAccent,
                    modifier = Modifier.padding(vertical = 12.dp),
                )
            }
        }
        Row(
            modifier = Modifier.rpgPanel().fillMaxWidth().padding(16.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Box(
                modifier = Modifier.size(14.dp).background(statusColor(status), CircleShape),
            )
            Column(modifier = Modifier.padding(start = 12.dp)) {
                Text(
                    text = status.name,
                    style = GodTypography.titleMedium,
                    color = TextPrimary,
                )
                Text(
                    text = prefs.baseUrl(),
                    style = GodTypography.bodyMedium,
                    color = TextSecondary,
                )
            }
        }
    }
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
