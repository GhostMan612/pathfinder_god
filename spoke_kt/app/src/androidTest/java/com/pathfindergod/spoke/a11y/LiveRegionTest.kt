// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.a11y

import androidx.compose.foundation.clickable
import androidx.compose.material3.Text
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.SemanticsConfiguration
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.semantics.SemanticsProperties.ContentDescription
import androidx.compose.ui.semantics.SemanticsPropertyKey
import androidx.compose.ui.test.SemanticsMatcher
import androidx.compose.ui.test.assert
import androidx.compose.ui.test.hasContentDescriptionExactly
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performClick
import com.pathfindergod.spoke.ui.designsystem.GodLiveRegion
import com.pathfindergod.spoke.ui.designsystem.godLiveRegion
import com.pathfindergod.spoke.ui.theme.PathfinderGodTheme
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNotNull
import org.junit.Rule
import org.junit.Test

class LiveRegionTest {
    @get:Rule
    val compose = createComposeRule()

    @Test
    fun godLiveRegion_isPoliteByDefault() {
        compose.setContent {
            PathfinderGodTheme {
                GodLiveRegion(text = "12 of 20 hit points", tag = TAG)
            }
        }
        compose.onNodeWithTag(TAG).assert(
            SemanticsMatcher.expectValue(SemanticsProperties.LiveRegion, LiveRegionMode.Polite),
        )
    }

    @Test
    fun godLiveRegion_canBeAssertiveForCrits() {
        compose.setContent {
            PathfinderGodTheme {
                GodLiveRegion(
                    text = "d20 equals 20. Critical success!",
                    assertive = true,
                    tag = TAG,
                )
            }
        }
        compose.onNodeWithTag(TAG).assert(
            SemanticsMatcher.expectValue(SemanticsProperties.LiveRegion, LiveRegionMode.Assertive),
        )
    }

    @Test
    fun godLiveRegion_publishesItsTextAsAContentDescription() {
        compose.setContent {
            PathfinderGodTheme {
                GodLiveRegion(text = "Kira takes 5 damage.", tag = TAG)
            }
        }
        compose.onNodeWithTag(TAG)
            .assert(hasContentDescriptionExactly("Kira takes 5 damage."))
    }

    @Test
    fun godLiveRegion_republishesWhenTheAnnouncementChanges() {
        compose.setContent {
            PathfinderGodTheme {
                var hp by remember { mutableStateOf(20) }
                GodLiveRegion(text = "Hit points now $hp of 20", tag = TAG)
                Text(
                    text = "apply five damage",
                    modifier = Modifier
                        .clickable { hp = 15 }
                        .testTag(TRIGGER),
                )
            }
        }
        val before = compose.onNodeWithTag(TAG).fetchSemanticsNode()
            .config.valueOrNull(ContentDescription)
        assertNotNull(before)

        compose.onNodeWithTag(TRIGGER).performClick()
        compose.waitForIdle()

        val after = compose.onNodeWithTag(TAG).fetchSemanticsNode()
            .config.valueOrNull(ContentDescription)
        assertNotNull(after)
        assertNotEquals(before, after)
    }

    @Test
    fun godLiveRegion_modifierMarksAGroupAsPolite() {
        compose.setContent {
            PathfinderGodTheme {
                Text(
                    text = "Round 2. Kira acts.",
                    modifier = Modifier
                        .godLiveRegion()
                        .testTag(TAG),
                )
            }
        }
        compose.onNodeWithTag(TAG).assert(
            SemanticsMatcher.expectValue(SemanticsProperties.LiveRegion, LiveRegionMode.Polite),
        )
    }

    @Test
    fun godLiveRegion_assertiveModifierIsWiredThrough() {
        compose.setContent {
            PathfinderGodTheme {
                Text(
                    text = "Encounter mustered. 4 foes, target 900 XP.",
                    modifier = Modifier
                        .godLiveRegion(assertive = true)
                        .testTag(TAG),
                )
            }
        }
        compose.onNodeWithTag(TAG).assert(
            SemanticsMatcher.expectValue(SemanticsProperties.LiveRegion, LiveRegionMode.Assertive),
        )
    }

    @Test
    fun liveRegionKeyIsExposedOnTheMergedNode() {
        compose.setContent {
            PathfinderGodTheme {
                GodLiveRegion(text = "d20 equals 17.", tag = TAG)
            }
        }
        compose.onNodeWithTag(TAG)
            .assert(SemanticsMatcher.keyIsDefined(SemanticsProperties.LiveRegion))
    }

    private companion object {
        const val TAG = "test:a11y:live"
        const val TRIGGER = "test:a11y:live:trigger"
    }
}

/**
 * This Compose version exposes SemanticsConfiguration.get / getOrElseNullable / contains;
 * there is no getOrNull. Returns the stored value, or null when the key is absent, so a
 * test can distinguish "not set" from "set to a default".
 */
private fun <T> SemanticsConfiguration.valueOrNull(key: SemanticsPropertyKey<T>): T? =
    if (contains(key)) get(key) else null
