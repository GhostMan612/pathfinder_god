// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.encounter

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
import com.pathfindergod.spoke.data.local.AppDatabase
import com.pathfindergod.spoke.data.local.EncounterEntity
import com.pathfindergod.spoke.data.local.NetworkPreferences
import com.pathfindergod.spoke.data.network.HubApi
import com.pathfindergod.spoke.data.network.HubApiFactory
import com.pathfindergod.spoke.data.repository.EncounterRepository
import com.pathfindergod.spoke.ui.theme.CritRed
import com.pathfindergod.spoke.ui.theme.GodTypography
import com.pathfindergod.spoke.ui.theme.GoldAccent
import com.pathfindergod.spoke.ui.theme.TextPrimary
import com.pathfindergod.spoke.ui.theme.TextSecondary
import com.pathfindergod.spoke.ui.theme.rpgPanel
import com.pathfindergod.spoke.ui.viewmodel.EncounterPhase
import com.pathfindergod.spoke.ui.viewmodel.EncounterViewModel

private val difficulties = listOf("trivial", "low", "moderate", "severe", "extreme")

private class EncounterVmFactory(
    private val repository: EncounterRepository,
    private val api: HubApi,
) : ViewModelProvider.Factory {
    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>): T =
        EncounterViewModel(repository, api) as T
}

@Composable
internal fun rememberEncounterViewModel(): EncounterViewModel {
    val context = LocalContext.current
    val prefs = remember { NetworkPreferences(context) }
    val api = remember { HubApiFactory.create(prefs.restUrl()) }
    val repository = remember {
        EncounterRepository(AppDatabase.create(context.applicationContext), api)
    }
    return viewModel(factory = remember { EncounterVmFactory(repository, api) })
}

@Composable
fun EncounterScreen(
    viewModel: EncounterViewModel,
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    var level by rememberSaveable { mutableStateOf("3") }
    var theme by rememberSaveable { mutableStateOf("") }
    var difficulty by rememberSaveable { mutableStateOf("moderate") }
    val loading = state.phase == EncounterPhase.Loading
    Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {
        Column(modifier = Modifier.rpgPanel().fillMaxWidth().padding(16.dp)) {
            Text(
                text = "Forge",
                style = GodTypography.titleMedium,
                color = GoldAccent,
            )
            Row(
                modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                TextField(
                    value = level,
                    onValueChange = { level = it },
                    label = { Text(text = "Party Level") },
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                    colors = forgeFieldColors(),
                    modifier = Modifier.weight(1f),
                )
                TextField(
                    value = theme,
                    onValueChange = { theme = it },
                    label = { Text(text = "Theme") },
                    singleLine = true,
                    colors = forgeFieldColors(),
                    modifier = Modifier.weight(2f),
                )
            }
            Row(
                horizontalArrangement = Arrangement.spacedBy(6.dp),
                modifier = Modifier.fillMaxWidth().padding(top = 10.dp),
            ) {
                difficulties.forEach { option ->
                    val selected = difficulty == option
                    Text(
                        text = option.replaceFirstChar { it.uppercase() },
                        style = GodTypography.labelLarge,
                        fontWeight = if (selected) FontWeight.Bold else FontWeight.Normal,
                        color = if (selected) GoldAccent else TextSecondary,
                        modifier = Modifier
                            .rpgPanel()
                            .clickable { difficulty = option }
                            .padding(horizontal = 10.dp, vertical = 6.dp),
                    )
                }
            }
            Box(
                modifier = Modifier
                    .rpgPanel()
                    .clickable(enabled = !loading) {
                        if (theme.isBlank()) return@clickable
                        viewModel.generateEncounter(
                            level.toIntOrNull()?.coerceIn(1, 20) ?: 1,
                            difficulty,
                            theme.trim(),
                        )
                    }
                    .fillMaxWidth()
                    .padding(top = 12.dp),
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    text = if (loading) "MUSTERING…" else "CONJURE ENCOUNTER",
                    style = GodTypography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    color = if (loading) TextSecondary else GoldAccent,
                    modifier = Modifier.padding(vertical = 12.dp),
                )
            }
        }
        (state.phase as? EncounterPhase.Error)?.let { error ->
            Text(
                text = error.message,
                style = GodTypography.bodyMedium,
                color = CritRed,
                modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
            )
        }
        if (state.activeMonsters.isEmpty() && !loading) {
            Box(
                modifier = Modifier.fillMaxWidth().weight(1f),
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    text = "Name a hunting ground.",
                    style = GodTypography.titleMedium,
                    color = TextSecondary,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.padding(horizontal = 32.dp),
                )
            }
        } else {
            LazyColumn(
                modifier = Modifier.fillMaxWidth().weight(1f).padding(top = 12.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                if (state.activeLabel.isNotBlank()) {
                    item(key = "label") {
                        Text(
                            text = "${state.activeLabel} · Target ${state.activeTargetXp} XP",
                            style = GodTypography.titleMedium,
                            color = GoldAccent,
                        )
                    }
                }
                items(state.activeMonsters, key = { it.name + it.level }) { monster ->
                    MonsterCard(monster = monster, modifier = Modifier.animateItem())
                }
                if (state.encounters.isNotEmpty()) {
                    item(key = "vault") {
                        Text(
                            text = "Vault",
                            style = GodTypography.titleMedium,
                            color = GoldAccent,
                            modifier = Modifier.padding(top = 8.dp),
                        )
                    }
                    state.encounters.forEach { saved ->
                        item(key = "vault-${saved.id}") {
                            VaultRow(
                                encounter = saved,
                                modifier = Modifier.animateItem(),
                                onSelect = { viewModel.inspect(saved) },
                                onDelete = { viewModel.delete(saved.id) },
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun VaultRow(
    encounter: EncounterEntity,
    modifier: Modifier = Modifier,
    onSelect: () -> Unit,
    onDelete: () -> Unit,
) {
    Row(
        modifier = modifier.rpgPanel().clickable { onSelect() }.fillMaxWidth().padding(12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = encounter.theme,
                style = GodTypography.bodyMedium,
                color = TextPrimary,
            )
            Text(
                text = "${encounter.threat} · Target ${encounter.targetXp} XP",
                style = GodTypography.labelLarge,
                color = TextSecondary,
            )
        }
        Text(
            text = "✕",
            style = GodTypography.titleLarge,
            fontWeight = FontWeight.Bold,
            color = CritRed,
            modifier = Modifier.clickable { onDelete() }.padding(8.dp),
        )
    }
}

@Composable
private fun forgeFieldColors() = TextFieldDefaults.colors(
    focusedTextColor = TextPrimary,
    unfocusedTextColor = TextPrimary,
    focusedContainerColor = Color.Transparent,
    unfocusedContainerColor = Color.Transparent,
    cursorColor = GoldAccent,
    focusedLabelColor = TextSecondary,
    unfocusedLabelColor = TextSecondary,
)
