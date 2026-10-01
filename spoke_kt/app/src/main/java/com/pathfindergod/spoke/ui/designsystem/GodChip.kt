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
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import com.pathfindergod.spoke.R
import com.pathfindergod.spoke.ui.theme.GoldAccent
import com.pathfindergod.spoke.ui.theme.TextPrimary
import com.pathfindergod.spoke.ui.theme.TextSecondary

@Composable
fun GodChip(
    label: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    testTag: String? = null,
    selected: Boolean = false,
    enabled: Boolean = true,
    role: Role = Role.RadioButton,
    selectedStateRes: Int? = R.string.a11y_state_selected,
    onClickLabel: String? = null,
    contentDescription: String? = null,
    containerColor: Color = TextPrimary.copy(alpha = 0.06f),
    borderColor: Color = GoldAccent,
    style: TextStyle = MaterialTheme.typography.titleMedium,
    horizontalPadding: Dp = Dimens.chipPaddingH,
    verticalPadding: Dp = Dimens.chipPaddingV,
) {
    val contentColor = when {
        !enabled -> TextSecondary.copy(alpha = 0.4f)
        selected -> GoldAccent
        else -> TextPrimary
    }
    val announcedState = selectedStateRes?.let { res ->
        stringResource(if (selected) res else R.string.a11y_state_not_selected)
    }
    Text(
        text = label,
        style = style,
        fontWeight = if (selected) FontWeight.Bold else FontWeight.Normal,
        color = contentColor,
        modifier = modifier
            .godCard(
                fill = containerColor.copy(alpha = if (enabled) containerColor.alpha else containerColor.alpha * 0.4f),
                border = borderColor.copy(alpha = if (enabled) 1f else 0.4f),
            )
            .clickable(
                enabled = enabled,
                onClickLabel = onClickLabel,
                role = role,
                onClick = onClick,
            )
            .godTouchHeight()
            .semantics(mergeDescendants = true) {
                if (announcedState != null) stateDescription = announcedState
                if (contentDescription != null) this.contentDescription = contentDescription
            }
            .padding(horizontal = horizontalPadding, vertical = verticalPadding)
            .then(if (testTag == null) Modifier else Modifier.testTag(testTag)),
    )
}
