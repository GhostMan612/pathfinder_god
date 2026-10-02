// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.dice

import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.pathfindergod.spoke.R
import com.pathfindergod.spoke.data.local.AppDatabase
import com.pathfindergod.spoke.data.local.AppPreferences
import com.pathfindergod.spoke.data.repository.RollRepository
import com.pathfindergod.spoke.service.AudioService
import com.pathfindergod.spoke.ui.designsystem.GodChip
import com.pathfindergod.spoke.ui.designsystem.GodPrimaryButton
import com.pathfindergod.spoke.ui.designsystem.GodSectionHeader
import com.pathfindergod.spoke.ui.designsystem.GodStatusText
import com.pathfindergod.spoke.ui.designsystem.GodTags
import com.pathfindergod.spoke.ui.designsystem.GodTone
import com.pathfindergod.spoke.ui.designsystem.Spacing
import com.pathfindergod.spoke.ui.motion.StaggerIn
import com.pathfindergod.spoke.ui.pit.FilamentPit
import com.pathfindergod.spoke.ui.strings.resolve
import com.pathfindergod.spoke.ui.theme.CritRed
import com.pathfindergod.spoke.ui.theme.GoldAccent
import com.pathfindergod.spoke.ui.theme.TextSecondary
import com.pathfindergod.spoke.ui.viewmodel.DiceUiState
import com.pathfindergod.spoke.ui.viewmodel.DiceViewModel
import com.pathfindergod.spoke.ui.viewmodel.RollEntry
import kotlin.math.abs

private val COUNT_STEPS = listOf(1, 2, 3, 4, 5, 6, 8, 10)
private val MODIFIER_STEPS = listOf(-3, -2, -1, 0, 1, 2, 3, 5)
private val TARGET_STEPS = listOf(5, 10, 11, 12, 14, 15, 16, 18, 20, 25)

private class DiceVmFactory(
    private val repository: RollRepository,
    private val audio: AudioService,
) : ViewModelProvider.Factory {
    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>): T =
        DiceViewModel(repository, audio) as T
}

@Composable
fun DiceScreen(initialDie: Die? = null) {
    val context = LocalContext.current
    val database = remember { AppDatabase.get(context.applicationContext) }
    val repository = remember(database) { RollRepository(database.rollDao()) }
    val audio = remember { AudioService.get(context) }
    val preferences = remember { AppPreferences(context.applicationContext) }
    val viewModel: DiceViewModel = viewModel(
        factory = remember { DiceVmFactory(repository, audio) },
    )
    val state by viewModel.state.collectAsStateWithLifecycle()
    val pit = preferences.pitEnabled()

    LaunchedEffect(initialDie) {
        if (initialDie != null) viewModel.selectDie(initialDie)
    }

    LazyColumn(
        modifier = Modifier.fillMaxSize().padding(Spacing.lg),
        verticalArrangement = Arrangement.spacedBy(Spacing.md),
    ) {
        item(key = "roller") {
            Roller(
                state = state,
                pit = pit,
                onImpact = viewModel::playImpact,
            )
        }
        item(key = "dice") {
            DieRow(selected = state.die, onSelect = viewModel::selectDie)
        }
        item(key = "count") {
            CountRow(state = state, onSelect = viewModel::setCount)
        }
        item(key = "modifier") {
            ModifierRow(state = state, onSelect = viewModel::setModifier)
        }
        item(key = "keep") {
            KeepRow(state = state, onSelect = viewModel::setKeepHighest)
        }
        item(key = "mode") {
            ModeRow(state = state, viewModel = viewModel)
        }
        item(key = "roll") {
            GodPrimaryButton(
                text = stringResource(R.string.dice_roll),
                onClick = viewModel::roll,
                testTag = GodTags.DICE_ROLL_BUTTON,
            )
        }
        item(key = "history-heading") {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                GodSectionHeader(text = stringResource(R.string.dice_history_heading))
                GodChip(
                    label = stringResource(R.string.dice_history_clear),
                    onClick = viewModel::clearHistory,
                    enabled = state.history.isNotEmpty(),
                    style = MaterialTheme.typography.labelLarge,
                    horizontalPadding = Spacing.sm,
                    verticalPadding = Spacing.xs,
                    role = Role.Button,
                    selectedStateRes = null,
                    onClickLabel = stringResource(R.string.a11y_history_clear),
                    testTag = GodTags.DICE_HISTORY_CLEAR,
                )
            }
        }
        itemsIndexed(
            items = state.history,
            key = { _, entry -> entry.key },
        ) { index, entry ->
            StaggerIn(index = index, modifier = Modifier.animateItem()) {
                HistoryRow(entry = entry)
            }
        }
    }
}

@Composable
private fun Roller(
    state: DiceUiState,
    pit: Boolean,
    onImpact: () -> Unit,
) {
    val record = state.record
    val announcement = rollAnnouncement(record)
    val critical = record != null && record.impact != Impact.NORMAL
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Box(
            modifier = Modifier.fillMaxWidth().padding(top = Spacing.sm),
            contentAlignment = Alignment.Center,
        ) {
            if (pit) {
                FilamentPit(
                    die = state.die,
                    face = state.face,
                    rollToken = state.rollToken,
                    impact = record?.impact ?: Impact.NORMAL,
                    modifier = Modifier.size(220.dp).testTag(GodTags.DICE_PIT),
                    onImpact = onImpact,
                )
            } else {
                DiceCanvas(
                    die = state.die,
                    face = state.face,
                    rollToken = state.rollToken,
                    modifier = Modifier.size(180.dp).testTag(GodTags.DICE_PIT),
                    impact = record?.impact ?: Impact.NORMAL,
                    onImpact = onImpact,
                )
            }
        }
        Box(
            modifier = Modifier.clearAndSetSemantics {
                liveRegion = if (critical) {
                    LiveRegionMode.Assertive
                } else {
                    LiveRegionMode.Polite
                }
                contentDescription = announcement
                testTag = GodTags.DICE_RESULT
            },
        ) {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text(
                    text = record?.let { "${it.total}" } ?: stringResource(R.string.dice_no_result),
                    style = MaterialTheme.typography.displayLarge,
                    fontWeight = FontWeight.Bold,
                    color = GoldAccent,
                )
                Text(
                    text = record?.let { impactLabel(it) } ?: stringResource(R.string.dice_prompt),
                    style = MaterialTheme.typography.bodyMedium,
                    color = TextSecondary,
                )
            }
        }
        state.error?.let { error ->
            GodStatusText(
                text = error.resolve(),
                tone = GodTone.Critical,
                color = CritRed,
                modifier = Modifier.padding(top = Spacing.xs),
            )
        }
    }
}

@Composable
private fun rollAnnouncement(record: RollRecord?): String {
    if (record == null) return stringResource(R.string.a11y_roll_idle)
    val base = when (record.impact) {
        Impact.CRITICAL_SUCCESS -> stringResource(
            R.string.a11y_roll_crit_success,
            record.notation,
            record.total,
        )
        Impact.CRITICAL_FAILURE -> stringResource(
            R.string.a11y_roll_crit_failure,
            record.notation,
            record.total,
        )
        Impact.NORMAL -> stringResource(
            R.string.a11y_roll_normal,
            record.notation,
            record.total,
        )
    }
    val degree = record.degree
    val target = record.targetNumber
    val suffix = if (degree != null && target != null) {
        stringResource(
            R.string.a11y_roll_degree,
            target,
            stringResource(degreeLabel(degree)),
        )
    } else {
        ""
    }
    return "$base $suffix".trim()
}

@Composable
private fun DieRow(selected: Die, onSelect: (Die) -> Unit) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceEvenly,
    ) {
        Die.entries.forEach { die ->
            GodChip(
                label = stringResource(R.string.dice_face_pattern, die.sides),
                selected = die == selected,
                onClick = { onSelect(die) },
                style = MaterialTheme.typography.bodyMedium,
                horizontalPadding = Spacing.sm,
                verticalPadding = Spacing.xs,
                testTag = GodTags.diceDie(die.sides),
            )
        }
    }
}

@Composable
private fun CountRow(
    state: DiceUiState,
    onSelect: (Int) -> Unit,
) {
    Row(
        // Scrollable: there is no horizontalScroll anywhere in this lane, so a
        // Row of 11 chips on a 360dp screen squeezed the last ones below the
        // 48dp minimum. TN 20 / TN 25 - the highest-value targets - collapsed
        // to untappable slivers.
        modifier = Modifier
            .fillMaxWidth()
            .horizontalScroll(rememberScrollState()),
        horizontalArrangement = Arrangement.spacedBy(Spacing.xs, Alignment.CenterHorizontally),
    ) {
        Text(
            text = stringResource(R.string.dice_count_label),
            style = MaterialTheme.typography.labelLarge,
            color = TextSecondary,
        )
        COUNT_STEPS.forEach { step ->
            GodChip(
                label = step.toString(),
                selected = state.count == step,
                onClick = { onSelect(step) },
                style = MaterialTheme.typography.labelLarge,
                horizontalPadding = Spacing.sm,
                verticalPadding = Spacing.xs,
                testTag = GodTags.diceCount(step),
            )
        }
    }
}

@Composable
private fun ModifierRow(
    state: DiceUiState,
    onSelect: (Int) -> Unit,
) {
    Row(
        // Scrollable: there is no horizontalScroll anywhere in this lane, so a
        // Row of 11 chips on a 360dp screen squeezed the last ones below the
        // 48dp minimum. TN 20 / TN 25 - the highest-value targets - collapsed
        // to untappable slivers.
        modifier = Modifier
            .fillMaxWidth()
            .horizontalScroll(rememberScrollState()),
        horizontalArrangement = Arrangement.spacedBy(Spacing.xs, Alignment.CenterHorizontally),
    ) {
        Text(
            text = stringResource(R.string.dice_modifier_label),
            style = MaterialTheme.typography.labelLarge,
            color = TextSecondary,
        )
        MODIFIER_STEPS.forEach { step ->
            GodChip(
                label = signedLabel(step),
                selected = state.modifier == step,
                onClick = { onSelect(step) },
                style = MaterialTheme.typography.labelLarge,
                horizontalPadding = Spacing.sm,
                verticalPadding = Spacing.xs,
                testTag = GodTags.diceModifier(step),
            )
        }
    }
}

@Composable
private fun KeepRow(
    state: DiceUiState,
    onSelect: (Int?) -> Unit,
) {
    Row(
        // Scrollable: there is no horizontalScroll anywhere in this lane, so a
        // Row of 11 chips on a 360dp screen squeezed the last ones below the
        // 48dp minimum. TN 20 / TN 25 - the highest-value targets - collapsed
        // to untappable slivers.
        modifier = Modifier
            .fillMaxWidth()
            .horizontalScroll(rememberScrollState()),
        horizontalArrangement = Arrangement.spacedBy(Spacing.xs, Alignment.CenterHorizontally),
    ) {
        Text(
            text = stringResource(R.string.dice_keep_label),
            style = MaterialTheme.typography.labelLarge,
            color = TextSecondary,
        )
        GodChip(
            label = stringResource(R.string.dice_keep_all),
            selected = !state.supportsKeep || state.keepHighest == null,
            onClick = { onSelect(null) },
            style = MaterialTheme.typography.labelLarge,
            horizontalPadding = Spacing.sm,
            verticalPadding = Spacing.xs,
            testTag = GodTags.diceKeep(null),
        )
        if (state.supportsKeep) {
            (1..state.count).forEach { keep ->
                GodChip(
                    label = stringResource(R.string.dice_keep_highest_pattern, keep),
                    selected = state.keepHighest == keep,
                    onClick = { onSelect(keep) },
                    style = MaterialTheme.typography.labelLarge,
                    horizontalPadding = Spacing.sm,
                    verticalPadding = Spacing.xs,
                    testTag = GodTags.diceKeep(keep),
                )
            }
        }
    }
}

@Composable
private fun ModeRow(
    state: DiceUiState,
    viewModel: DiceViewModel,
) {
    Column {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.spacedBy(Spacing.xs, Alignment.CenterHorizontally),
        ) {
            Advantage.entries.forEach { entry ->
                GodChip(
                    label = stringResource(advantageLabel(entry)),
                    selected = state.advantage == entry && state.supportsAdvantage,
                    enabled = entry == Advantage.STRAIGHT || state.supportsAdvantage,
                    onClick = { viewModel.setAdvantage(entry) },
                    style = MaterialTheme.typography.labelLarge,
                    horizontalPadding = Spacing.sm,
                    verticalPadding = Spacing.xs,
                    testTag = GodTags.diceAdvantage(entry.name),
                )
            }
            GodChip(
                label = stringResource(R.string.dice_explode),
                selected = state.exploding,
                onClick = { viewModel.setExploding(!state.exploding) },
                style = MaterialTheme.typography.labelLarge,
                horizontalPadding = Spacing.sm,
                verticalPadding = Spacing.xs,
                testTag = GodTags.DICE_EXPLODE,
            )
        }
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(top = Spacing.xs),
            horizontalArrangement = Arrangement.spacedBy(Spacing.xs, Alignment.CenterHorizontally),
        ) {
            Text(
                text = stringResource(R.string.dice_target_label),
                style = MaterialTheme.typography.labelLarge,
                color = TextSecondary,
            )
            GodChip(
                label = stringResource(R.string.dice_target_off),
                selected = state.targetNumber == null,
                onClick = { viewModel.setTargetNumber(null) },
                style = MaterialTheme.typography.labelLarge,
                horizontalPadding = Spacing.sm,
                verticalPadding = Spacing.xs,
                testTag = GodTags.diceTarget(null),
            )
            TARGET_STEPS.forEach { target ->
                GodChip(
                    label = stringResource(R.string.dice_target_pattern, target),
                    selected = state.targetNumber == target,
                    onClick = { viewModel.setTargetNumber(target) },
                    style = MaterialTheme.typography.labelLarge,
                    horizontalPadding = Spacing.sm,
                    verticalPadding = Spacing.xs,
                    testTag = GodTags.diceTarget(target),
                )
            }
        }
    }
}

@Composable
private fun HistoryRow(entry: RollEntry) {
    val record = entry.record
    Column(modifier = Modifier.fillMaxWidth().padding(vertical = Spacing.xs)) {
        Text(
            text = stringResource(R.string.dice_rolled_pattern, record.notation, record.total),
            style = MaterialTheme.typography.bodyMedium,
            color = when (record.impact) {
                Impact.CRITICAL_SUCCESS -> GoldAccent
                Impact.CRITICAL_FAILURE -> CritRed
                Impact.NORMAL -> TextSecondary
            },
        )
        if (record.dropped.isNotEmpty()) {
            Text(
                text = stringResource(
                    R.string.dice_dropped_pattern,
                    DiceLabels.dice(record.dropped, stringResource(R.string.dice_join_plus)),
                ),
                style = MaterialTheme.typography.labelLarge,
                color = TextSecondary,
            )
        }
        val degree = record.degree
        val target = record.targetNumber
        if (degree != null && target != null) {
            Text(
                text = stringResource(
                    R.string.dice_degree_pattern,
                    target,
                    stringResource(degreeLabel(degree)),
                ),
                style = MaterialTheme.typography.labelLarge,
                color = when (degree) {
                    DegreeOfSuccess.CRITICAL_SUCCESS -> GoldAccent
                    DegreeOfSuccess.CRITICAL_FAILURE -> CritRed
                    else -> TextSecondary
                },
            )
        }
    }
}

@Composable
private fun impactLabel(record: RollRecord): String = when (record.impact) {
    Impact.CRITICAL_SUCCESS -> stringResource(R.string.dice_crit_success, record.notation)
    Impact.CRITICAL_FAILURE -> stringResource(R.string.dice_crit_failure, record.notation)
    Impact.NORMAL -> {
        val joiner = stringResource(R.string.dice_join_plus)
        val modifier = when {
            record.modifier > 0 -> stringResource(R.string.dice_modifier_plus, record.modifier)
            record.modifier < 0 -> stringResource(R.string.dice_modifier_minus, abs(record.modifier))
            else -> null
        }
        stringResource(
            R.string.dice_normal_keeps,
            record.notation,
            DiceLabels.expression(record.kept, joiner, modifier),
        )
    }
}

@Composable
private fun signedLabel(modifier: Int): String = when {
    modifier > 0 -> stringResource(R.string.dice_modifier_plus, modifier)
    modifier < 0 -> stringResource(R.string.dice_modifier_minus, abs(modifier))
    else -> modifier.toString()
}

private fun advantageLabel(advantage: Advantage): Int = when (advantage) {
    Advantage.STRAIGHT -> R.string.dice_advantage_straight
    Advantage.ADVANTAGE -> R.string.dice_advantage_advantage
    Advantage.DISADVANTAGE -> R.string.dice_advantage_disadvantage
}

private fun degreeLabel(degree: DegreeOfSuccess): Int = when (degree) {
    DegreeOfSuccess.CRITICAL_SUCCESS -> R.string.dice_degree_critical_success
    DegreeOfSuccess.SUCCESS -> R.string.dice_degree_success
    DegreeOfSuccess.FAILURE -> R.string.dice_degree_failure
    DegreeOfSuccess.CRITICAL_FAILURE -> R.string.dice_degree_critical_failure
}
