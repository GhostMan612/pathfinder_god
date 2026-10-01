// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.designsystem

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import com.pathfindergod.spoke.ui.theme.CritRed
import com.pathfindergod.spoke.ui.theme.GoldAccent
import com.pathfindergod.spoke.ui.theme.StatusGreen
import com.pathfindergod.spoke.ui.theme.TextPrimary
import com.pathfindergod.spoke.ui.theme.TextSecondary

enum class GodTone { Neutral, Accent, Positive, Critical }

fun GodTone.resolve(): Color = when (this) {
    GodTone.Neutral -> TextSecondary
    GodTone.Accent -> GoldAccent
    GodTone.Positive -> StatusGreen
    GodTone.Critical -> CritRed
}

@Composable
fun GodStatusText(
    text: String,
    modifier: Modifier = Modifier,
    tone: GodTone = GodTone.Neutral,
    color: Color = tone.resolve(),
) {
    Text(
        text = text,
        style = MaterialTheme.typography.bodyMedium,
        color = color,
        modifier = modifier,
    )
}

@Composable
fun GodSectionHeader(
    text: String,
    modifier: Modifier = Modifier,
    prominent: Boolean = false,
) {
    Text(
        text = text,
        style = if (prominent) {
            MaterialTheme.typography.titleLarge
        } else {
            MaterialTheme.typography.titleMedium
        },
        fontWeight = FontWeight.Bold,
        color = if (prominent) GoldAccent else TextSecondary,
        modifier = modifier.padding(top = 4.dp),
    )
}

@Composable
fun GodBackLink(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    testTag: String? = null,
) {
    Text(
        text = text,
        style = MaterialTheme.typography.labelLarge,
        color = GoldAccent,
        modifier = modifier
            .clickable(
                onClickLabel = text,
                role = Role.Button,
                onClick = onClick,
            )
            .godTouchHeight()
            .padding(horizontal = Spacing.xs, vertical = Spacing.md)
            .then(if (testTag == null) Modifier else Modifier.testTag(testTag)),
    )
}

@Composable
fun GodBadge(
    text: String,
    modifier: Modifier = Modifier,
    tone: GodTone = GodTone.Accent,
    horizontalPadding: Dp = 8.dp,
    verticalPadding: Dp = 4.dp,
) {
    Text(
        text = text,
        style = MaterialTheme.typography.labelLarge,
        fontWeight = FontWeight.Bold,
        color = tone.resolve(),
        modifier = modifier
            .godCard(
                fill = TextPrimary.copy(alpha = 0.06f),
                border = tone.resolve().copy(alpha = 0.7f),
            )
            .padding(horizontal = horizontalPadding, vertical = verticalPadding),
    )
}
