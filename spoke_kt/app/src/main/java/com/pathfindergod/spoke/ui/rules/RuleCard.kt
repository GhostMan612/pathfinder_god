// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.rules

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.pathfindergod.spoke.R
import com.pathfindergod.spoke.data.local.RuleFtsEntity
import com.pathfindergod.spoke.ui.designsystem.Dimens
import com.pathfindergod.spoke.ui.designsystem.GodBadge
import com.pathfindergod.spoke.ui.designsystem.GodCard
import com.pathfindergod.spoke.ui.designsystem.GodTags
import com.pathfindergod.spoke.ui.designsystem.GodTone
import com.pathfindergod.spoke.ui.designsystem.Spacing
import com.pathfindergod.spoke.ui.designsystem.godMirrorInRtl
import com.pathfindergod.spoke.ui.designsystem.godRtlText
import com.pathfindergod.spoke.ui.theme.TextPrimary
import com.pathfindergod.spoke.ui.theme.TextSecondary

@Composable
fun RuleCard(
    rule: RuleFtsEntity,
    modifier: Modifier = Modifier,
) {
    var expanded by remember { mutableStateOf(false) }
    val body = remember(rule.rowId) { rule.rawContent.take(8000) }
    GodCard(
        modifier = modifier.fillMaxWidth(),
        testTag = GodTags.rule(rule.rowId),
        contentPadding = PaddingValues(Dimens.cardPaddingTight),
        onClickLabel = stringResource(
            if (expanded) R.string.a11y_rule_collapse else R.string.a11y_rule_expand,
            rule.name,
        ),
        stateDescription = stringResource(
            if (expanded) R.string.a11y_state_expanded else R.string.a11y_state_collapsed,
        ),
        onClick = { expanded = !expanded },
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = rule.name,
                    style = MaterialTheme.typography.titleMedium,
                    color = TextPrimary,
                )
                Text(
                    text = stringResource(R.string.rule_meta_pattern, rule.category, rule.sourceBook),
                    style = MaterialTheme.typography.bodyMedium,
                    color = TextSecondary,
                )
            }
            GodBadge(
                text = rule.system.uppercase(),
                tone = if (rule.system == "2e") GodTone.Accent else GodTone.Critical,
            )
            Text(
                text = if (expanded) {
                    stringResource(R.string.disclosure_expanded)
                } else {
                    godRtlText(
                        R.string.disclosure_collapsed,
                        R.string.disclosure_collapsed_rtl,
                    )
                },
                style = MaterialTheme.typography.titleMedium,
                color = TextSecondary,
                modifier = Modifier
                    .godMirrorInRtl()
                    .padding(start = Spacing.sm),
            )
        }
        if (expanded) {
            Text(
                text = body,
                style = MaterialTheme.typography.bodyMedium,
                color = TextPrimary,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = Spacing.sm)
                    .heightIn(max = 280.dp)
                    .verticalScroll(rememberScrollState()),
            )
        }
    }
}
