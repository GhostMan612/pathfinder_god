// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.designsystem

import androidx.compose.foundation.layout.Box
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.layout.layout
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTag
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.LayoutDirection
import com.pathfindergod.spoke.ui.theme.TextSecondary

fun Modifier.godTouchHeight(min: Dp = Dimens.minTouchTarget): Modifier =
    enforceTouchTarget(min = min, growWidth = false)

fun Modifier.godTouchSize(min: Dp = Dimens.minTouchTarget): Modifier =
    enforceTouchTarget(min = min, growWidth = true)

private fun Modifier.enforceTouchTarget(min: Dp, growWidth: Boolean): Modifier =
    layout { measurable, constraints ->
        val placeable = measurable.measure(constraints)
        val target = min.roundToPx()
        val grownWidth = if (growWidth) maxOf(placeable.width, target) else placeable.width
        val grownHeight = maxOf(placeable.height, target)
        val width = if (constraints.hasBoundedWidth) {
            grownWidth.coerceAtMost(constraints.maxWidth)
        } else {
            grownWidth
        }
        val height = if (constraints.hasBoundedHeight) {
            grownHeight.coerceAtMost(constraints.maxHeight)
        } else {
            grownHeight
        }
        layout(width, height) {
            placeable.placeRelative(
                (width - placeable.width) / 2,
                (height - placeable.height) / 2,
            )
        }
    }

fun Modifier.godLiveRegion(
    assertive: Boolean = false,
    tag: String? = null,
): Modifier = semantics(mergeDescendants = true) {
    liveRegion = if (assertive) LiveRegionMode.Assertive else LiveRegionMode.Polite
    if (tag != null) testTag = tag
}

@Composable
fun Modifier.godMirrorInRtl(): Modifier {
    val rtl = LocalLayoutDirection.current == LayoutDirection.Rtl
    return graphicsLayer {
        if (rtl) scaleX = -1f
    }
}

@Composable
fun godRtlText(ltrRes: Int, rtlRes: Int): String = stringResource(
    if (LocalLayoutDirection.current == LayoutDirection.Ltr) ltrRes else rtlRes,
)

@Composable
fun GodLiveRegion(
    text: String,
    modifier: Modifier = Modifier,
    assertive: Boolean = false,
    tag: String? = null,
    style: TextStyle = MaterialTheme.typography.labelSmall,
    color: Color = TextSecondary,
) {
    Box(
        modifier = modifier.clearAndSetSemantics {
            liveRegion = if (assertive) LiveRegionMode.Assertive else LiveRegionMode.Polite
            this.contentDescription = text
            if (tag != null) this.testTag = tag
        },
    ) {
        Text(text = text, style = style, color = color)
    }
}