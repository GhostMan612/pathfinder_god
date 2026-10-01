// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.encounter

import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.pathfindergod.spoke.R
import com.pathfindergod.spoke.data.network.EncounterMonster
import com.pathfindergod.spoke.ui.designsystem.Dimens
import com.pathfindergod.spoke.ui.designsystem.GodBadge
import com.pathfindergod.spoke.ui.designsystem.GodCard
import com.pathfindergod.spoke.ui.designsystem.Spacing
import com.pathfindergod.spoke.ui.theme.GoldAccent
import com.pathfindergod.spoke.ui.theme.TextPrimary
import com.pathfindergod.spoke.ui.theme.TextSecondary

@Composable
fun MonsterCard(
    monster: EncounterMonster,
    modifier: Modifier = Modifier,
) {
    GodCard(
        modifier = modifier.fillMaxWidth(),
        contentPadding = PaddingValues(Dimens.cardPaddingTight),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(
                text = monster.name,
                style = MaterialTheme.typography.titleMedium,
                color = GoldAccent,
                modifier = Modifier.weight(1f),
            )
            if (monster.count > 1) {
                GodBadge(text = stringResource(R.string.monster_count_pattern, monster.count))
            }
            Text(
                text = stringResource(R.string.monster_level_pattern, monster.level),
                style = MaterialTheme.typography.bodyMedium,
                color = TextSecondary,
                modifier = Modifier.padding(start = Spacing.sm),
            )
        }
        Text(
            text = stringResource(R.string.monster_xp_pattern, monster.xpEach, monster.totalXp),
            style = MaterialTheme.typography.bodyMedium,
            color = TextPrimary,
            modifier = Modifier.padding(top = Spacing.sm),
        )
        if (monster.sourceBook.isNotBlank()) {
            Text(
                text = monster.sourceBook,
                style = MaterialTheme.typography.labelLarge,
                color = TextSecondary,
                modifier = Modifier.padding(top = Spacing.xxs),
            )
        }
    }
}
