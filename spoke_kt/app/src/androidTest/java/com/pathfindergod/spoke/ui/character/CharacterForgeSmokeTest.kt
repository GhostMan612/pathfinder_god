// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.character

import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performTextInput
import com.pathfindergod.spoke.R
import com.pathfindergod.spoke.a11y.ComposeTestActivity
import com.pathfindergod.spoke.data.local.AppDatabase
import com.pathfindergod.spoke.data.network.HubApiFactory
import com.pathfindergod.spoke.data.repository.CharacterRepository
import com.pathfindergod.spoke.data.local.AppPreferences
import com.pathfindergod.spoke.ui.designsystem.GodTags
import com.pathfindergod.spoke.ui.viewmodel.CharacterViewModel
import org.junit.Rule
import org.junit.Test

class CharacterForgeSmokeTest {

    @get:Rule
    val composeRule = createAndroidComposeRule<ComposeTestActivity>()

    @Test
    fun fabOpensTheForgeAndCancelClosesIt() {
        val context = composeRule.activity
        val repository = CharacterRepository(
            AppDatabase.get(context.applicationContext),
            HubApiFactory.get(AppPreferences(context).restUrl()),
        )
        val viewModel = CharacterViewModel(repository)
        composeRule.setContent {
            CharacterListScreen(viewModel = viewModel, onSelect = {})
        }
        composeRule.waitForIdle()

        composeRule.onNodeWithTag(GodTags.HERO_FORGE_FAB).performClick()
        composeRule.onNodeWithText(context.getString(R.string.character_forge_title)).assertExists()
        composeRule.onNodeWithTag(GodTags.HERO_FORGE_PROMPT)
            .performTextInput("a dwarven champion of Torag")
        composeRule.onNodeWithTag(GodTags.HERO_FORGE_SUBMIT).assertExists()
        composeRule.onNodeWithTag(GodTags.HERO_FORGE_CANCEL).performClick()
        composeRule.onNodeWithText(context.getString(R.string.character_forge_title))
            .assertDoesNotExist()
    }
}
