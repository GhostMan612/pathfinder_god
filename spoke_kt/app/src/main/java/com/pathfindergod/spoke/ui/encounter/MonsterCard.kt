// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.encounter

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.pathfindergod.spoke.data.network.EncounterMonster
import com.pathfindergod.spoke.ui.theme.GodTypography
import com.pathfindergod.spoke.ui.theme.GoldAccent
import com.pathfindergod.spoke.ui.theme.TextPrimary
import com.pathfindergod.spoke.ui.theme.TextSecondary
import com.pathfindergod.spoke.ui.theme.rpgPanel

@Composable
fun MonsterCard(
    monster: EncounterMonster,
    modifier: Modifier = Modifier,
) {
    Column(modifier = modifier.rpgPanel().fillMaxWidth().padding(12.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(
                text = monster.name,
                style = GodTypography.titleMedium,
                color = GoldAccent,
                modifier = Modifier.weight(1f),
            )
            if (monster.count > 1) {
                Text(
                    text = "×${monster.count}",
                    style = GodTypography.labelLarge,
                    fontWeight = FontWeight.Bold,
                    color = GoldAccent,
                    modifier = Modifier.rpgPanel().padding(horizontal = 8.dp, vertical = 4.dp),
                )
            }
            Text(
                text = "Lv ${monster.level}",
                style = GodTypography.bodyMedium,
                color = TextSecondary,
                modifier = Modifier.padding(start = 8.dp),
            )
        }
        Text(
            text = "${monster.xpEach} XP each · ${monster.totalXp} XP total",
            style = GodTypography.bodyMedium,
            color = TextPrimary,
            modifier = Modifier.padding(top = 6.dp),
        )
        if (monster.sourceBook.isNotBlank()) {
            Text(
                text = monster.sourceBook,
                style = GodTypography.labelLarge,
                color = TextSecondary,
                modifier = Modifier.padding(top = 2.dp),
            )
        }
    }
}
