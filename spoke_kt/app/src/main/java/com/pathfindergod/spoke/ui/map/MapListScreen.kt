// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.map

import androidx.compose.foundation.Image
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.itemsIndexed
import com.pathfindergod.spoke.ui.motion.StaggerIn
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.pathfindergod.spoke.R
import com.pathfindergod.spoke.data.local.AppDatabase
import com.pathfindergod.spoke.data.local.AppPreferences
import com.pathfindergod.spoke.data.local.MapEntity
import com.pathfindergod.spoke.data.network.HubApi
import com.pathfindergod.spoke.data.network.HubApiFactory
import com.pathfindergod.spoke.data.repository.MapRepository
import com.pathfindergod.spoke.ui.designsystem.Dimens
import com.pathfindergod.spoke.ui.designsystem.GodCard
import com.pathfindergod.spoke.ui.designsystem.GodEmptyState
import com.pathfindergod.spoke.ui.designsystem.GodFab
import com.pathfindergod.spoke.ui.designsystem.GodLiveRegion
import com.pathfindergod.spoke.ui.designsystem.GodSectionHeader
import com.pathfindergod.spoke.ui.designsystem.GodStatusText
import com.pathfindergod.spoke.ui.designsystem.GodTags
import com.pathfindergod.spoke.ui.designsystem.GodTone
import com.pathfindergod.spoke.ui.designsystem.Spacing
import com.pathfindergod.spoke.ui.designsystem.godTouchHeight
import com.pathfindergod.spoke.ui.strings.resolve
import com.pathfindergod.spoke.ui.theme.CritRed
import com.pathfindergod.spoke.ui.theme.TextPrimary
import com.pathfindergod.spoke.ui.theme.TextSecondary
import com.pathfindergod.spoke.ui.viewmodel.MapViewModel

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
    val prefs = remember { AppPreferences(context) }
    val api = remember { HubApiFactory.get(prefs.restUrl()) }
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
        Column(modifier = Modifier.fillMaxSize().padding(Spacing.lg)) {
            GodSectionHeader(
                text = stringResource(R.string.map_vault),
                prominent = true,
            )
            if (state.isGenerating) {
                GodStatusText(
                    text = stringResource(R.string.map_conjuring),
                    modifier = Modifier.padding(top = Spacing.xs),
                )
            }
            state.error?.let { error ->
                GodStatusText(
                    text = error.resolve(),
                    tone = GodTone.Critical,
                    color = CritRed,
                    modifier = Modifier.padding(top = Spacing.xs),
                )
            }
            if (!state.isGenerating && state.maps.isNotEmpty()) {
                GodLiveRegion(
                    text = stringResource(R.string.a11y_map_count, state.maps.size),
                    tag = GodTags.MAP_FAB + ":count",
                    modifier = Modifier.padding(top = Spacing.xs),
                )
            }
            if (state.maps.isEmpty() && !state.isGenerating) {
                Box(
                    modifier = Modifier.fillMaxWidth().weight(1f),
                    contentAlignment = Alignment.Center,
                ) {
                    GodEmptyState(text = stringResource(R.string.map_empty))
                }
            } else {
                LazyVerticalGrid(
                    columns = GridCells.Fixed(2),
                    modifier = Modifier.fillMaxWidth().weight(1f).padding(top = Spacing.md),
                    horizontalArrangement = Arrangement.spacedBy(Dimens.gridSpacing),
                    verticalArrangement = Arrangement.spacedBy(Dimens.gridSpacing),
                ) {
                    itemsIndexed(
                        state.maps,
                        key = { _, map -> map.id },
                    ) { index, map ->
                        StaggerIn(index = index, modifier = Modifier.animateItem()) {
                            MapCard(
                                map = map,
                                onSelect = { onSelect(map.id) },
                                onDelete = { viewModel.delete(map.id) },
                            )
                        }
                    }
                }
            }
        }
        val defaultPrompt = stringResource(R.string.map_default_prompt)
        GodFab(
            icon = Icons.Filled.Add,
            contentDescription = stringResource(R.string.map_fab),
            onClick = { viewModel.generate(defaultPrompt) },
            testTag = GodTags.MAP_FAB,
            modifier = Modifier
                .align(Alignment.BottomEnd)
                .padding(Spacing.xl),
        )
    }
}

@Composable
private fun MapCard(
    map: MapEntity,
    modifier: Modifier = Modifier,
    onSelect: () -> Unit,
    onDelete: () -> Unit,
) {
    val decoded by produceState<ImageBitmap?>(initialValue = null, map.id) {
        value = MapImageDecoder.decode(
            map.playerBase64Png.ifBlank { map.gmBase64Png },
            THUMBNAIL_PX,
        )
    }
    val thumbnail = decoded
    GodCard(
        modifier = modifier.fillMaxWidth(),
        testTag = GodTags.map(map.id),
        contentPadding = PaddingValues(Spacing.sm),
        onClickLabel = stringResource(R.string.a11y_map_open, map.prompt),
        onClick = onSelect,
    ) {
        if (thumbnail != null) {
            Image(
                bitmap = thumbnail,
                contentDescription = null,
                contentScale = ContentScale.Crop,
                modifier = Modifier
                    .fillMaxWidth()
                    .aspectRatio(1f),
            )
        } else {
            Box(
                modifier = Modifier.fillMaxWidth().aspectRatio(1f),
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    text = stringResource(R.string.value_placeholder_image),
                    style = MaterialTheme.typography.displayLarge,
                    color = TextSecondary,
                )
            }
        }
        Text(
            text = map.prompt,
            style = MaterialTheme.typography.bodyMedium,
            color = TextPrimary,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
            modifier = Modifier.padding(top = Spacing.sm),
        )
        Text(
            text = stringResource(R.string.map_banish),
            style = MaterialTheme.typography.labelLarge,
            color = CritRed,
            modifier = Modifier
                .clickable(
                    onClickLabel = stringResource(R.string.a11y_map_banish, map.prompt),
                    role = Role.Button,
                ) { onDelete() }
                .godTouchHeight()
                .padding(top = Spacing.xxs)
                .testTag(GodTags.mapBanish(map.id)),
        )
    }
}
