// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.loot

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.pathfindergod.spoke.ui.theme.GodTypography
import com.pathfindergod.spoke.ui.theme.GoldAccent
import com.pathfindergod.spoke.ui.theme.TextPrimary
import com.pathfindergod.spoke.ui.theme.TextSecondary
import com.pathfindergod.spoke.ui.theme.rpgPanel
import com.pathfindergod.spoke.ui.viewmodel.LootItem

@Composable
fun LootCard(
    item: LootItem,
    craftDc: Int?,
    modifier: Modifier = Modifier,
) {
    Column(modifier = modifier.rpgPanel().fillMaxWidth().padding(12.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(
                text = item.name,
                style = GodTypography.titleMedium,
                color = GoldAccent,
                modifier = Modifier.weight(1f),
            )
            Text(
                text = "Lv ${item.level} · ${item.priceGp}",
                style = GodTypography.bodyMedium,
                color = TextSecondary,
            )
        }
        if (item.description.isNotBlank()) {
            Text(
                text = item.description,
                style = GodTypography.bodyMedium,
                color = TextPrimary,
                modifier = Modifier.padding(top = 6.dp),
            )
        }
        Text(
            text = if (craftDc != null) {
                "${item.rarity} · Craft DC $craftDc"
            } else {
                item.rarity
            },
            style = GodTypography.labelLarge,
            color = TextSecondary,
            modifier = Modifier.padding(top = 6.dp),
        )
    }
}
