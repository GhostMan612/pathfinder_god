// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.loot

import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
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
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.pathfindergod.spoke.R
import com.pathfindergod.spoke.data.local.AppPreferences
import com.pathfindergod.spoke.data.network.HubApiFactory
import com.pathfindergod.spoke.data.network.HubWebSocketClient
import com.pathfindergod.spoke.ui.designsystem.Dimens
import com.pathfindergod.spoke.ui.designsystem.GodBadge
import com.pathfindergod.spoke.ui.designsystem.GodCard
import com.pathfindergod.spoke.ui.designsystem.GodChip
import com.pathfindergod.spoke.ui.designsystem.GodEmptyState
import com.pathfindergod.spoke.ui.designsystem.GodLiveRegion
import com.pathfindergod.spoke.ui.designsystem.GodPrimaryButton
import com.pathfindergod.spoke.ui.designsystem.GodSectionHeader
import com.pathfindergod.spoke.ui.designsystem.GodStatTile
import com.pathfindergod.spoke.ui.designsystem.GodStatusText
import com.pathfindergod.spoke.ui.designsystem.GodTags
import com.pathfindergod.spoke.ui.designsystem.GodTextField
import com.pathfindergod.spoke.ui.designsystem.GodTexture
import com.pathfindergod.spoke.ui.designsystem.GodTone
import com.pathfindergod.spoke.ui.designsystem.Spacing
import com.pathfindergod.spoke.ui.motion.StaggerIn
import com.pathfindergod.spoke.ui.strings.resolve
import com.pathfindergod.spoke.ui.theme.CritRed
import com.pathfindergod.spoke.ui.theme.GoldAccent
import com.pathfindergod.spoke.ui.theme.TextPrimary
import com.pathfindergod.spoke.ui.theme.TextSecondary
import com.pathfindergod.spoke.ui.viewmodel.GmCampaignStateUi
import com.pathfindergod.spoke.ui.viewmodel.GmChatEntry
import com.pathfindergod.spoke.ui.viewmodel.GmChatViewModel
import com.pathfindergod.spoke.ui.viewmodel.LootViewModel

private class GmChatVmFactory(
    private val viewModel: GmChatViewModel,
) : ViewModelProvider.Factory {
    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>): T =
        viewModel as T
}

@Composable
internal fun rememberGmChatViewModel(): GmChatViewModel {
    val context = LocalContext.current
    val prefs = remember { AppPreferences(context) }
    val delegate = remember {
        GmChatViewModel(
            api = HubApiFactory.get(prefs.restUrl()),
            streamClient = HubWebSocketClient(),
            streamUrlProvider = { prefs.streamUrl() },
        )
    }
    return viewModel(factory = remember { GmChatVmFactory(delegate) })
}

@Composable
fun GodScreen(
    gmViewModel: GmChatViewModel,
    lootViewModel: LootViewModel,
) {
    var showChat by rememberSaveable { mutableStateOf(true) }
    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(GodTexture.parchmentBrush()),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = Spacing.lg, vertical = Spacing.sm),
            horizontalArrangement = Arrangement.spacedBy(Spacing.sm),
        ) {
            GodChip(
                label = stringResource(R.string.god_mode_chat),
                selected = showChat,
                onClickLabel = stringResource(R.string.a11y_god_mode_chat),
                testTag = GodTags.GOD_MODE_CHAT,
                onClick = { showChat = true },
            )
            GodChip(
                label = stringResource(R.string.god_mode_loot),
                selected = !showChat,
                onClickLabel = stringResource(R.string.a11y_god_mode_loot),
                testTag = GodTags.GOD_MODE_LOOT,
                onClick = { showChat = false },
            )
        }
        Box(modifier = Modifier.fillMaxWidth().weight(1f)) {
            if (showChat) {
                GmChatScreen(viewModel = gmViewModel)
            } else {
                LootScreen(viewModel = lootViewModel)
            }
        }
    }
}

@Composable
fun GmChatScreen(
    viewModel: GmChatViewModel,
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    var input by rememberSaveable { mutableStateOf("") }

    LaunchedEffect(Unit) {
        viewModel.refreshCampaignState()
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(horizontal = Spacing.lg, vertical = Spacing.sm),
    ) {
        CampaignStateCard(state = state.campaignState)

        if (state.isBusy) {
            GodStatusText(
                text = stringResource(R.string.gm_streaming),
                modifier = Modifier.padding(top = Spacing.xs),
            )
        }

        state.error?.let { err ->
            GodStatusText(
                text = err.resolve(),
                tone = GodTone.Critical,
                color = CritRed,
                modifier = Modifier.padding(top = Spacing.xs),
            )
        }

        val lastReady = state.entries.lastOrNull { !it.isStreaming && it.narration.isNotBlank() }
        if (lastReady != null) {
            GodLiveRegion(
                text = stringResource(R.string.a11y_gm_ready, lastReady.narration),
                tag = GodTags.GM_STATUS,
                modifier = Modifier.padding(top = Spacing.xxs),
            )
        }

        if (state.entries.isEmpty()) {
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(1f)
                    .testTag(GodTags.GM_TRANSCRIPT),
                contentAlignment = Alignment.Center,
            ) {
                GodEmptyState(text = stringResource(R.string.gm_empty))
            }
        } else {
            LazyColumn(
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(1f)
                    .padding(top = Spacing.sm)
                    .testTag(GodTags.GM_TRANSCRIPT),
                verticalArrangement = Arrangement.spacedBy(Dimens.gridSpacing),
            ) {
                itemsIndexed(state.entries, key = { _, item -> item.id }) { index, entry ->
                    StaggerIn(index = index, modifier = Modifier.animateItem()) {
                        GmEntryCard(entry = entry)
                    }
                }
            }
        }

        if (state.activeChoices.isNotEmpty()) {
            GodSectionHeader(
                text = stringResource(R.string.gm_choices_header),
                modifier = Modifier.padding(top = Spacing.xs),
            )
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .horizontalScroll(rememberScrollState())
                    .padding(vertical = Spacing.xs)
                    .testTag(GodTags.GM_CHOICES),
                horizontalArrangement = Arrangement.spacedBy(Spacing.sm),
            ) {
                state.activeChoices.forEachIndexed { index, choice ->
                    GodChip(
                        label = choice,
                        selected = false,
                        role = Role.Button,
                        selectedStateRes = null,
                        onClickLabel = stringResource(R.string.a11y_gm_choice, choice),
                        testTag = GodTags.gmChoice(index),
                        onClick = {
                            if (!state.isBusy) {
                                viewModel.takeTurn(choice)
                            }
                        },
                    )
                }
            }
        }

        GodTextField(
            value = input,
            onValueChange = { input = it },
            label = stringResource(R.string.gm_input_label),
            numeric = false,
            modifier = Modifier
                .fillMaxWidth()
                .padding(top = Spacing.xs)
                .testTag(GodTags.GM_INPUT),
        )

        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(top = Spacing.sm, bottom = Spacing.xs),
            horizontalArrangement = Arrangement.spacedBy(Spacing.sm),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            GodPrimaryButton(
                text = stringResource(R.string.gm_send_turn),
                enabled = !state.isBusy && input.isNotBlank(),
                onClickLabel = stringResource(R.string.a11y_gm_send_turn),
                testTag = GodTags.GM_SEND_TURN,
                onClick = {
                    val action = input.trim()
                    if (action.isNotEmpty()) {
                        input = ""
                        viewModel.takeTurn(action)
                    }
                },
                modifier = Modifier.weight(1f),
            )
            GodChip(
                label = stringResource(R.string.gm_send_ask),
                selected = true,
                role = Role.Button,
                selectedStateRes = null,
                onClickLabel = stringResource(R.string.a11y_gm_send_ask),
                testTag = GodTags.GM_SEND_ASK,
                onClick = {
                    val query = input.trim()
                    if (query.isNotEmpty() && !state.isBusy) {
                        input = ""
                        viewModel.ask(query)
                    }
                },
            )
        }
    }
}

@Composable
private fun CampaignStateCard(state: GmCampaignStateUi) {
    val inCombat = state.phase.equals("combat", ignoreCase = true)
    GodCard(
        title = {
            Text(
                text = state.name.ifBlank { stringResource(R.string.gm_state_title) },
                style = MaterialTheme.typography.titleMedium,
                color = GoldAccent,
            )
        },
        trailing = {
            GodBadge(
                text = if (inCombat) {
                    stringResource(R.string.gm_state_phase_combat)
                } else {
                    stringResource(R.string.gm_state_phase_exploration)
                },
                tone = if (inCombat) GodTone.Positive else GodTone.Neutral,
            )
        },
        contentPadding = PaddingValues(Dimens.cardPaddingTight),
        testTag = GodTags.GM_STATE_CARD,
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceEvenly,
        ) {
            GodStatTile(
                label = stringResource(R.string.gm_state_round),
                value = state.round.toString(),
            )
            GodStatTile(
                label = stringResource(R.string.gm_state_location),
                value = state.location ?: stringResource(R.string.value_unknown),
            )
            GodStatTile(
                label = stringResource(R.string.gm_state_active),
                value = state.activeCombatant ?: stringResource(R.string.value_unknown),
            )
        }
        if (state.conditions.isNotEmpty()) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .horizontalScroll(rememberScrollState())
                    .padding(top = Spacing.xs),
                horizontalArrangement = Arrangement.spacedBy(Spacing.xs),
            ) {
                state.conditions.forEach { cond ->
                    GodBadge(
                        text = stringResource(
                            R.string.gm_condition_pattern,
                            cond.combatant,
                            cond.name,
                            cond.value,
                        ),
                        tone = GodTone.Critical,
                    )
                }
            }
        }
    }
}

@Composable
private fun GmEntryCard(entry: GmChatEntry) {
    GodCard(
        title = {
            Text(
                text = entry.prompt,
                style = MaterialTheme.typography.titleSmall,
                color = GoldAccent,
            )
        },
        trailing = {
            val badgeLabel = when {
                entry.turnNum != null -> stringResource(R.string.gm_turn_badge, entry.turnNum)
                entry.isAsk -> stringResource(
                    R.string.gm_oracle_badge,
                    entry.backend.ifBlank { "ollama" },
                )
                else -> stringResource(R.string.gm_state_phase_exploration)
            }
            GodBadge(text = badgeLabel, tone = GodTone.Neutral)
        },
        contentPadding = PaddingValues(Dimens.cardPaddingTight),
    ) {
        if (entry.diceRolls.isNotEmpty()) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .horizontalScroll(rememberScrollState())
                    .padding(top = Spacing.xs),
                horizontalArrangement = Arrangement.spacedBy(Spacing.xs),
            ) {
                entry.diceRolls.forEach { roll ->
                    GodBadge(
                        text = stringResource(R.string.gm_dice_pattern, roll.notation, roll.total),
                        tone = GodTone.Neutral,
                    )
                }
            }
        }
        if (entry.hpChanges.isNotEmpty()) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .horizontalScroll(rememberScrollState())
                    .padding(top = Spacing.xs),
                horizontalArrangement = Arrangement.spacedBy(Spacing.xs),
            ) {
                entry.hpChanges.forEach { hp ->
                    val label = if (hp.isHeal) {
                        stringResource(
                            R.string.gm_hp_heal_pattern,
                            hp.name,
                            hp.deltaAmount,
                            hp.hp,
                            hp.maxHp,
                        )
                    } else {
                        stringResource(
                            R.string.gm_hp_damage_pattern,
                            hp.name,
                            hp.deltaAmount,
                            hp.hp,
                            hp.maxHp,
                        )
                    }
                    GodBadge(
                        text = label,
                        tone = if (hp.isHeal) GodTone.Positive else GodTone.Critical,
                    )
                }
            }
        }
        if (entry.conditions.isNotEmpty()) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .horizontalScroll(rememberScrollState())
                    .padding(top = Spacing.xs),
                horizontalArrangement = Arrangement.spacedBy(Spacing.xs),
            ) {
                entry.conditions.forEach { cond ->
                    GodBadge(
                        text = stringResource(
                            R.string.gm_condition_pattern,
                            cond.combatant,
                            cond.name,
                            cond.value,
                        ),
                        tone = GodTone.Critical,
                    )
                }
            }
        }
        if (entry.narration.isNotBlank()) {
            Text(
                text = entry.narration,
                style = MaterialTheme.typography.bodyMedium,
                color = TextPrimary,
                modifier = Modifier.padding(top = Spacing.sm),
            )
        }
        if (entry.sources.isNotEmpty()) {
            Text(
                text = stringResource(
                    R.string.gm_sources_pattern,
                    entry.sources.joinToString(", "),
                ),
                style = MaterialTheme.typography.labelSmall,
                color = TextSecondary,
                modifier = Modifier.padding(top = Spacing.xs),
            )
        }
    }
}
