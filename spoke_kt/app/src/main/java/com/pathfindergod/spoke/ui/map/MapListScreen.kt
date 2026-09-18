// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.map

import android.graphics.BitmapFactory
import android.util.Base64
import androidx.compose.foundation.Image
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.pathfindergod.spoke.data.local.AppDatabase
import com.pathfindergod.spoke.data.local.MapEntity
import com.pathfindergod.spoke.data.local.NetworkPreferences
import com.pathfindergod.spoke.data.network.HubApi
import com.pathfindergod.spoke.data.network.HubApiFactory
import com.pathfindergod.spoke.data.repository.MapRepository
import com.pathfindergod.spoke.ui.theme.CritRed
import com.pathfindergod.spoke.ui.theme.CrimsonPrimary
import com.pathfindergod.spoke.ui.theme.GodTypography
import com.pathfindergod.spoke.ui.theme.GoldAccent
import com.pathfindergod.spoke.ui.theme.TextPrimary
import com.pathfindergod.spoke.ui.theme.TextSecondary
import com.pathfindergod.spoke.ui.theme.rpgPanel
import com.pathfindergod.spoke.ui.viewmodel.MapViewModel

internal fun decodeMapPng(raw: String): ImageBitmap? = try {
    val bytes = Base64.decode(raw, Base64.DEFAULT)
    BitmapFactory.decodeByteArray(bytes, 0, bytes.size)?.asImageBitmap()
} catch (_: Exception) {
    null
}

private class MapVmFactory(
    private val repository: MapRepository,
    private val api: HubApi,
) : ViewModelProvider.Factory {
    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>): T =
        MapViewModel(repository, api) as T
}

@Composable
internal fun rememberMapViewModel(): MapViewModel {
    val context = LocalContext.current
    val prefs = remember { NetworkPreferences(context) }
    val api = remember { HubApiFactory.create(prefs.restUrl()) }
    val repository = remember {
        MapRepository(AppDatabase.create(context.applicationContext), api)
    }
    return viewModel(factory = remember { MapVmFactory(repository, api) })
}

@Composable
fun MapListScreen(
    viewModel: MapViewModel,
    onSelect: (String) -> Unit,
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    Box(modifier = Modifier.fillMaxSize()) {
        Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {
            Text(
                text = "Vault",
                style = GodTypography.titleLarge,
                fontWeight = FontWeight.Bold,
                color = GoldAccent,
            )
            if (state.isGenerating) {
                Text(
                    text = "Conjuring…",
                    style = GodTypography.bodyMedium,
                    color = TextSecondary,
                    modifier = Modifier.padding(top = 4.dp),
                )
            }
            state.error?.let { error ->
                Text(
                    text = error,
                    style = GodTypography.bodyMedium,
                    color = CritRed,
                    modifier = Modifier.padding(top = 4.dp),
                )
            }
            if (state.maps.isEmpty() && !state.isGenerating) {
                Box(
                    modifier = Modifier.fillMaxWidth().weight(1f),
                    contentAlignment = Alignment.Center,
                ) {
                    Text(
                        text = "No maps yet — conjure a ruined crypt.",
                        style = GodTypography.titleMedium,
                        color = TextSecondary,
                        textAlign = TextAlign.Center,
                        modifier = Modifier.padding(horizontal = 32.dp),
                    )
                }
            } else {
                LazyVerticalGrid(
                    columns = GridCells.Fixed(2),
                    modifier = Modifier.fillMaxWidth().weight(1f).padding(top = 12.dp),
                    horizontalArrangement = Arrangement.spacedBy(10.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    items(state.maps, key = { it.id }) { map ->
                        MapCard(
                            map = map,
                            modifier = Modifier.animateItem(),
                            onSelect = { onSelect(map.id) },
                            onDelete = { viewModel.delete(map.id) },
                        )
                    }
                }
            }
        }
        FloatingActionButton(
            onClick = { viewModel.generate("A ruined crypt") },
            containerColor = CrimsonPrimary,
            modifier = Modifier.align(Alignment.BottomEnd).padding(20.dp),
        ) {
            Icon(
                imageVector = Icons.Filled.Add,
                contentDescription = "Conjure map",
                tint = GoldAccent,
            )
        }
    }
}

@Composable
private fun MapCard(
    map: MapEntity,
    modifier: Modifier = Modifier,
    onSelect: () -> Unit,
    onDelete: () -> Unit,
) {
    val thumbnail = remember(map.id) {
        decodeMapPng(map.playerBase64Png.ifBlank { map.gmBase64Png })
    }
    Column(
        modifier = modifier.rpgPanel().clickable { onSelect() }.padding(8.dp),
    ) {
        if (thumbnail != null) {
            Image(
                bitmap = thumbnail,
                contentDescription = map.prompt,
                contentScale = ContentScale.Crop,
                modifier = Modifier.fillMaxWidth().aspectRatio(1f),
            )
        } else {
            Box(
                modifier = Modifier.fillMaxWidth().aspectRatio(1f),
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    text = "?",
                    style = GodTypography.displayLarge,
                    color = TextSecondary,
                )
            }
        }
        Text(
            text = map.prompt,
            style = GodTypography.bodyMedium,
            color = TextPrimary,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
            modifier = Modifier.padding(top = 6.dp),
        )
        Text(
            text = "Banish",
            style = GodTypography.labelLarge,
            color = CritRed,
            modifier = Modifier.clickable { onDelete() }.padding(top = 2.dp),
        )
    }
}
