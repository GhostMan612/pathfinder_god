// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.a11y

import androidx.activity.ComponentActivity
import androidx.compose.material3.Text
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.test.SemanticsMatcher
import androidx.compose.ui.test.assertHeightIsAtLeast
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertWidthIsAtLeast
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.pathfindergod.spoke.ui.designsystem.Dimens
import com.pathfindergod.spoke.ui.designsystem.GodTags
import com.pathfindergod.spoke.ui.navigation.AppTopBar
import com.pathfindergod.spoke.ui.navigation.NavRoutes
import com.pathfindergod.spoke.ui.theme.PathfinderGodTheme
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test

class NavigationA11yTest {
    @get:Rule
    val compose = createAndroidComposeRule<ComponentActivity>()

    @Test
    fun topBarTitleIsALiveRegionSoScreenChangesAreAnnounced() {
        compose.setContent {
            PathfinderGodTheme {
                AppTopBar(
                    title = "Combat",
                    canNavigateUp = false,
                    onNavigateUp = {},
                    onHome = {},
                    onMore = {},
                )
            }
        }
        compose.onNodeWithTag(GodTags.TOP_BAR_TITLE)
            .assert(SemanticsMatcher.expectValue(SemanticsProperties.LiveRegion, LiveRegionMode.Polite))
    }

    @Test
    fun topBarTitleUpdatesWhenTheRouteChanges() {
        compose.setContent {
            PathfinderGodTheme {
                AppTopBar(
                    title = "Dice",
                    canNavigateUp = true,
                    onNavigateUp = {},
                    onHome = {},
                    onMore = {},
                )
            }
        }
        compose.onNodeWithTag(GodTags.TOP_BAR_TITLE).assertIsDisplayed()
    }

    @Test
    fun topBarActionsMeetTheFortyEightDpTouchMinimum() {
        compose.setContent {
            PathfinderGodTheme {
                AppTopBar(
                    title = "Roster",
                    canNavigateUp = true,
                    onNavigateUp = {},
                    onHome = {},
                    onMore = {},
                )
            }
        }
        compose.onNodeWithTag(GodTags.TOP_BAR_BACK)
            .assertWidthIsAtLeast(Dimens.minTouchTarget)
            .assertHeightIsAtLeast(Dimens.minTouchTarget)
        compose.onNodeWithTag(GodTags.TOP_BAR_MORE)
            .assertWidthIsAtLeast(Dimens.minTouchTarget)
            .assertHeightIsAtLeast(Dimens.minTouchTarget)
    }

    @Test
    fun systemBackPopsTheNavHostBackStack() {
        lateinit var controller: NavHostController
        compose.setContent {
            PathfinderGodTheme {
                controller = rememberNavController()
                NavHost(navController = controller, startDestination = NavRoutes.HOME) {
                    composable(NavRoutes.HOME) {
                        Text("home", modifier = Modifier.testTag(TAG_HOME))
                    }
                    composable(NavRoutes.DICE) {
                        Text("dice", modifier = Modifier.testTag(TAG_DICE))
                    }
                }
            }
        }
        compose.onNodeWithTag(TAG_HOME).assertIsDisplayed()

        compose.runOnUiThread { controller.navigate(NavRoutes.DICE) }
        compose.waitForIdle()
        compose.onNodeWithTag(TAG_DICE).assertIsDisplayed()

        compose.activityRule.scenario.onActivity { activity ->
            activity.onBackPressedDispatcher.onBackPressed()
        }
        compose.waitForIdle()

        compose.onNodeWithTag(TAG_HOME).assertIsDisplayed()
        assertEquals(NavRoutes.HOME, controller.currentDestination?.route)
    }

    @Test
    fun navTabTagsFollowTheConvention() {
        assertEquals("pg:nav:tab:dice", GodTags.navTab("dice"))
        assertEquals("pg:nav:tab:combat", GodTags.navTab("combat"))
        assertEquals("pg:nav:tab:hero", GodTags.navTab("hero"))
        assertEquals("pg:nav:tab:rules", GodTags.navTab("rules"))
    }

    @Test
    fun topBarTagsAreUnique() {
        val tags = listOf(
            GodTags.TOP_BAR_TITLE,
            GodTags.TOP_BAR_BACK,
            GodTags.TOP_BAR_MORE,
        )
        assertEquals(tags.size, tags.toSet().size)
    }

    private companion object {
        const val TAG_HOME = "test:nav:home"
        const val TAG_DICE = "test:nav:dice"
    }
}
