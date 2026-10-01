// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.loot

import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import com.pathfindergod.spoke.R
import com.pathfindergod.spoke.ui.designsystem.Dimens
import com.pathfindergod.spoke.ui.designsystem.GodCard
import com.pathfindergod.spoke.ui.designsystem.Spacing
import com.pathfindergod.spoke.ui.icons.CategoryIcons
import com.pathfindergod.spoke.ui.theme.GoldAccent
import com.pathfindergod.spoke.ui.theme.TextPrimary
import com.pathfindergod.spoke.ui.theme.TextSecondary
import com.pathfindergod.spoke.ui.viewmodel.LootItem

@Composable
fun LootCard(
    item: LootItem,
    craftDc: Int?,
    modifier: Modifier = Modifier,
) {
    GodCard(
        modifier = modifier.fillMaxWidth(),
        contentPadding = PaddingValues(Dimens.cardPaddingTight),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(
                painter = painterResource(CategoryIcons.lootRarity(item.rarity)),
                contentDescription = null,
                tint = GoldAccent,
                modifier = Modifier.size(Dimens.iconInline).padding(end = Spacing.sm),
            )
            Text(
                text = item.name,
                style = MaterialTheme.typography.titleMedium,
                color = GoldAccent,
                modifier = Modifier.weight(1f),
            )
            Text(
                text = stringResource(R.string.loot_line_pattern, item.level, item.priceGp),
                style = MaterialTheme.typography.bodyMedium,
                color = TextSecondary,
            )
        }
        if (item.description.isNotBlank()) {
            Text(
                text = item.description,
                style = MaterialTheme.typography.bodyMedium,
                color = TextPrimary,
                modifier = Modifier.padding(top = Spacing.sm),
            )
        }
        Text(
            text = if (craftDc != null) {
                stringResource(R.string.loot_craft_pattern, item.rarity, craftDc)
            } else {
                item.rarity
            },
            style = MaterialTheme.typography.labelLarge,
            color = TextSecondary,
            modifier = Modifier.padding(top = Spacing.sm),
        )
    }
}
