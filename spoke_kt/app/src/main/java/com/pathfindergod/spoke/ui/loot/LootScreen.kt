// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.loot

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import com.pathfindergod.spoke.ui.motion.StaggerIn
import androidx.compose.foundation.lazy.items
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
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.pathfindergod.spoke.R
import com.pathfindergod.spoke.data.local.AppPreferences
import com.pathfindergod.spoke.data.network.HubApiFactory
import com.pathfindergod.spoke.ui.designsystem.Dimens
import com.pathfindergod.spoke.ui.designsystem.GodCard
import com.pathfindergod.spoke.ui.designsystem.GodEmptyState
import com.pathfindergod.spoke.ui.designsystem.GodLiveRegion
import com.pathfindergod.spoke.ui.designsystem.GodPrimaryButton
import com.pathfindergod.spoke.ui.designsystem.GodStatusText
import com.pathfindergod.spoke.ui.designsystem.GodTags
import com.pathfindergod.spoke.ui.designsystem.GodTextField
import com.pathfindergod.spoke.ui.designsystem.GodTone
import com.pathfindergod.spoke.ui.designsystem.GodTexture
import com.pathfindergod.spoke.ui.designsystem.Spacing
import com.pathfindergod.spoke.ui.strings.resolve
import com.pathfindergod.spoke.ui.theme.CritRed
import com.pathfindergod.spoke.ui.theme.GoldAccent
import com.pathfindergod.spoke.ui.viewmodel.LootItem
import com.pathfindergod.spoke.ui.viewmodel.LootState
import com.pathfindergod.spoke.ui.viewmodel.LootViewModel

private class LootVmFactory(
    private val viewModel: LootViewModel,
) : ViewModelProvider.Factory {
    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>): T =
        viewModel as T
}

@Composable
internal fun rememberLootViewModel(): LootViewModel {
    val context = LocalContext.current
    val delegate = remember {
        LootViewModel(
            HubApiFactory.get(AppPreferences(context).restUrl()),
        )
    }
    return viewModel(factory = remember { LootVmFactory(delegate) })
}

@Composable
fun LootScreen(
    viewModel: LootViewModel,
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    var level by rememberSaveable { mutableStateOf("3") }
    var budget by rememberSaveable { mutableStateOf("100") }
    var theme by rememberSaveable { mutableStateOf("") }
    val loading = state == LootState.Loading
    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(GodTexture.parchmentBrush())
            .padding(Spacing.lg),
    ) {
        GodCard(title = { Text(text = stringResource(R.string.loot_commission), style = MaterialTheme.typography.titleMedium, color = GoldAccent) }) {
            Row(
                modifier = Modifier.fillMaxWidth().padding(top = Spacing.sm),
                horizontalArrangement = Arrangement.spacedBy(Spacing.sm),
            ) {
                GodTextField(
                    value = level,
                    onValueChange = { level = it },
                    label = stringResource(R.string.loot_party_level),
                    numeric = true,
                    modifier = Modifier.weight(1f),
                )
                GodTextField(
                    value = budget,
                    onValueChange = { budget = it },
                    label = stringResource(R.string.loot_budget),
                    numeric = true,
                    modifier = Modifier.weight(1f),
                )
            }
            GodTextField(
                value = theme,
                onValueChange = { theme = it },
                label = stringResource(R.string.loot_theme),
                numeric = false,
                modifier = Modifier.fillMaxWidth().padding(top = Spacing.sm),
            )
            GodPrimaryButton(
                text = stringResource(
                    if (loading) R.string.loot_consulting else R.string.loot_generate,
                ),
                enabled = !loading,
                onClickLabel = stringResource(R.string.a11y_loot_conjure),
                onClick = {
                    viewModel.generateLoot(
                        level.toIntOrNull()?.coerceIn(1, 20) ?: 1,
                        budget.toIntOrNull()?.coerceAtLeast(0) ?: 0,
                        theme.trim(),
                    )
                },
                modifier = Modifier.padding(top = Spacing.md),
            )
        }
        when (val current = state) {
            is LootState.Error -> {
                GodStatusText(
                    text = current.message.resolve(),
                    tone = GodTone.Critical,
                    color = CritRed,
                    modifier = Modifier.fillMaxWidth().padding(top = Spacing.sm),
                )
                GodLiveRegion(
                    text = stringResource(R.string.a11y_loot_ready, current.items.size),
                    tag = GodTags.LOOT_STATUS,
                    assertive = true,
                    modifier = Modifier.fillMaxWidth().padding(top = Spacing.xs),
                )
                HoardList(
                    items = current.items,
                    craftDc = null,
                    modifier = Modifier.weight(1f),
                )
            }
            is LootState.Success -> {
                GodLiveRegion(
                    text = stringResource(R.string.a11y_loot_ready, current.items.size),
                    tag = GodTags.LOOT_STATUS,
                    assertive = true,
                    modifier = Modifier.fillMaxWidth().padding(top = Spacing.xs),
                )
                HoardList(
                    items = current.items,
                    craftDc = current.craftDc,
                    modifier = Modifier.weight(1f),
                )
            }
            is LootState.Loading -> {
                Box(
                    modifier = Modifier.fillMaxWidth().weight(1f),
                    contentAlignment = Alignment.Center,
                ) {
                    GodStatusText(text = stringResource(R.string.loot_forge_fires))
                }
            }
            is LootState.Idle -> {
                Box(
                    modifier = Modifier.fillMaxWidth().weight(1f),
                    contentAlignment = Alignment.Center,
                ) {
                    GodEmptyState(text = stringResource(R.string.loot_idle))
                }
            }
        }
    }
}

@Composable
private fun HoardList(
    items: List<LootItem>,
    craftDc: Int?,
    modifier: Modifier = Modifier,
) {
    LazyColumn(
        modifier = modifier.fillMaxWidth().padding(top = Spacing.md),
        verticalArrangement = Arrangement.spacedBy(Dimens.gridSpacing),
    ) {
        // Keyed on index, not name+level: the hub returns one LLM-authored item per
    // request with no uniqueness check, so two Generate taps routinely yield
    // identical names at identical levels. A duplicate key throws from the lazy
    // list's saveable-state registry and takes the process down.
    itemsIndexed(items, key = { index, _ -> "loot-$index" }) { index, item ->
            StaggerIn(index = index, modifier = Modifier.animateItem()) {
                LootCard(item = item, craftDc = craftDc)
            }
        }
    }
}
