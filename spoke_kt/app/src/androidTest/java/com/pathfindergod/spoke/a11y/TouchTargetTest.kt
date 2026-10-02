// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.a11y

import androidx.compose.foundation.layout.Column
import androidx.compose.material3.Text
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.test.assertHeightIsAtLeast
import androidx.compose.ui.test.assertWidthIsAtLeast
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.unit.dp
import com.pathfindergod.spoke.ui.designsystem.Dimens
import com.pathfindergod.spoke.ui.designsystem.GodBackLink
import com.pathfindergod.spoke.ui.designsystem.GodChip
import com.pathfindergod.spoke.ui.designsystem.GodPrimaryButton
import com.pathfindergod.spoke.ui.designsystem.Spacing
import com.pathfindergod.spoke.ui.designsystem.godTouchSize
import com.pathfindergod.spoke.ui.theme.PathfinderGodTheme
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test

class TouchTargetTest {
    @get:Rule
    val compose = createAndroidComposeRule<ComposeTestActivity>()

    @Test
    fun minimumTouchTargetIsFortyEightDp() {
        assertEquals(48.dp, Dimens.minTouchTarget)
    }

    @Test
    fun godChip_meetsTouchHeightWithZeroPadding() {
        compose.setContent {
            PathfinderGodTheme {
                GodChip(
                    label = "1",
                    onClick = {},
                    horizontalPadding = Spacing.none,
                    verticalPadding = Spacing.none,
                    testTag = TAG_CHIP,
                )
            }
        }
        compose.onNodeWithTag(TAG_CHIP).assertHeightIsAtLeast(Dimens.minTouchTarget)
    }

    @Test
    fun godChip_meetsTouchHeightWithDefaultPadding() {
        compose.setContent {
            PathfinderGodTheme {
                GodChip(
                    label = "d20",
                    onClick = {},
                    testTag = TAG_CHIP,
                )
            }
        }
        compose.onNodeWithTag(TAG_CHIP).assertHeightIsAtLeast(Dimens.minTouchTarget)
    }

    @Test
    fun godChip_enforcesHeightButNeverGrowsWidthSoWideRowsStillFit() {
        compose.setContent {
            PathfinderGodTheme {
                Column {
                    GodChip(
                        label = "d20",
                        onClick = {},
                        horizontalPadding = Spacing.none,
                        testTag = TAG_CHIP_NARROW,
                    )
                    GodChip(
                        label = "d20",
                        onClick = {},
                        testTag = TAG_CHIP_PADDED,
                    )
                }
            }
        }
        val minPx = with(compose.density) { Dimens.minTouchTarget.roundToPx() }
        val narrow = compose.onNodeWithTag(TAG_CHIP_NARROW).fetchSemanticsNode().size
        val padded = compose.onNodeWithTag(TAG_CHIP_PADDED).fetchSemanticsNode().size

        // Height is forced up to the 48dp minimum even with no vertical padding...
        assertTrue(
            "chip height must be at least the 48dp minimum, was ${narrow.height}px (min $minPx)",
            narrow.height >= minPx,
        )
        // ...but width is left entirely to the content, which is the whole point of
        // godTouchHeight over godTouchSize: a row of chips must not each be forced 48dp wide.
        assertTrue(
            "chip width must not be grown to the touch minimum, was ${narrow.width}px (min $minPx)",
            narrow.width < minPx,
        )
        // And padding still widens the chip, proving the width above is content-driven and
        // not simply stuck at the minimum.
        assertTrue(
            "padding should widen the chip, was ${narrow.width}px narrow vs ${padded.width}px padded",
            padded.width > narrow.width,
        )
    }

    @Test
    fun godPrimaryButton_meetsTouchHeightWithNoVerticalPadding() {
        compose.setContent {
            PathfinderGodTheme {
                GodPrimaryButton(
                    text = "ROLL",
                    onClick = {},
                    verticalPadding = 0.dp,
                    testTag = TAG_BUTTON,
                )
            }
        }
        compose.onNodeWithTag(TAG_BUTTON).assertHeightIsAtLeast(Dimens.minTouchTarget)
    }

    @Test
    fun godBackLink_meetsTouchHeight() {
        compose.setContent {
            PathfinderGodTheme {
                GodBackLink(
                    text = "Roster",
                    onClick = {},
                    testTag = TAG_BACK,
                )
            }
        }
        compose.onNodeWithTag(TAG_BACK).assertHeightIsAtLeast(Dimens.minTouchTarget)
    }

    @Test
    fun godTouchSize_growsBothAxesToTheMinimum() {
        compose.setContent {
            PathfinderGodTheme {
                Text(
                    text = "x",
                    // testTag before godTouchSize, i.e. outermost. Modifier.layout opens a
                    // new LayoutNode, so a tag applied after it lands on the inner node and
                    // reports the raw glyph bounds - which measured 10dp, not 48dp.
                    modifier = Modifier
                        .testTag(TAG_ICON)
                        .godTouchSize(),
                )
            }
        }
        compose.onNodeWithTag(TAG_ICON)
            .assertWidthIsAtLeast(Dimens.minTouchTarget)
            .assertHeightIsAtLeast(Dimens.minTouchTarget)
    }

    private companion object {
        const val TAG_CHIP = "test:a11y:chip"
        const val TAG_CHIP_NARROW = "test:a11y:chip:narrow"
        const val TAG_CHIP_PADDED = "test:a11y:chip:padded"
        const val TAG_BUTTON = "test:a11y:button"
        const val TAG_BACK = "test:a11y:back"
        const val TAG_ICON = "test:a11y:icon"
    }
}
