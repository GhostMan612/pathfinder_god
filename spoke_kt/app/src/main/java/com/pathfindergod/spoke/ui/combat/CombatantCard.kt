// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.combat

import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import kotlinx.coroutines.launch
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.text.font.FontWeight
import com.pathfindergod.spoke.R
import com.pathfindergod.spoke.ui.designsystem.Dimens
import com.pathfindergod.spoke.ui.designsystem.GodCard
import com.pathfindergod.spoke.ui.designsystem.GodChip
import com.pathfindergod.spoke.ui.designsystem.GodProgressBar
import com.pathfindergod.spoke.ui.designsystem.GodTags
import com.pathfindergod.spoke.ui.designsystem.godTouchHeight
import com.pathfindergod.spoke.ui.designsystem.Spacing
import com.pathfindergod.spoke.ui.icons.CategoryIcons
import com.pathfindergod.spoke.ui.theme.CritRed
import com.pathfindergod.spoke.ui.theme.GoldAccent
import com.pathfindergod.spoke.ui.theme.ParchmentSurface
import com.pathfindergod.spoke.ui.theme.TextPrimary
import com.pathfindergod.spoke.ui.theme.TextSecondary
import com.pathfindergod.spoke.ui.theme.VoidBackground
import com.pathfindergod.spoke.ui.viewmodel.CombatCondition
import com.pathfindergod.spoke.ui.viewmodel.Combatant

@Composable
private fun rememberQuickConditions(): List<CombatCondition> = listOf(
    CombatCondition(stringResource(R.string.combat_condition_frightened), 1),
    CombatCondition(stringResource(R.string.combat_condition_prone), 1),
    CombatCondition(stringResource(R.string.combat_condition_sickened), 1),
)

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun CombatantCard(
    combatant: Combatant,
    isActive: Boolean,
    modifier: Modifier = Modifier,
    onDamage: () -> Unit,
    onHeal: () -> Unit,
    onAddCondition: (CombatCondition) -> Unit,
    onRemoveCondition: (String) -> Unit,
) {
    var picking by rememberSaveable { mutableStateOf(false) }
    val quickConditions = rememberQuickConditions()
    val frightened = stringResource(R.string.combat_condition_frightened)
    val prone = stringResource(R.string.combat_condition_prone)
    val sickened = stringResource(R.string.combat_condition_sickened)
    val fraction = if (combatant.maxHp > 0) {
        (combatant.currentHp.toFloat() / combatant.maxHp).coerceIn(0f, 1f)
    } else {
        0f
    }
    val barColor = if (fraction < 0.5f) CritRed else GoldAccent
    val ghost by animateFloatAsState(
        targetValue = fraction,
        animationSpec = tween(durationMillis = 700, delayMillis = 350),
    )
    val border by animateColorAsState(
        targetValue = if (isActive) GoldAccent else GoldAccent.copy(alpha = 0.35f),
        animationSpec = tween(400),
    )
    var lastHp by remember { mutableStateOf(combatant.currentHp) }
    var floater by remember { mutableStateOf<Int?>(null) }
    var hpDelta by remember(combatant.id) { mutableStateOf<Int?>(null) }
    val rise = remember { Animatable(0f) }
    val shake = remember { Animatable(0f) }
    LaunchedEffect(combatant.id, combatant.currentHp) {
        val delta = combatant.currentHp - lastHp
        lastHp = combatant.currentHp
        if (delta != 0) {
            floater = delta
            hpDelta = delta
            launch {
                rise.snapTo(0f)
                rise.animateTo(1f, tween(900))
                floater = null
                // hpDelta was never cleared, so hpDescription stayed pinned to
                // the FIRST HP change. Heal a combatant back to full and the
                // live region still announced "Goblin took 5 damage, now
                // 12/12" - a false statement about current HP.
                hpDelta = null
            }
            if (delta < 0) {
                launch {
                    shake.snapTo(-12f)
                    shake.animateTo(
                        0f,
                        spring(Spring.DampingRatioHighBouncy, Spring.StiffnessMedium),
                    )
                }
            }
        }
    }
    val lastDelta = hpDelta
    val hpLost = combatant.maxHp > 0 && combatant.currentHp == 0
    val hpDescription = if (lastDelta == null) {
        stringResource(
            R.string.a11y_combatant_card,
            combatant.name,
            combatant.initiative,
            combatant.currentHp,
            combatant.maxHp,
        )
    } else {
        hpChangePhrase(
            name = combatant.name,
            delta = lastDelta,
            currentHp = combatant.currentHp,
            maxHp = combatant.maxHp,
        )
    }
    GodCard(
        modifier = modifier
            .graphicsLayer { translationX = shake.value }
            .fillMaxWidth(),
        testTag = GodTags.combatant(combatant.id),
        containerColor = if (isActive) ParchmentSurface else VoidBackground,
        borderColor = border,
        stateDescription = if (isActive) {
            stringResource(R.string.a11y_combatant_active)
        } else {
            null
        },
        contentDescription = stringResource(
            R.string.a11y_combatant_card,
            combatant.name,
            combatant.initiative,
            combatant.currentHp,
            combatant.maxHp,
        ),
        contentPadding = PaddingValues(start = Spacing.md, end = Spacing.md, top = Spacing.md, bottom = Spacing.md),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(
                horizontalAlignment = Alignment.CenterHorizontally,
                modifier = Modifier.padding(end = Spacing.md),
            ) {
                Text(
                    text = "${combatant.initiative}",
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.Bold,
                    color = GoldAccent,
                )
                Text(
                    text = stringResource(R.string.combat_init_label),
                    style = MaterialTheme.typography.labelLarge,
                    color = TextSecondary,
                )
            }
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = combatant.name,
                    style = MaterialTheme.typography.titleMedium,
                    color = TextPrimary,
                )
                if (combatant.conditions.isNotEmpty()) {
                    FlowRow(
                        horizontalArrangement = Arrangement.spacedBy(Spacing.sm),
                        verticalArrangement = Arrangement.spacedBy(Spacing.xs),
                        modifier = Modifier.padding(top = Spacing.xs),
                    ) {
                        combatant.conditions.forEach { condition ->
                            val glyph = CategoryIcons.condition(
                                condition.name,
                                frightened,
                                prone,
                                sickened,
                            )
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                if (glyph != null) {
                                    Icon(
                                        painter = painterResource(glyph),
                                        contentDescription = null,
                                        tint = CritRed,
                                        modifier = Modifier
                                            .size(Dimens.iconInline)
                                            .padding(end = Spacing.xs),
                                    )
                                }
                                GodChip(
                                    label = if (condition.value > 1) {
                                        stringResource(
                                            R.string.combat_condition_pattern,
                                            condition.name,
                                            condition.value,
                                        )
                                    } else {
                                        condition.name
                                    },
                                    selected = true,
                                    onClick = { onRemoveCondition(condition.name) },
                                    style = MaterialTheme.typography.labelLarge,
                                    horizontalPadding = Spacing.sm,
                                    verticalPadding = Spacing.xs,
                                    role = Role.Button,
                                    selectedStateRes = null,
                                    contentDescription = stringResource(
                                        R.string.a11y_condition_applied,
                                        condition.name,
                                    ),
                                    onClickLabel = stringResource(
                                        R.string.a11y_condition_remove,
                                        condition.name,
                                    ),
                                    testTag = GodTags.combatantCondition(
                                        combatant.id,
                                        condition.name,
                                    ),
                                )
                            }
                        }
                    }
                }
            }
            Box(contentAlignment = Alignment.TopCenter) {
                Column(
                    horizontalAlignment = Alignment.CenterHorizontally,
                    modifier = Modifier
                        .clearAndSetSemantics {
                            liveRegion = if (hpLost) {
                                LiveRegionMode.Assertive
                            } else {
                                LiveRegionMode.Polite
                            }
                            contentDescription = hpDescription
                        },
                ) {
                    Text(
                        text = "${combatant.currentHp}/${combatant.maxHp}",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        color = if (combatant.maxHp > 0 && combatant.currentHp * 2 < combatant.maxHp) {
                            CritRed
                        } else {
                            TextPrimary
                        },
                    )
                    Text(
                        text = stringResource(R.string.combat_hp_label),
                        style = MaterialTheme.typography.labelLarge,
                        color = TextSecondary,
                    )
                }
                val amount = floater
                if (amount != null) {
                    Text(
                        text = if (amount > 0) "+$amount" else "$amount",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        color = if (amount > 0) GoldAccent else CritRed,
                        modifier = Modifier.graphicsLayer {
                            translationY = -rise.value * 44f
                            alpha = 1f - rise.value
                        },
                    )
                }
            }
        }
        GodProgressBar(
            fraction = fraction,
            ghostFraction = ghost,
            barColor = barColor,
            label = stringResource(
                R.string.a11y_hp_bar,
                combatant.name,
                combatant.currentHp,
                combatant.maxHp,
            ),
            modifier = Modifier.fillMaxWidth().padding(top = Spacing.sm),
        )
        Row(
            modifier = Modifier.fillMaxWidth().padding(top = Spacing.xs),
            horizontalArrangement = Arrangement.SpaceEvenly,
        ) {
            Text(
                text = stringResource(R.string.combat_damage_five),
                style = MaterialTheme.typography.titleMedium,
                color = CritRed,
                modifier = Modifier
                    .clickable(
                        onClickLabel = stringResource(R.string.a11y_damage_five, combatant.name),
                        role = Role.Button,
                        onClick = { onDamage() },
                    )
                    .godTouchHeight()
                    .padding(Spacing.sm)
                    .testTag(GodTags.combatantDamage(combatant.id)),
            )
            Text(
                text = stringResource(R.string.combat_heal_five),
                style = MaterialTheme.typography.titleMedium,
                color = GoldAccent,
                modifier = Modifier
                    .clickable(
                        onClickLabel = stringResource(R.string.a11y_heal_five, combatant.name),
                        role = Role.Button,
                        onClick = { onHeal() },
                    )
                    .godTouchHeight()
                    .padding(Spacing.sm)
                    .testTag(GodTags.combatantHeal(combatant.id)),
            )
            Text(
                text = stringResource(R.string.combat_add_condition),
                style = MaterialTheme.typography.titleMedium,
                color = TextPrimary,
                modifier = Modifier
                    .clickable(
                        onClickLabel = stringResource(R.string.a11y_condition_add, combatant.name),
                        role = Role.Button,
                        onClick = { picking = !picking },
                    )
                    .godTouchHeight()
                    .padding(Spacing.sm)
                    .testTag(GodTags.combatantConditions(combatant.id)),
            )
        }
        if (picking) {
            FlowRow(
                horizontalArrangement = Arrangement.spacedBy(Spacing.sm),
                modifier = Modifier.fillMaxWidth().padding(top = Spacing.xs),
            ) {
                quickConditions.forEach { condition ->
                    val glyph = CategoryIcons.condition(
                        condition.name,
                        frightened,
                        prone,
                        sickened,
                    )
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        if (glyph != null) {
                            Icon(
                                painter = painterResource(glyph),
                                contentDescription = null,
                                tint = CritRed,
                                modifier = Modifier
                                    .size(Dimens.iconInline)
                                    .padding(end = Spacing.xs),
                            )
                        }
                        GodChip(
                            label = condition.name,
                            role = Role.Button,
                            selectedStateRes = null,
                            onClickLabel = stringResource(R.string.a11y_condition_apply, condition.name),
                            contentDescription = stringResource(
                                R.string.a11y_condition_chip,
                                condition.name,
                            ),
                            onClick = {
                                onAddCondition(condition)
                                picking = false
                            },
                            style = MaterialTheme.typography.bodyMedium,
                            horizontalPadding = Spacing.md,
                            verticalPadding = Spacing.sm,
                            testTag = GodTags.combatantCondition(
                                combatant.id,
                                condition.name,
                            ),
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun hpChangePhrase(
    name: String,
    delta: Int,
    currentHp: Int,
    maxHp: Int,
): String = when {
    currentHp <= 0 -> stringResource(R.string.a11y_hp_down, name)
    delta < 0 -> stringResource(
        R.string.a11y_hp_damage,
        name,
        -delta,
        currentHp,
        maxHp,
    )
    else -> stringResource(R.string.a11y_hp_heal, name, delta, currentHp, maxHp)
}
