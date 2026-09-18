// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.map

import androidx.compose.foundation.Image
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectTransformGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Share
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
import com.pathfindergod.spoke.service.ExportService
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.pathfindergod.spoke.data.local.MapEntity
import com.pathfindergod.spoke.ui.theme.GodTypography
import com.pathfindergod.spoke.ui.theme.GoldAccent
import com.pathfindergod.spoke.ui.theme.TextPrimary
import com.pathfindergod.spoke.ui.theme.TextSecondary
import com.pathfindergod.spoke.ui.theme.rpgPanel
import com.pathfindergod.spoke.ui.viewmodel.MapViewModel

@Composable
fun MapViewerScreen(
    mapId: String,
    viewModel: MapViewModel,
    onBack: () -> Unit,
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val map = state.maps.firstOrNull { it.id == mapId }
    if (map == null) {
        Box(
            modifier = Modifier.fillMaxSize(),
            contentAlignment = Alignment.Center,
        ) {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text(
                    text = "Map lost to the void.",
                    style = GodTypography.titleMedium,
                    color = TextSecondary,
                    textAlign = TextAlign.Center,
                )
                Text(
                    text = "‹ Vault",
                    style = GodTypography.labelLarge,
                    color = GoldAccent,
                    modifier = Modifier.clickable { onBack() }.padding(top = 12.dp),
                )
            }
        }
    } else {
        MapCanvas(map = map, onBack = onBack)
    }
}

@Composable
private fun MapCanvas(
    map: MapEntity,
    onBack: () -> Unit,
) {
    val context = LocalContext.current
    var gmLayer by rememberSaveable { mutableStateOf(true) }
    var scale by remember { mutableFloatStateOf(1f) }
    var offset by remember { mutableStateOf(Offset.Zero) }
    val bitmap = remember(map.id, gmLayer) {
        decodeMapPng(if (gmLayer) map.gmBase64Png else map.playerBase64Png)
    }
    Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                text = "‹ Vault",
                style = GodTypography.labelLarge,
                color = GoldAccent,
                modifier = Modifier.clickable { onBack() }.padding(vertical = 4.dp),
            )
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                Text(
                    text = "GM",
                    style = GodTypography.titleMedium,
                    fontWeight = if (gmLayer) FontWeight.Bold else FontWeight.Normal,
                    color = if (gmLayer) GoldAccent else TextSecondary,
                    modifier = Modifier.clickable { gmLayer = true }.padding(4.dp),
                )
                Text(
                    text = "Player",
                    style = GodTypography.titleMedium,
                    fontWeight = if (!gmLayer) FontWeight.Bold else FontWeight.Normal,
                    color = if (!gmLayer) GoldAccent else TextSecondary,
                    modifier = Modifier.clickable { gmLayer = false }.padding(4.dp),
                )
            }
            Icon(
                imageVector = Icons.Filled.Share,
                contentDescription = "Share map",
                tint = GoldAccent,
                modifier = Modifier
                    .clickable {
                        ExportService.shareMapImage(
                            context,
                            if (gmLayer) map.gmBase64Png else map.playerBase64Png,
                            map.prompt,
                        )
                    }
                    .padding(4.dp),
            )
        }
        Text(
            text = map.prompt,
            style = GodTypography.titleMedium,
            color = TextPrimary,
            modifier = Modifier.padding(top = 4.dp),
        )
        Box(
            modifier = Modifier.rpgPanel().fillMaxWidth().weight(1f).padding(top = 12.dp),
            contentAlignment = Alignment.Center,
        ) {
            if (bitmap != null) {
                Image(
                    bitmap = bitmap,
                    contentDescription = map.prompt,
                    modifier = Modifier
                        .fillMaxSize()
                        .pointerInput(Unit) {
                            detectTransformGestures { _, pan, zoom, _ ->
                                scale = (scale * zoom).coerceIn(0.5f, 6f)
                                offset += pan
                            }
                        }
                        .graphicsLayer(
                            scaleX = scale,
                            scaleY = scale,
                            translationX = offset.x,
                            translationY = offset.y,
                        ),
                )
            } else {
                Text(
                    text = "Image would not resolve.",
                    style = GodTypography.bodyMedium,
                    color = TextSecondary,
                )
            }
        }
    }
}
