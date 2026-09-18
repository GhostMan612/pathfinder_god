// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.combat

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
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
    Column(
        modifier = modifier.rpgPanel(
            fill = if (isActive) ParchmentSurface else VoidBackground,
            border = if (isActive) GoldAccent else GoldAccent.copy(alpha = 0.35f),
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
