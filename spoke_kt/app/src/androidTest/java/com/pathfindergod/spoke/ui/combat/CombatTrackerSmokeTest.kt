// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.combat

import androidx.compose.ui.test.assertTextEquals
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performClick
import com.pathfindergod.spoke.a11y.ComposeTestActivity
import com.pathfindergod.spoke.data.combat.CombatSceneProducer
import com.pathfindergod.spoke.data.local.AppDatabase
import com.pathfindergod.spoke.data.network.HubApiFactory
import com.pathfindergod.spoke.data.network.TestHubUrl
import com.pathfindergod.spoke.data.repository.EncounterRepository
import com.pathfindergod.spoke.ui.designsystem.GodTags
import com.pathfindergod.spoke.ui.theme.PathfinderGodTheme
import com.pathfindergod.spoke.ui.viewmodel.CombatViewModel
import com.pathfindergod.spoke.ui.viewmodel.Combatant
import org.junit.Rule
import org.junit.Test

class CombatTrackerSmokeTest {

    @get:Rule
    val composeRule = createAndroidComposeRule<ComposeTestActivity>()

    @Test
    fun combatTrackerRendersAndAdvancesTurn() {
        val context = composeRule.activity
        val baseUrl = TestHubUrl.resolve(context)
        val repository = EncounterRepository(
            AppDatabase.get(context.applicationContext),
            HubApiFactory.get(baseUrl),
        )
        val producer = CombatSceneProducer(baseUrlProvider = { baseUrl })
        val viewModel = CombatViewModel(repository, producer)
        viewModel.addCombatant(
            Combatant(
                id = "hero-1",
                name = "Valeros",
                isPc = true,
                initiative = 18,
                currentHp = 20,
                maxHp = 20,
                ac = 18,
            ),
        )
        viewModel.addCombatant(
            Combatant(
                id = "goblin-1",
                name = "Goblin Commando",
                isPc = false,
                initiative = 12,
                currentHp = 15,
                maxHp = 15,
                ac = 16,
            ),
        )

        composeRule.setContent {
            PathfinderGodTheme {
                CombatTrackerScreen(viewModel = viewModel)
            }
        }

        composeRule.waitForIdle()
        composeRule.onNodeWithTag(GodTags.COMBAT_ROUND).assertExists()
        composeRule.onNodeWithTag(GodTags.COMBAT_SUMMON).assertExists()
        composeRule.onNodeWithTag(GodTags.COMBAT_ACTIVE).assertExists().assertTextEquals("Valeros")
        composeRule.onNodeWithTag(GodTags.COMBAT_END_TURN).assertExists().performClick()
        composeRule.waitForIdle()
        composeRule.onNodeWithTag(GodTags.COMBAT_ACTIVE).assertExists().assertTextEquals("Goblin Commando")
    }
}
