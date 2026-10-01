// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.a11y

import androidx.compose.material3.Text
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.test.assertHeightIsAtLeast
import androidx.compose.ui.test.assertWidthIsAtLeast
import androidx.compose.ui.test.junit4.createComposeRule
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
    val compose = createComposeRule()

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
    fun godChip_doesNotGrowHorizontallySoWideRowsStillFit() {
        compose.setContent {
            PathfinderGodTheme {
                GodChip(
                    label = "+3",
                    onClick = {},
                    testTag = TAG_CHIP,
                )
            }
        }
        val node = compose.onNodeWithTag(TAG_CHIP).fetchSemanticsNode()
        assertTrue(
            "chip must grow in height only, was ${node.size}",
            node.size.width < node.size.height,
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
                    modifier = Modifier
                        .godTouchSize()
                        .testTag(TAG_ICON),
                )
            }
        }
        compose.onNodeWithTag(TAG_ICON)
            .assertWidthIsAtLeast(Dimens.minTouchTarget)
            .assertHeightIsAtLeast(Dimens.minTouchTarget)
    }

    private companion object {
        const val TAG_CHIP = "test:a11y:chip"
        const val TAG_BUTTON = "test:a11y:button"
        const val TAG_BACK = "test:a11y:back"
        const val TAG_ICON = "test:a11y:icon"
    }
}
