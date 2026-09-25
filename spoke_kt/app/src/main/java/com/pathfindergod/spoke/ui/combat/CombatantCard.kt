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
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.ui.graphics.graphicsLayer
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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.pathfindergod.spoke.ui.theme.CritRed
import com.pathfindergod.spoke.ui.theme.GodTypography
import com.pathfindergod.spoke.ui.theme.GoldAccent
import com.pathfindergod.spoke.ui.theme.ParchmentSurface
import com.pathfindergod.spoke.ui.theme.TextPrimary
import com.pathfindergod.spoke.ui.theme.TextSecondary
import com.pathfindergod.spoke.ui.theme.VoidBackground
import com.pathfindergod.spoke.ui.theme.rpgPanel
import com.pathfindergod.spoke.ui.viewmodel.CombatCondition
import com.pathfindergod.spoke.ui.viewmodel.Combatant

private val quickConditions = listOf(
    CombatCondition("Frightened", 1),
    CombatCondition("Prone"),
    CombatCondition("Sickened", 1),
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
    val rise = remember { Animatable(0f) }
    val shake = remember { Animatable(0f) }
    LaunchedEffect(combatant.currentHp) {
        val delta = combatant.currentHp - lastHp
        lastHp = combatant.currentHp
        if (delta != 0) {
            floater = delta
            launch {
                rise.snapTo(0f)
                rise.animateTo(1f, tween(900))
                floater = null
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
    Column(
        modifier = modifier
            .graphicsLayer { translationX = shake.value }
            .rpgPanel(
                fill = if (isActive) ParchmentSurface else VoidBackground,
                border = border,
            ).fillMaxWidth().padding(horizontal = 12.dp, vertical = 10.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(
                horizontalAlignment = Alignment.CenterHorizontally,
                modifier = Modifier.padding(end = 12.dp),
            ) {
                Text(
                    text = "${combatant.initiative}",
                    style = GodTypography.titleLarge,
                    fontWeight = FontWeight.Bold,
                    color = GoldAccent,
                )
                Text(
                    text = "INIT",
                    style = GodTypography.labelLarge,
                    color = TextSecondary,
                )
            }
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = combatant.name,
                    style = GodTypography.titleMedium,
                    color = TextPrimary,
                )
                if (combatant.conditions.isNotEmpty()) {
                    FlowRow(
                        horizontalArrangement = Arrangement.spacedBy(6.dp),
                        verticalArrangement = Arrangement.spacedBy(4.dp),
                        modifier = Modifier.padding(top = 4.dp),
                    ) {
                        combatant.conditions.forEach { condition ->
                            Text(
                                text = if (condition.value > 1) {
                                    "${condition.name} ${condition.value}"
                                } else {
                                    condition.name
                                },
                                style = GodTypography.labelLarge,
                                color = GoldAccent,
                                modifier = Modifier
                                    .rpgPanel()
                                    .clickable { onRemoveCondition(condition.name) }
                                    .padding(horizontal = 8.dp, vertical = 4.dp),
                            )
                        }
                    }
                }
            }
            Box(contentAlignment = Alignment.TopCenter) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Text(
                        text = "${combatant.currentHp}/${combatant.maxHp}",
                        style = GodTypography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        color = if (combatant.maxHp > 0 && combatant.currentHp * 2 < combatant.maxHp) {
                            CritRed
                        } else {
                            TextPrimary
                        },
                    )
                    Text(
                        text = "HP",
                        style = GodTypography.labelLarge,
                        color = TextSecondary,
                    )
                }
                val amount = floater
                if (amount != null && rise.value < 1f) {
                    Text(
                        text = if (amount > 0) "+$amount" else "$amount",
                        style = GodTypography.titleMedium,
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
        Box(modifier = Modifier.fillMaxWidth().padding(top = 8.dp)) {
            Box(
                modifier = Modifier.fillMaxWidth().height(8.dp)
                    .background(TextSecondary.copy(alpha = 0.25f)),
            )
            Box(
                modifier = Modifier.fillMaxWidth(ghost).height(8.dp)
                    .background(barColor.copy(alpha = 0.45f)),
            )
            Box(
                modifier = Modifier.fillMaxWidth(fraction).height(8.dp)
                    .background(barColor),
            )
        }
        Row(
            modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
            horizontalArrangement = Arrangement.SpaceEvenly,
        ) {
            Text(
                text = "−5",
                style = GodTypography.titleMedium,
                color = CritRed,
                modifier = Modifier.clickable { onDamage() }.padding(6.dp),
            )
            Text(
                text = "+5",
                style = GodTypography.titleMedium,
                color = GoldAccent,
                modifier = Modifier.clickable { onHeal() }.padding(6.dp),
            )
            Text(
                text = "+Cond",
                style = GodTypography.titleMedium,
                color = TextPrimary,
                modifier = Modifier.clickable { picking = !picking }.padding(6.dp),
            )
        }
        if (picking) {
            FlowRow(
                horizontalArrangement = Arrangement.spacedBy(6.dp),
                modifier = Modifier.fillMaxWidth().padding(top = 4.dp),
            ) {
                quickConditions.forEach { condition ->
                    Text(
                        text = condition.name,
                        style = GodTypography.bodyMedium,
                        color = TextSecondary,
                        modifier = Modifier
                            .rpgPanel()
                            .clickable {
                                onAddCondition(condition)
                                picking = false
                            }
                            .padding(horizontal = 10.dp, vertical = 6.dp),
                    )
                }
            }
        }
    }
}
