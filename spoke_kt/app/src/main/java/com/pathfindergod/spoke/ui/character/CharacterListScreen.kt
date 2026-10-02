// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.character

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import com.pathfindergod.spoke.ui.motion.StaggerIn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.pathfindergod.spoke.R
import com.pathfindergod.spoke.data.local.AppDatabase
import com.pathfindergod.spoke.data.local.AppPreferences
import com.pathfindergod.spoke.data.local.CharacterEntity
import com.pathfindergod.spoke.data.network.HubApi
import com.pathfindergod.spoke.data.repository.CharacterRepository
import com.pathfindergod.spoke.ui.designsystem.Dimens
import com.pathfindergod.spoke.ui.designsystem.GodCard
import com.pathfindergod.spoke.ui.designsystem.GodEmptyState
import com.pathfindergod.spoke.ui.designsystem.GodTags
import com.pathfindergod.spoke.ui.designsystem.Spacing
import com.pathfindergod.spoke.ui.designsystem.godTouchSize
import com.pathfindergod.spoke.ui.theme.CritRed
import com.pathfindergod.spoke.ui.theme.TextPrimary
import com.pathfindergod.spoke.ui.theme.TextSecondary
import com.pathfindergod.spoke.ui.viewmodel.CharacterViewModel
import com.pathfindergod.spoke.data.network.HubApiFactory

private class CharacterVmFactory(
    private val repository: CharacterRepository,
) : ViewModelProvider.Factory {
    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>): T =
        CharacterViewModel(repository) as T
}

private fun buildHubApi(baseUrl: String): HubApi = HubApiFactory.get(baseUrl)

@Composable
internal fun rememberCharacterViewModel(): CharacterViewModel {
    val context = LocalContext.current
    val prefs = remember { AppPreferences(context) }
    val repository = remember {
        CharacterRepository(
            AppDatabase.get(context.applicationContext),
            buildHubApi(prefs.restUrl()),
        )
    }
    return viewModel(factory = remember { CharacterVmFactory(repository) })
}

@Composable
fun CharacterListScreen(
    viewModel: CharacterViewModel,
    onSelect: (Long) -> Unit,
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    AnimatedVisibility(
        visible = !state.isLoading,
        enter = fadeIn(),
        exit = fadeOut(),
    ) {
        if (state.characters.isEmpty()) {
            Box(
                modifier = Modifier.fillMaxSize(),
                contentAlignment = Alignment.Center,
            ) {
                GodEmptyState(text = stringResource(R.string.character_empty))
            }
        } else {
            LazyColumn(
                modifier = Modifier.fillMaxSize().padding(Spacing.lg),
                verticalArrangement = Arrangement.spacedBy(Dimens.gridSpacing),
            ) {
                itemsIndexed(
                    state.characters,
                    key = { _, character -> character.id },
                ) { index, character ->
                    StaggerIn(index = index, modifier = Modifier.animateItem()) {
                        CharacterCard(
                            character = character,
                            onSelect = { onSelect(character.id) },
                            onDelete = { viewModel.delete(character.id) },
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun CharacterCard(
    character: CharacterEntity,
    modifier: Modifier = Modifier,
    onSelect: () -> Unit,
    onDelete: () -> Unit,
) {
    GodCard(
        modifier = modifier.fillMaxWidth(),
        testTag = GodTags.hero(character.id),
        contentPadding = PaddingValues(start = Spacing.lg, end = Spacing.md, top = Spacing.md, bottom = Spacing.md),
        onClickLabel = stringResource(R.string.a11y_hero_open, character.name),
        contentDescription = stringResource(R.string.a11y_hero_card, character.name),
        onClick = onSelect,
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = character.name,
                    style = MaterialTheme.typography.titleLarge,
                    color = TextPrimary,
                )
                Text(
                    text = stringResource(
                        R.string.character_summary_pattern,
                        character.ancestry ?: stringResource(R.string.value_not_set),
                        character.characterClass ?: stringResource(R.string.value_not_set),
                        character.level,
                    ),
                    style = MaterialTheme.typography.bodyMedium,
                    color = TextSecondary,
                )
            }
            Text(
                text = stringResource(R.string.action_delete),
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold,
                color = CritRed,
                modifier = Modifier
                    // No contentDescription override: an empty string suppresses
                    // the child Text in the merged node, leaving the Delete
                    // control with a click action but no accessible name. The
                    // visible text is the label.
                    .clickable(
                        onClickLabel = stringResource(R.string.a11y_hero_delete, character.name),
                        role = Role.Button,
                    ) { onDelete() }
                    .godTouchSize()
                    .padding(Spacing.sm)
                    .testTag(GodTags.heroDelete(character.id)),
            )
        }
    }
}
