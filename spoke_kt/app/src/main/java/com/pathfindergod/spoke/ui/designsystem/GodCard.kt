// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.designsystem

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.calculateEndPadding
import androidx.compose.foundation.layout.calculateStartPadding
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.selection.toggleable
import androidx.compose.runtime.Composable
import androidx.compose.runtime.State
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.drawWithCache
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.LayoutDirection
import com.pathfindergod.spoke.ui.theme.GoldAccent
import com.pathfindergod.spoke.ui.theme.ParchmentSurface

fun Modifier.godCard(
    cornerRadius: Dp = Dimens.panelCorner,
    fill: Color = ParchmentSurface,
    border: Color = GoldAccent,
): Modifier = godCardState(
    cornerRadius = cornerRadius,
    fill = fill,
    // Plain holder, not remember{}: this is a Modifier extension, not a
    // @Composable, so it cannot call remember. The draw lambda only ever
    // reads this value, so a constant holder is correct here.
    border = object : State<Color> {
        override val value: Color = border
    },
)

/**
 * Border-color-aware variant for animated borders (BP-08 O7).
 *
 * The border is read inside `onDrawBehind`, i.e. at DRAW time, so an animated
 * [State] passed here updates the stroke without recomposing the card subtree on
 * every animation frame. Reading it in composition instead meant a border
 * animation re-ran composition for the whole card ~60x/second.
 */
fun Modifier.godCardState(
    cornerRadius: Dp = Dimens.panelCorner,
    fill: Color = ParchmentSurface,
    border: State<Color>,
): Modifier = this.drawWithCache {
    val radiusPx = cornerRadius.toPx()
    val outer = CornerRadius(radiusPx, radiusPx)
    val outerStroke = Stroke(width = Dimens.outerStroke.toPx())
    val inset = Dimens.innerInset.toPx()
    val innerStroke = Stroke(width = Dimens.innerStroke.toPx())
    val notch = Dimens.notchLength.toPx()
    val notchStroke = Dimens.notchStroke.toPx()
    onDrawBehind {
        val borderColor = border.value
        drawRoundRect(color = fill, cornerRadius = outer)
        drawRoundRect(color = borderColor, cornerRadius = outer, style = outerStroke)
        drawRoundRect(
            color = borderColor.copy(alpha = 0.55f),
            topLeft = Offset(inset, inset),
            size = Size(size.width - inset * 2f, size.height - inset * 2f),
            cornerRadius = CornerRadius((radiusPx - inset).coerceAtLeast(0f)),
            style = innerStroke,
        )
        val w = size.width
        val h = size.height
        drawLine(borderColor, Offset(0f, notch), Offset(notch, 0f), notchStroke)
        drawLine(borderColor, Offset(w - notch, 0f), Offset(w, notch), notchStroke)
        drawLine(borderColor, Offset(w, h - notch), Offset(w - notch, h), notchStroke)
        drawLine(borderColor, Offset(notch, h), Offset(0f, h - notch), notchStroke)
    }
}

@Composable
fun GodCard(
    modifier: Modifier = Modifier,
    testTag: String? = null,
    title: (@Composable () -> Unit)? = null,
    trailing: (@Composable () -> Unit)? = null,
    containerColor: Color = ParchmentSurface,
    borderColor: Color = GoldAccent,
    // BP-08 O7: pass an animated border here and it is sampled in the draw
    // phase instead of recomposing this card on every animation frame.
    borderColorState: State<Color>? = null,
    contentPadding: PaddingValues = PaddingValues(Dimens.cardPadding),
    onClick: (() -> Unit)? = null,
    onClickLabel: String? = null,
    clickRole: Role? = Role.Button,
    stateDescription: String? = null,
    onToggle: ((Boolean) -> Unit)? = null,
    toggleValue: Boolean = false,
    contentDescription: String? = null,
    content: @Composable ColumnScope.() -> Unit,
) {
    val base = if (borderColorState != null) {
        modifier.godCardState(fill = containerColor, border = borderColorState)
    } else {
        modifier.godCard(fill = containerColor, border = borderColor)
    }
    val interaction = when {
        onToggle != null -> Modifier.toggleable(
            value = toggleValue,
            role = Role.Switch,
            onValueChange = onToggle,
        ).godTouchHeight()
        onClick != null -> Modifier.clickable(
            onClickLabel = onClickLabel,
            role = clickRole,
            onClick = onClick,
            // godTouchHeight here as well as on the toggleable branch above:
            // without it only toggleable cards were guaranteed a 48dp target,
            // and every plain clickable card fell back to whatever its content
            // happened to measure.
        ).godTouchHeight()
        else -> Modifier
    }
    val described = if (stateDescription == null && contentDescription == null) {
        Modifier
    } else {
        Modifier.semantics(mergeDescendants = true) {
            if (stateDescription != null) this.stateDescription = stateDescription
            if (contentDescription != null) this.contentDescription = contentDescription
        }
    }
    val tagged = if (testTag == null) Modifier else Modifier.testTag(testTag)
    val surface = base.then(interaction).then(described).fillMaxWidth().then(tagged)
    val hasHeader = title != null || trailing != null
    val start = contentPadding.calculateStartPadding(LayoutDirection.Ltr)
    val end = contentPadding.calculateEndPadding(LayoutDirection.Ltr)
    val top = contentPadding.calculateTopPadding()
    val bottom = contentPadding.calculateBottomPadding()
    Column(modifier = surface) {
        if (hasHeader) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(start = start, top = top, end = end)
                    .padding(bottom = if (bottom > Spacing.none) Spacing.xs else Spacing.none),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                if (title != null) title()
                if (trailing != null) trailing()
            }
        }
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(
                    start = start,
                    end = end,
                    top = if (hasHeader) Spacing.none else top,
                    bottom = bottom,
                ),
            content = content,
        )
    }
}
