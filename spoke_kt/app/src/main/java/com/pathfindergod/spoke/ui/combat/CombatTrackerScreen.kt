// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.combat

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import com.pathfindergod.spoke.ui.motion.StaggerIn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.AlertDialog
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
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.pathfindergod.spoke.R
import com.pathfindergod.spoke.data.local.AppDatabase
import com.pathfindergod.spoke.data.local.AppPreferences
import com.pathfindergod.spoke.service.AudioService
import com.pathfindergod.spoke.data.network.HubApiFactory
import com.pathfindergod.spoke.data.repository.EncounterRepository
import com.pathfindergod.spoke.ui.designsystem.Dimens
import com.pathfindergod.spoke.ui.designsystem.GodCard
import com.pathfindergod.spoke.ui.designsystem.GodChip
import com.pathfindergod.spoke.ui.designsystem.GodEmptyState
import com.pathfindergod.spoke.ui.designsystem.GodLiveRegion
import com.pathfindergod.spoke.ui.designsystem.GodPrimaryButton
import com.pathfindergod.spoke.ui.designsystem.GodStatusText
import com.pathfindergod.spoke.ui.designsystem.GodTags
import com.pathfindergod.spoke.ui.designsystem.GodTextField
import com.pathfindergod.spoke.ui.designsystem.GodTexture
import com.pathfindergod.spoke.ui.designsystem.GodTone
import com.pathfindergod.spoke.ui.designsystem.Spacing
import com.pathfindergod.spoke.ui.designsystem.godTouchHeight
import com.pathfindergod.spoke.ui.theme.GoldAccent
import com.pathfindergod.spoke.ui.theme.ParchmentSurface
import com.pathfindergod.spoke.ui.theme.StatusGreen
import com.pathfindergod.spoke.ui.theme.TextPrimary
import com.pathfindergod.spoke.ui.theme.TextSecondary
import com.pathfindergod.spoke.ui.theme.VoidBackground
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
    val prefs = remember { AppPreferences(context) }
    val repository = remember {
        EncounterRepository(
            AppDatabase.get(context.applicationContext),
            HubApiFactory.get(prefs.restUrl()),
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
    val context = LocalContext.current
    val audio = remember(context) { AudioService.get(context) }
    var summoning by rememberSaveable { mutableStateOf(false) }
    var name by rememberSaveable { mutableStateOf("") }
    var initiative by rememberSaveable { mutableStateOf("") }
    var hp by rememberSaveable { mutableStateOf("") }
    val activeName = state.combatants.getOrNull(state.activeIndex)?.name
    val turnAnnouncement = if (activeName == null) {
        stringResource(R.string.a11y_turn_idle)
    } else {
        stringResource(R.string.a11y_turn_change, state.currentRound, activeName)
    }
    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(GodTexture.feltBrush())
            .padding(Spacing.lg),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                text = stringResource(R.string.combat_round_pattern, state.currentRound),
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold,
                color = GoldAccent,
                modifier = Modifier.testTag(GodTags.COMBAT_ROUND),
            )
            Text(
                text = stringResource(R.string.combat_summon),
                style = MaterialTheme.typography.titleMedium,
                color = GoldAccent,
                modifier = Modifier
                    .semantics {
                        contentDescription = ""
                    }
                    .clickable(
                        onClickLabel = stringResource(R.string.a11y_combat_summon),
                        role = Role.Button,
                    ) { summoning = true }
                    .godTouchHeight()
                    .padding(Spacing.sm)
                    .testTag(GodTags.COMBAT_SUMMON),
            )
            Text(
                text = activeName ?: stringResource(R.string.value_unknown),
                style = MaterialTheme.typography.titleMedium,
                color = TextPrimary,
                modifier = Modifier.testTag(GodTags.COMBAT_ACTIVE),
            )
        }
        GodLiveRegion(
            text = turnAnnouncement,
            tag = GodTags.COMBAT_ACTIVE + ":announce",
            modifier = Modifier.padding(top = Spacing.xs),
        )
        Row(
            modifier = Modifier.fillMaxWidth().padding(top = Spacing.md),
            horizontalArrangement = Arrangement.spacedBy(Spacing.sm),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            GodTextField(
                value = name,
                onValueChange = { name = it },
                label = stringResource(R.string.combat_field_name),
                numeric = false,
                modifier = Modifier.weight(2f),
            )
            GodTextField(
                value = initiative,
                onValueChange = { initiative = it },
                label = stringResource(R.string.combat_init_label),
                numeric = true,
                modifier = Modifier.weight(1f),
            )
            GodTextField(
                value = hp,
                onValueChange = { hp = it },
                label = stringResource(R.string.combat_hp_label),
                numeric = true,
                modifier = Modifier.weight(1f),
            )
            GodChip(
                label = stringResource(R.string.combat_add),
                selected = true,
                style = MaterialTheme.typography.titleMedium,
                onClickLabel = stringResource(R.string.a11y_combat_add),
                contentDescription = stringResource(R.string.a11y_combat_add),
                testTag = GodTags.COMBAT_ADD,
                onClick = {
                    if (name.isBlank()) return@GodChip
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
                },
            )
        }
        if (state.combatants.isEmpty()) {
            Box(
                modifier = Modifier.fillMaxWidth().weight(1f),
                contentAlignment = Alignment.Center,
            ) {
                GodEmptyState(text = stringResource(R.string.combat_empty))
            }
        } else {
            LazyColumn(
                modifier = Modifier.fillMaxWidth().weight(1f).padding(top = Spacing.md),
                verticalArrangement = Arrangement.spacedBy(Dimens.gridSpacing),
            ) {
                itemsIndexed(state.combatants, key = { _, combatant -> combatant.id }) { index, combatant ->
                    StaggerIn(index = index, modifier = Modifier.animateItem()) {
                        CombatantCard(
                            combatant = combatant,
                            isActive = index == state.activeIndex,
                            onDamage = {
                                audio.damage()
                                viewModel.updateHp(combatant.id, -5)
                            },
                            onHeal = { viewModel.updateHp(combatant.id, 5) },
                            onAddCondition = { viewModel.addCondition(combatant.id, it) },
                            onRemoveCondition = { viewModel.removeCondition(combatant.id, it) },
                        )
                    }
                }
            }
        }
        if (state.lastNotes.isNotBlank()) {
            GodStatusText(
                text = state.lastNotes,
                modifier = Modifier.fillMaxWidth().padding(top = Spacing.sm),
            )
        }
        GodPrimaryButton(
            text = stringResource(R.string.combat_end_turn),
            onClickLabel = stringResource(R.string.a11y_combat_end_turn),
            onClick = { viewModel.nextTurn() },
            testTag = GodTags.COMBAT_END_TURN,
        )
        if (summoning) {
            AlertDialog(
                onDismissRequest = { summoning = false },
                title = {
                    Text(
                        text = stringResource(R.string.combat_vault),
                        style = MaterialTheme.typography.titleMedium,
                        color = GoldAccent,
                    )
                },
                text = {
                    if (vault.isEmpty()) {
                        GodStatusText(text = stringResource(R.string.combat_vault_empty))
                    } else {
                        LazyColumn(modifier = Modifier.heightIn(max = 320.dp)) {
                            itemsIndexed(vault, key = { _, saved -> saved.id }) { index, saved ->
                                StaggerIn(index = index) {
                                    Text(
                                        text = stringResource(
                                            R.string.combat_pattern_threat_theme,
                                            saved.threat,
                                            saved.theme,
                                        ),
                                        style = MaterialTheme.typography.bodyMedium,
                                        color = TextPrimary,
                                        modifier = Modifier
                                            .clickable(
                                                onClickLabel = stringResource(
                                                    R.string.a11y_vault_load,
                                                    saved.theme,
                                                ),
                                                role = Role.Button,
                                            ) {
                                                viewModel.loadEncounter(saved.id)
                                                summoning = false
                                            }
                                            .godTouchHeight()
                                            .fillMaxWidth()
                                            .padding(vertical = Spacing.sm),
                                    )
                                }
                            }
                        }
                    }
                },
                confirmButton = {
                    Text(
                        text = stringResource(R.string.combat_close),
                        style = MaterialTheme.typography.titleMedium,
                        color = GoldAccent,
                        modifier = Modifier
                            .clickable(
                                onClickLabel = stringResource(R.string.a11y_dialog_close),
                                role = Role.Button,
                            ) { summoning = false }
                            .godTouchHeight()
                            .padding(horizontal = Spacing.md, vertical = Spacing.sm)
                            .testTag(GodTags.COMBAT_DIALOG_CLOSE),
                    )
                },
                containerColor = ParchmentSurface,
            )
        }
    }
}
