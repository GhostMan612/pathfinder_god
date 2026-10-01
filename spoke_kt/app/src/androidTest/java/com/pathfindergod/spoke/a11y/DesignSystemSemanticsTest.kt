// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.a11y

import androidx.compose.material3.Text
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.SemanticsConfiguration
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.semantics.SemanticsProperties.StateDescription
import androidx.compose.ui.semantics.SemanticsPropertyKey
import androidx.compose.ui.test.SemanticsMatcher
import androidx.compose.ui.test.assert
import androidx.compose.ui.test.assertHasClickAction
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performClick
import com.pathfindergod.spoke.ui.designsystem.GodCard
import com.pathfindergod.spoke.ui.designsystem.GodChip
import com.pathfindergod.spoke.ui.designsystem.GodProgressBar
import com.pathfindergod.spoke.ui.designsystem.Spacing
import com.pathfindergod.spoke.ui.theme.PathfinderGodTheme
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test

class DesignSystemSemanticsTest {
    @get:Rule
    val compose = createComposeRule()

    @Test
    fun godChip_exposesRadioButtonRole() {
        compose.setContent {
            PathfinderGodTheme {
                GodChip(label = "d20", onClick = {}, testTag = TAG)
            }
        }
        compose.onNodeWithTag(TAG)
            .assert(SemanticsMatcher.expectValue(SemanticsProperties.Role, Role.RadioButton))
    }

    @Test
    fun godChip_announcesSelectedState() {
        compose.setContent {
            PathfinderGodTheme {
                GodChip(
                    label = "d20",
                    selected = true,
                    onClick = {},
                    testTag = TAG,
                )
            }
        }
        val state = compose.onNodeWithTag(TAG).fetchSemanticsNode()
            .config.valueOrNull(StateDescription)
        // StateDescription is a SemanticsPropertyKey<String>, not a list.
        assertEquals("Selected", state)
    }

    @Test
    fun godChip_announcesNotSelectedState() {
        compose.setContent {
            PathfinderGodTheme {
                GodChip(
                    label = "d12",
                    selected = false,
                    onClick = {},
                    testTag = TAG,
                )
            }
        }
        val state = compose.onNodeWithTag(TAG).fetchSemanticsNode()
            .config.valueOrNull(StateDescription)
        assertEquals("Not selected", state)
    }

    @Test
    fun godChip_disabledChipIsAnnouncedAsDisabled() {
        compose.setContent {
            PathfinderGodTheme {
                GodChip(
                    label = "Advantage",
                    enabled = false,
                    onClick = {},
                    testTag = TAG,
                )
            }
        }
        compose.onNodeWithTag(TAG)
            .assert(SemanticsMatcher.keyIsDefined(SemanticsProperties.Disabled))
    }

    @Test
    fun godCard_withOnClick_isAButtonWithAClickAction() {
        compose.setContent {
            PathfinderGodTheme {
                GodCard(onClick = {}, testTag = TAG) {
                    Text("Rule")
                }
            }
        }
        compose.onNodeWithTag(TAG)
            .assert(SemanticsMatcher.expectValue(SemanticsProperties.Role, Role.Button))
            .assertHasClickAction()
    }

    @Test
    fun expandableGodCard_reportsCollapsedThenExpanded() {
        compose.setContent {
            PathfinderGodTheme {
                var expanded by remember { mutableStateOf(false) }
                GodCard(
                    onClick = { expanded = !expanded },
                    onClickLabel = if (expanded) "Collapse" else "Expand",
                    stateDescription = if (expanded) "Expanded" else "Collapsed",
                    testTag = TAG,
                ) {
                    Text("Blink")
                }
            }
        }
        var state = compose.onNodeWithTag(TAG).fetchSemanticsNode()
            .config.valueOrNull(StateDescription)
        assertEquals("Collapsed", state)

        compose.onNodeWithTag(TAG).performClick()
        compose.waitForIdle()

        state = compose.onNodeWithTag(TAG).fetchSemanticsNode()
            .config.valueOrNull(StateDescription)
        assertEquals("Expanded", state)
    }

    @Test
    fun godProgressBar_exposesProgressBarRangeInfo() {
        compose.setContent {
            PathfinderGodTheme {
                GodProgressBar(fraction = 0.4f, label = "Hit points", testTag = TAG)
            }
        }
        compose.onNodeWithTag(TAG)
            .assert(SemanticsMatcher.keyIsDefined(SemanticsProperties.ProgressBarRangeInfo))
    }

    @Test
    fun actionChip_doesNotAnnounceAbleSelectionState() {
        compose.setContent {
            PathfinderGodTheme {
                GodChip(
                    label = "CLEAR",
                    onClick = {},
                    role = Role.Button,
                    selectedStateRes = null,
                    onClickLabel = "Clear roll history",
                    testTag = TAG,
                )
            }
        }
        val node = compose.onNodeWithTag(TAG).fetchSemanticsNode()
        assertTrue(!node.config.contains(StateDescription))
    }

    @Test
    fun godChip_clickInvokesTheHandler() {
        var taps = 0
        compose.setContent {
            PathfinderGodTheme {
                GodChip(
                    label = "d8",
                    onClick = { taps++ },
                    horizontalPadding = Spacing.sm,
                    testTag = TAG,
                )
            }
        }
        compose.onNodeWithTag(TAG).performClick()
        compose.waitForIdle()
        assertEquals(1, taps)
    }

    private companion object {
        const val TAG = "test:a11y:semantics"
    }
}

/**
 * This Compose version exposes SemanticsConfiguration.get / getOrElseNullable / contains;
 * there is no getOrNull. Returns the stored value, or null when the key is absent, so a
 * test can distinguish "not set" from "set to a default".
 */
private fun <T> SemanticsConfiguration.valueOrNull(key: SemanticsPropertyKey<T>): T? =
    if (contains(key)) get(key) else null
