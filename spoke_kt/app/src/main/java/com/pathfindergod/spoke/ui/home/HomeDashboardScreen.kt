// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.home

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.pathfindergod.spoke.R
import com.pathfindergod.spoke.ui.designsystem.Dimens
import com.pathfindergod.spoke.ui.designsystem.GlassCard
import com.pathfindergod.spoke.ui.designsystem.GodBadge
import com.pathfindergod.spoke.ui.designsystem.GodCard
import com.pathfindergod.spoke.ui.designsystem.GodChip
import com.pathfindergod.spoke.ui.designsystem.GodProgressBar
import com.pathfindergod.spoke.ui.designsystem.GodSectionHeader
import com.pathfindergod.spoke.ui.designsystem.GodStatTile
import com.pathfindergod.spoke.ui.designsystem.GodStatusText
import com.pathfindergod.spoke.ui.designsystem.GodTags
import com.pathfindergod.spoke.ui.designsystem.GodTone
import com.pathfindergod.spoke.ui.designsystem.Spacing
import com.pathfindergod.spoke.ui.dice.Die
import com.pathfindergod.spoke.ui.navigation.Destination
import com.pathfindergod.spoke.ui.navigation.Destinations
import com.pathfindergod.spoke.ui.theme.GoldAccent
import com.pathfindergod.spoke.ui.theme.TextPrimary
import com.pathfindergod.spoke.ui.theme.TextSecondary
import com.pathfindergod.spoke.ui.viewmodel.CharacterViewModel
import com.pathfindergod.spoke.ui.viewmodel.CombatViewModel
import com.pathfindergod.spoke.ui.viewmodel.EncounterViewModel
import com.pathfindergod.spoke.ui.viewmodel.MapViewModel

@Composable
fun HomeDashboardScreen(
    characters: CharacterViewModel,
    combat: CombatViewModel,
    encounters: EncounterViewModel,
    maps: MapViewModel,
    onOpen: (Destination) -> Unit,
    onQuickRoll: (Die) -> Unit,
) {
    val roster by characters.state.collectAsStateWithLifecycle()
    val combatState by combat.state.collectAsStateWithLifecycle()
    val encounterState by encounters.state.collectAsStateWithLifecycle()
    val mapState by maps.state.collectAsStateWithLifecycle()
    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(Spacing.lg),
        verticalArrangement = Arrangement.spacedBy(Spacing.md),
    ) {
        HomeHeader()
        PartyTurnCard(
            heroCount = roster.characters.size,
            round = combatState.currentRound,
            turnIndex = combatState.activeIndex,
            activeName = combat.activeCombatant?.name,
            activeHp = combat.activeCombatant?.currentHp ?: 0,
            maxHp = combat.activeCombatant?.maxHp ?: 0,
        )
        QuickRollCard(onQuickRoll = onQuickRoll)
        ActiveEncounterCard(
            label = encounterState.activeLabel,
            monsterCount = encounterState.activeMonsters.size,
            targetXp = encounterState.activeTargetXp,
            onOpen = { onOpen(Destinations.Encounter) },
        )
        GodSectionHeader(
            text = stringResource(R.string.home_section_destinations),
            prominent = true,
        )
        DestinationCard(
            destination = Destinations.Campaign,
            status = stringResource(R.string.home_campaign_hint),
            onOpen = onOpen,
        )
        DestinationCard(
            destination = Destinations.Map,
            status = if (mapState.maps.isEmpty()) {
                stringResource(R.string.home_map_empty)
            } else {
                stringResource(R.string.home_map_count, mapState.maps.size)
            },
            onOpen = onOpen,
        )
        DestinationCard(
            destination = Destinations.Encounter,
            status = if (encounterState.encounters.isEmpty()) {
                stringResource(R.string.home_encounter_vault_empty)
            } else {
                stringResource(R.string.home_encounter_vault_count, encounterState.encounters.size)
            },
            onOpen = onOpen,
        )
        DestinationCard(
            destination = Destinations.God,
            status = stringResource(R.string.home_god_hint),
            onOpen = onOpen,
        )
        DestinationCard(
            destination = Destinations.Setup,
            status = stringResource(R.string.home_setup_hint),
            onOpen = onOpen,
        )
    }
}

@Composable
private fun HomeHeader() {
    GlassCard(modifier = Modifier.fillMaxWidth()) {
        Column {
            Text(
                text = stringResource(R.string.home_title),
                style = MaterialTheme.typography.headlineSmall,
                color = GoldAccent,
            )
            GodStatusText(text = stringResource(R.string.home_subtitle))
        }
    }
}

@Composable
private fun PartyTurnCard(
    heroCount: Int,
    round: Int,
    turnIndex: Int,
    activeName: String?,
    activeHp: Int,
    maxHp: Int,
) {
    GodCard(
        title = {
            Text(
                text = stringResource(R.string.home_party_title),
                style = MaterialTheme.typography.titleMedium,
                color = GoldAccent,
            )
        },
        trailing = {
            GodBadge(
                text = if (activeName == null) {
                    stringResource(R.string.home_badge_idle)
                } else {
                    stringResource(R.string.home_badge_active)
                },
                tone = if (activeName == null) GodTone.Neutral else GodTone.Positive,
            )
        },
        testTag = GodTags.HOME_PARTY,
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceEvenly,
        ) {
            GodStatTile(
                label = stringResource(R.string.home_stat_heroes),
                value = heroCount.toString(),
            )
            GodStatTile(
                label = stringResource(R.string.home_stat_round),
                value = round.toString(),
            )
            GodStatTile(
                label = stringResource(R.string.home_stat_turn),
                value = if (activeName == null) {
                    stringResource(R.string.value_unknown)
                } else {
                    (turnIndex + 1).toString()
                },
            )
        }
        if (activeName == null) {
            GodStatusText(
                text = stringResource(R.string.home_turn_idle),
                modifier = Modifier.padding(top = Spacing.md),
            )
        } else {
            Text(
                text = activeName,
                style = MaterialTheme.typography.titleMedium,
                color = TextPrimary,
                modifier = Modifier.padding(top = Spacing.md),
            )
            GodProgressBar(
                fraction = if (maxHp <= 0) 0f else activeHp.toFloat() / maxHp.toFloat(),
                label = stringResource(R.string.a11y_hp_bar, activeName, activeHp, maxHp),
                modifier = Modifier.padding(top = Spacing.sm),
            )
            GodStatusText(
                text = stringResource(R.string.home_hp, activeHp, maxHp),
                modifier = Modifier.padding(top = Spacing.xs),
            )
        }
    }
}

@Composable
private fun QuickRollCard(onQuickRoll: (Die) -> Unit) {
    GodSectionHeader(text = stringResource(R.string.home_section_quick_roll))
    GodCard(contentPadding = PaddingValues(Dimens.cardPaddingTight)) {
        Die.entries.chunked(3).forEach { row ->
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(vertical = Spacing.xs),
                horizontalArrangement = Arrangement.spacedBy(Spacing.sm, Alignment.CenterHorizontally),
            ) {
                row.forEach { die ->
                    GodChip(
                        label = stringResource(R.string.home_die, die.sides),
                        onClick = { onQuickRoll(die) },
                        style = MaterialTheme.typography.bodyMedium,
                        horizontalPadding = Spacing.md,
                        verticalPadding = Spacing.sm,
                        role = Role.Button,
                        selectedStateRes = null,
                        onClickLabel = stringResource(R.string.a11y_quick_roll, die.sides),
                        testTag = GodTags.homeQuickDie(die.sides),
                    )
                }
            }
        }
    }
}

@Composable
private fun ActiveEncounterCard(
    label: String,
    monsterCount: Int,
    targetXp: Int,
    onOpen: () -> Unit,
) {
    GodCard(
        title = {
            Text(
                text = stringResource(R.string.home_encounter_title),
                style = MaterialTheme.typography.titleMedium,
                color = GoldAccent,
            )
        },
        onClickLabel = stringResource(R.string.a11y_home_encounter_open),
        testTag = GodTags.HOME_ENCOUNTER,
        onClick = onOpen,
    ) {
        if (label.isBlank()) {
            GodStatusText(text = stringResource(R.string.home_encounter_empty))
        } else {
            Text(
                text = label,
                style = MaterialTheme.typography.bodyLarge,
                color = TextPrimary,
            )
            GodStatusText(
                text = stringResource(R.string.home_monsters, monsterCount, targetXp),
                modifier = Modifier.padding(top = Spacing.xs),
            )
        }
    }
}

@Composable
private fun DestinationCard(
    destination: Destination,
    status: String,
    onOpen: (Destination) -> Unit,
) {
    GodCard(
        contentPadding = PaddingValues(Dimens.cardPaddingTight),
        onClick = { onOpen(destination) },
        onClickLabel = stringResource(R.string.a11y_open_destination, status),
        testTag = GodTags.homeDestination(destination.route),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(
                painter = painterResource(destination.iconRes),
                contentDescription = null,
                tint = GoldAccent,
                modifier = Modifier.size(Dimens.statusDot * 2),
            )
            Column(
                modifier = Modifier
                    .weight(1f)
                    .padding(start = Spacing.md),
            ) {
                Text(
                    text = stringResource(destination.labelRes),
                    style = MaterialTheme.typography.titleMedium,
                    color = TextPrimary,
                )
                GodStatusText(text = status, color = TextSecondary)
            }
        }
    }
}