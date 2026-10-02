// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.encounter

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import com.pathfindergod.spoke.ui.motion.StaggerIn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Icon
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
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.pathfindergod.spoke.R
import com.pathfindergod.spoke.data.local.AppDatabase
import com.pathfindergod.spoke.data.local.AppPreferences
import com.pathfindergod.spoke.data.local.EncounterEntity
import com.pathfindergod.spoke.data.network.HubApi
import com.pathfindergod.spoke.data.network.HubApiFactory
import com.pathfindergod.spoke.data.repository.EncounterRepository
import com.pathfindergod.spoke.ui.designsystem.Dimens
import com.pathfindergod.spoke.ui.designsystem.GodCard
import com.pathfindergod.spoke.ui.designsystem.GodChip
import com.pathfindergod.spoke.ui.designsystem.GodEmptyState
import com.pathfindergod.spoke.ui.designsystem.GodLiveRegion
import com.pathfindergod.spoke.ui.designsystem.GodPrimaryButton
import com.pathfindergod.spoke.ui.designsystem.GodSectionHeader
import com.pathfindergod.spoke.ui.designsystem.GodStatusText
import com.pathfindergod.spoke.ui.designsystem.GodTags
import com.pathfindergod.spoke.ui.designsystem.GodTextField
import com.pathfindergod.spoke.ui.designsystem.GodTone
import com.pathfindergod.spoke.ui.designsystem.Spacing
import com.pathfindergod.spoke.ui.designsystem.godTouchSize
import com.pathfindergod.spoke.ui.icons.CategoryIcons
import com.pathfindergod.spoke.ui.strings.resolve
import com.pathfindergod.spoke.ui.theme.CritRed
import com.pathfindergod.spoke.ui.theme.GoldAccent
import com.pathfindergod.spoke.ui.theme.TextPrimary
import com.pathfindergod.spoke.ui.theme.TextSecondary
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
    val prefs = remember { AppPreferences(context) }
    val api = remember { HubApiFactory.get(prefs.restUrl()) }
    val repository = remember {
        EncounterRepository(AppDatabase.get(context.applicationContext), api)
    }
    return viewModel(factory = remember { EncounterVmFactory(repository, api) })
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun EncounterScreen(
    viewModel: EncounterViewModel,
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    var level by rememberSaveable { mutableStateOf("3") }
    var theme by rememberSaveable { mutableStateOf("") }
    var themeError by rememberSaveable { mutableStateOf(false) }
    var difficulty by rememberSaveable { mutableStateOf("moderate") }
    val loading = state.phase == EncounterPhase.Loading
    Column(modifier = Modifier.fillMaxSize().padding(Spacing.lg)) {
        GodCard(title = { ForgeHeader() }) {
            Row(
                horizontalArrangement = Arrangement.spacedBy(Spacing.sm),
                modifier = Modifier.fillMaxWidth().padding(top = Spacing.sm),
            ) {
                GodTextField(
                    value = level,
                    onValueChange = { level = it },
                    label = stringResource(R.string.encounter_party_level),
                    numeric = true,
                    modifier = Modifier.weight(1f),
                )
                GodTextField(
                    value = theme,
                    onValueChange = { theme = it },
                    label = stringResource(R.string.encounter_theme),
                    modifier = Modifier.weight(2f),
                )
            }
            FlowRow(
                horizontalArrangement = Arrangement.spacedBy(Spacing.sm),
                verticalArrangement = Arrangement.spacedBy(Spacing.xs),
                modifier = Modifier.fillMaxWidth().padding(top = Spacing.md),
            ) {
                difficulties.forEach { option ->
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(
                            painter = painterResource(CategoryIcons.encounterDifficulty(option)),
                            contentDescription = null,
                            tint = if (difficulty == option) GoldAccent else TextSecondary,
                            modifier = Modifier.size(Dimens.iconInline).padding(end = Spacing.xs),
                        )
                        GodChip(
                            label = option.replaceFirstChar { it.uppercase() },
                            selected = difficulty == option,
                            onClick = { difficulty = option },
                            style = MaterialTheme.typography.labelLarge,
                            testTag = GodTags.encounterDifficulty(option),
                        )
                    }
                }
            }
            GodPrimaryButton(
                text = stringResource(
                    if (loading) R.string.encounter_mustering else R.string.encounter_conjure,
                ),
                enabled = !loading,
                onClickLabel = stringResource(R.string.a11y_encounter_conjure),
                onClick = {
                    // Same silent-no-op problem as the combat Add button: an
                    // early return with no feedback reads as a dropped tap.
                    if (theme.isBlank()) {
                        themeError = true
                        return@GodPrimaryButton
                    }
                    themeError = false
                    viewModel.generateEncounter(
                        level.toIntOrNull()?.coerceIn(1, 20) ?: 1,
                        difficulty,
                        theme.trim(),
                    )
                },
                modifier = Modifier.padding(top = Spacing.md),
            )
        }
        if (themeError) {
            GodStatusText(
                text = stringResource(R.string.encounter_theme_required),
                color = CritRed,
                modifier = Modifier.padding(top = Spacing.xs),
            )
        }
        (state.phase as? EncounterPhase.Error)?.let { error ->
            GodStatusText(
                text = error.message.resolve(),
                tone = GodTone.Critical,
                color = CritRed,
                modifier = Modifier.fillMaxWidth().padding(top = Spacing.sm),
            )
        }
        if (state.activeMonsters.isNotEmpty() && !loading) {
            GodLiveRegion(
                text = stringResource(
                    R.string.a11y_encounter_ready,
                    state.activeMonsters.size,
                    state.activeTargetXp,
                ),
                assertive = true,
                tag = GodTags.ENCOUNTER_STATUS,
                modifier = Modifier.fillMaxWidth().padding(top = Spacing.xs),
            )
        }
        if (state.activeMonsters.isEmpty() && !loading) {
            Box(
                modifier = Modifier.fillMaxWidth().weight(1f),
                contentAlignment = Alignment.Center,
            ) {
                GodEmptyState(text = stringResource(R.string.encounter_idle))
            }
        } else {
            LazyColumn(
                modifier = Modifier.fillMaxWidth().weight(1f).padding(top = Spacing.md),
                verticalArrangement = Arrangement.spacedBy(Dimens.gridSpacing),
            ) {
                if (state.activeLabel.isNotBlank()) {
                    item(key = "label") {
                        Text(
                            text = stringResource(
                                R.string.encounter_target_pattern,
                                state.activeLabel,
                                state.activeTargetXp,
                            ),
                            style = MaterialTheme.typography.titleMedium,
                            color = GoldAccent,
                        )
                    }
                }
                itemsIndexed(
                    state.activeMonsters,
                    // The hub parses the LLM array with no dedupe, so two entries can share a name
    // and level. A duplicate lazy key throws and kills the process.
    key = { index, _ -> "monster-$index" },
                ) { index, monster ->
                    StaggerIn(index = index, modifier = Modifier.animateItem()) {
                        MonsterCard(monster = monster)
                    }
                }
                if (state.encounters.isNotEmpty()) {
                    item(key = "vault") {
                        GodSectionHeader(
                            text = stringResource(R.string.encounter_vault),
                            modifier = Modifier.padding(top = Spacing.sm),
                        )
                    }
                    state.encounters.forEachIndexed { index, saved ->
                        item(key = "vault-${saved.id}") {
                            StaggerIn(index = index, modifier = Modifier.animateItem()) {
                                VaultRow(
                                    encounter = saved,
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
}

@Composable
private fun ForgeHeader() {
    Text(
        text = stringResource(R.string.encounter_forge),
        style = MaterialTheme.typography.titleMedium,
        color = GoldAccent,
    )
}

@Composable
private fun VaultRow(
    encounter: EncounterEntity,
    modifier: Modifier = Modifier,
    onSelect: () -> Unit,
    onDelete: () -> Unit,
) {
    GodCard(
        modifier = modifier.fillMaxWidth(),
        testTag = GodTags.encounter(encounter.id),
        contentPadding = PaddingValues(Dimens.cardPaddingTight),
        onClickLabel = stringResource(R.string.a11y_encounter_open, encounter.theme),
        onClick = onSelect,
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = encounter.theme,
                    style = MaterialTheme.typography.bodyMedium,
                    color = TextPrimary,
                )
                Text(
                    text = stringResource(
                        R.string.combat_pattern_threat_xp,
                        encounter.threat,
                        encounter.targetXp,
                    ),
                    style = MaterialTheme.typography.labelLarge,
                    color = TextSecondary,
                )
            }
            Text(
                text = stringResource(R.string.action_delete),
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold,
                color = CritRed,
                modifier = Modifier
                    .godTouchSize()
                    .clickable(
                        onClickLabel = stringResource(
                            R.string.a11y_encounter_delete,
                            encounter.theme,
                        ),
                        role = Role.Button,
                    ) { onDelete() }
                    .padding(Spacing.sm)
                    .testTag(GodTags.encounterDelete(encounter.id)),
            )
        }
    }
}
