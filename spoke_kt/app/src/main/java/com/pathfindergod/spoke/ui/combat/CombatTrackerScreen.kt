// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.combat

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import com.pathfindergod.spoke.ui.motion.StaggerIn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.AlertDialog
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
import com.pathfindergod.spoke.data.local.NetworkPreferences
import com.pathfindergod.spoke.data.network.HubApiFactory
import com.pathfindergod.spoke.data.repository.EncounterRepository
import com.pathfindergod.spoke.ui.theme.ParchmentSurface
import com.pathfindergod.spoke.ui.theme.GodTypography
import com.pathfindergod.spoke.ui.theme.GoldAccent
import com.pathfindergod.spoke.ui.theme.TextPrimary
import com.pathfindergod.spoke.ui.theme.TextSecondary
import com.pathfindergod.spoke.ui.theme.rpgPanel
import com.pathfindergod.spoke.ui.viewmodel.CombatViewModel
import com.pathfindergod.spoke.ui.viewmodel.Combatant
import java.util.UUID

private class CombatVmFactory(
    private val repository: EncounterRepository,
) : ViewModelProvider.Factory {
    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>): T =
        CombatViewModel(repository) as T
}

@Composable
internal fun rememberCombatViewModel(): CombatViewModel {
    val context = LocalContext.current
    val prefs = remember { NetworkPreferences(context) }
    val repository = remember {
        EncounterRepository(
            AppDatabase.create(context.applicationContext),
            HubApiFactory.create(prefs.restUrl()),
        )
    }
    return viewModel(factory = remember { CombatVmFactory(repository) })
}

@Composable
fun CombatTrackerScreen(
    viewModel: CombatViewModel,
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val vault by viewModel.vault.collectAsStateWithLifecycle()
    var summoning by rememberSaveable { mutableStateOf(false) }
    var name by rememberSaveable { mutableStateOf("") }
    var initiative by rememberSaveable { mutableStateOf("") }
    var hp by rememberSaveable { mutableStateOf("") }
    Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                text = "Round ${state.currentRound}",
                style = GodTypography.titleLarge,
                fontWeight = FontWeight.Bold,
                color = GoldAccent,
            )
            Text(
                text = "Summon",
                style = GodTypography.titleMedium,
                color = GoldAccent,
                modifier = Modifier.clickable { summoning = true }.padding(8.dp),
            )
            Text(
                text = state.combatants.getOrNull(state.activeIndex)?.name ?: "—",
                style = GodTypography.titleMedium,
                color = TextPrimary,
            )
        }
        Row(
            modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            TrackerField(
                value = name,
                onChange = { name = it },
                label = "Name",
                modifier = Modifier.weight(2f),
            )
            TrackerField(
                value = initiative,
                onChange = { initiative = it },
                label = "Init",
                numeric = true,
                modifier = Modifier.weight(1f),
            )
            TrackerField(
                value = hp,
                onChange = { hp = it },
                label = "HP",
                numeric = true,
                modifier = Modifier.weight(1f),
            )
            Text(
                text = "Add",
                style = GodTypography.titleMedium,
                fontWeight = FontWeight.Bold,
                color = GoldAccent,
                modifier = Modifier
                    .rpgPanel()
                    .clickable {
                        if (name.isBlank()) return@clickable
                        val maxHp = hp.toIntOrNull()?.coerceAtLeast(1) ?: 20
                        viewModel.addCombatant(
                            Combatant(
                                id = UUID.randomUUID().toString(),
                                name = name.trim(),
                                isPc = true,
                                initiative = initiative.toIntOrNull() ?: 10,
                                currentHp = maxHp,
                                maxHp = maxHp,
                            ),
                        )
                        name = ""
                        initiative = ""
                        hp = ""
                    }
                    .padding(horizontal = 14.dp, vertical = 10.dp),
            )
        }
        if (state.combatants.isEmpty()) {
            Box(
                modifier = Modifier.fillMaxWidth().weight(1f),
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    text = "No combatants — add the party and roll initiative.",
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
                itemsIndexed(state.combatants, key = { _, combatant -> combatant.id }) { index, combatant ->
                    StaggerIn(index = index, modifier = Modifier.animateItem()) {
                        CombatantCard(
                            combatant = combatant,
                            isActive = index == state.activeIndex,
                            onDamage = { viewModel.updateHp(combatant.id, -5) },
                            onHeal = { viewModel.updateHp(combatant.id, 5) },
                            onAddCondition = { viewModel.addCondition(combatant.id, it) },
                            onRemoveCondition = { viewModel.removeCondition(combatant.id, it) },
                        )
                    }
                }
            }
        }
        if (state.lastNotes.isNotBlank()) {
            Text(
                text = state.lastNotes,
                style = GodTypography.bodyMedium,
                color = TextSecondary,
                modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
            )
        }
        Box(
            modifier = Modifier
                .rpgPanel()
                .clickable { viewModel.nextTurn() }
                .fillMaxWidth()
                .padding(top = 0.dp),
            contentAlignment = Alignment.Center,
        ) {
            Text(
                text = "END TURN",
                style = GodTypography.titleLarge,
                fontWeight = FontWeight.Bold,
                color = GoldAccent,
                modifier = Modifier.padding(vertical = 14.dp),
            )
        }
        if (summoning) {
            AlertDialog(
                onDismissRequest = { summoning = false },
                title = {
                    Text(
                        text = "Vault",
                        style = GodTypography.titleMedium,
                        color = GoldAccent,
                    )
                },
                text = {
                    if (vault.isEmpty()) {
                        Text(
                            text = "Vault empty — conjure encounters first.",
                            style = GodTypography.bodyMedium,
                            color = TextSecondary,
                        )
                    } else {
                        LazyColumn(modifier = Modifier.heightIn(max = 320.dp)) {
                            itemsIndexed(vault, key = { _, saved -> saved.id }) { index, saved ->
                                StaggerIn(index = index) {
                                    Text(
                                        text = "${saved.threat} · ${saved.theme}",
                                        style = GodTypography.bodyMedium,
                                        color = TextPrimary,
                                        modifier = Modifier
                                            .clickable {
                                                viewModel.loadEncounter(saved.id)
                                                summoning = false
                                            }
                                            .fillMaxWidth()
                                            .padding(vertical = 8.dp),
                                    )
                                }
                            }
                        }
                    }
                },
                confirmButton = {
                    Text(
                        text = "Close",
                        style = GodTypography.titleMedium,
                        color = GoldAccent,
                        modifier = Modifier.clickable { summoning = false },
                    )
                },
                containerColor = ParchmentSurface,
            )
        }
    }
}

@Composable
private fun TrackerField(
    value: String,
    onChange: (String) -> Unit,
    label: String,
    modifier: Modifier = Modifier,
    numeric: Boolean = false,
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
