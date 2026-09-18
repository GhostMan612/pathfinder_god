// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.rules

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.pathfindergod.spoke.data.local.RuleFtsEntity
import com.pathfindergod.spoke.ui.theme.CritRed
import com.pathfindergod.spoke.ui.theme.GodTypography
import com.pathfindergod.spoke.ui.theme.GoldAccent
import com.pathfindergod.spoke.ui.theme.TextPrimary
import com.pathfindergod.spoke.ui.theme.TextSecondary
import com.pathfindergod.spoke.ui.theme.rpgPanel

@Composable
fun RuleCard(
    rule: RuleFtsEntity,
    modifier: Modifier = Modifier,
) {
    var expanded by remember { mutableStateOf(false) }
    val body = remember(rule.rowId) { rule.rawContent.take(8000) }
    Column(
        modifier = modifier.rpgPanel().clickable { expanded = !expanded }.padding(12.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = rule.name,
                    style = GodTypography.titleMedium,
                    color = TextPrimary,
                )
                Text(
                    text = "${rule.category} · ${rule.sourceBook}",
                    style = GodTypography.bodyMedium,
                    color = TextSecondary,
                )
            }
            Text(
                text = rule.system.uppercase(),
                style = GodTypography.labelLarge,
                fontWeight = FontWeight.Bold,
                color = if (rule.system == "2e") GoldAccent else CritRed,
                modifier = Modifier.rpgPanel().padding(horizontal = 8.dp, vertical = 4.dp),
            )
            Text(
                text = if (expanded) "▾" else "▸",
                style = GodTypography.titleMedium,
                color = TextSecondary,
                modifier = Modifier.padding(start = 8.dp),
            )
        }
        if (expanded) {
            Text(
                text = body,
                style = GodTypography.bodyMedium,
                color = TextPrimary,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 8.dp)
                    .heightIn(max = 280.dp)
                    .verticalScroll(rememberScrollState()),
            )
        }
    }
}
