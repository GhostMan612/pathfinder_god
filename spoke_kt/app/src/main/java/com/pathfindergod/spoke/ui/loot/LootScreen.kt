// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.loot

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardOptions
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
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.pathfindergod.spoke.data.local.NetworkPreferences
import com.pathfindergod.spoke.data.network.HubApiFactory
import com.pathfindergod.spoke.ui.theme.CritRed
import com.pathfindergod.spoke.ui.theme.GodTypography
import com.pathfindergod.spoke.ui.theme.GoldAccent
import com.pathfindergod.spoke.ui.theme.TextPrimary
import com.pathfindergod.spoke.ui.theme.TextSecondary
import com.pathfindergod.spoke.ui.theme.rpgPanel
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
            HubApiFactory.create(NetworkPreferences(context).restUrl()),
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
    Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {
        Column(modifier = Modifier.rpgPanel().fillMaxWidth().padding(16.dp)) {
            Text(
                text = "Commission",
                style = GodTypography.titleMedium,
                color = GoldAccent,
            )
            Row(
                modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                LootField(
                    value = level,
                    onChange = { level = it },
                    label = "Party Level",
                    modifier = Modifier.weight(1f),
                )
                LootField(
                    value = budget,
                    onChange = { budget = it },
                    label = "Budget (gp)",
                    modifier = Modifier.weight(1f),
                )
            }
            LootField(
                value = theme,
                onChange = { theme = it },
                label = "Theme (e.g. Undead hunting gear)",
                numeric = false,
                modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
            )
            Box(
                modifier = Modifier
                    .rpgPanel()
                    .clickable(enabled = !loading) {
                        viewModel.generateLoot(
                            level.toIntOrNull()?.coerceIn(1, 20) ?: 1,
                            budget.toIntOrNull()?.coerceAtLeast(0) ?: 0,
                            theme.trim(),
                        )
                    }
                    .fillMaxWidth()
                    .padding(top = 12.dp),
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    text = if (loading) "CONSULTING THE FORGE…" else "GENERATE LOOT",
                    style = GodTypography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    color = if (loading) TextSecondary else GoldAccent,
                    modifier = Modifier.padding(vertical = 12.dp),
                )
            }
        }
        when (val current = state) {
            is LootState.Error -> {
                Text(
                    text = current.message,
                    style = GodTypography.bodyMedium,
                    color = CritRed,
                    modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
                )
                HoardList(
                    items = current.items,
                    craftDc = null,
                    modifier = Modifier.weight(1f),
                )
            }
            is LootState.Success -> HoardList(
                items = current.items,
                craftDc = current.craftDc,
                modifier = Modifier.weight(1f),
            )
            is LootState.Loading -> {
                Box(
                    modifier = Modifier.fillMaxWidth().weight(1f),
                    contentAlignment = Alignment.Center,
                ) {
                    Text(
                        text = "The forge fires…",
                        style = GodTypography.titleMedium,
                        color = TextSecondary,
                    )
                }
            }
            is LootState.Idle -> {
                Box(
                    modifier = Modifier.fillMaxWidth().weight(1f),
                    contentAlignment = Alignment.Center,
                ) {
                    Text(
                        text = "Name a price and a prey.",
                        style = GodTypography.titleMedium,
                        color = TextSecondary,
                        textAlign = TextAlign.Center,
                        modifier = Modifier.padding(horizontal = 32.dp),
                    )
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
        modifier = modifier.fillMaxWidth().padding(top = 12.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        items(items, key = { it.name + it.level }) { item ->
            LootCard(
                item = item,
                craftDc = craftDc,
                modifier = Modifier.animateItem(),
            )
        }
    }
}

@Composable
private fun LootField(
    value: String,
    onChange: (String) -> Unit,
    label: String,
    modifier: Modifier = Modifier,
    numeric: Boolean = true,
) {
    TextField(
        value = value,
        onValueChange = onChange,
        label = { Text(text = label) },
        singleLine = true,
        keyboardOptions = if (numeric) {
            KeyboardOptions(keyboardType = KeyboardType.Number)
        } else {
            KeyboardOptions.Default
        },
        colors = TextFieldDefaults.colors(
            focusedTextColor = TextPrimary,
            unfocusedTextColor = TextPrimary,
            focusedContainerColor = Color.Transparent,
            unfocusedContainerColor = Color.Transparent,
            cursorColor = GoldAccent,
            focusedLabelColor = TextSecondary,
            unfocusedLabelColor = TextSecondary,
        ),
        modifier = modifier,
    )
}
