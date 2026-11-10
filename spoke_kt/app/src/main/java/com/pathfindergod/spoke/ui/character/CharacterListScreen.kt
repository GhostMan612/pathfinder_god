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
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
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
import com.pathfindergod.spoke.data.network.HubApiFactory
import com.pathfindergod.spoke.data.repository.CharacterRepository
import com.pathfindergod.spoke.ui.designsystem.Dimens
import com.pathfindergod.spoke.ui.designsystem.GodCard
import com.pathfindergod.spoke.ui.designsystem.GodEmptyState
import com.pathfindergod.spoke.ui.designsystem.GodFab
import com.pathfindergod.spoke.ui.designsystem.GodStatusText
import com.pathfindergod.spoke.ui.designsystem.GodTags
import com.pathfindergod.spoke.ui.designsystem.GodTextField
import com.pathfindergod.spoke.ui.designsystem.GodTone
import com.pathfindergod.spoke.ui.designsystem.Spacing
import com.pathfindergod.spoke.ui.designsystem.godTouchHeight
import com.pathfindergod.spoke.ui.designsystem.godTouchSize
import com.pathfindergod.spoke.ui.motion.StaggerIn
import com.pathfindergod.spoke.ui.strings.UiText
import com.pathfindergod.spoke.ui.strings.resolve
import com.pathfindergod.spoke.ui.theme.CritRed
import com.pathfindergod.spoke.ui.theme.GoldAccent
import com.pathfindergod.spoke.ui.theme.TextPrimary
import com.pathfindergod.spoke.ui.theme.TextSecondary
import com.pathfindergod.spoke.ui.viewmodel.CharacterViewModel

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
    var showForge by rememberSaveable { mutableStateOf(false) }

    LaunchedEffect(showForge) {
        if (showForge) viewModel.clearForgeError()
    }
    LaunchedEffect(state.lastForgedId) {
        val id = state.lastForgedId ?: return@LaunchedEffect
        showForge = false
        viewModel.consumeForged()
        onSelect(id)
    }

    Box(modifier = Modifier.fillMaxSize()) {
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
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(
                        start = Spacing.lg,
                        end = Spacing.lg,
                        top = Spacing.lg,
                        bottom = 96.dp,
                    ),
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
        GodFab(
            icon = Icons.Filled.Add,
            contentDescription = stringResource(R.string.a11y_character_forge),
            onClick = { showForge = true },
            testTag = GodTags.HERO_FORGE_FAB,
            modifier = Modifier
                .align(Alignment.BottomEnd)
                .padding(Spacing.xl),
        )
    }

    if (showForge) {
        ForgeHeroDialog(
            isForging = state.isForging,
            error = state.error,
            onDismiss = { showForge = false },
            onForge = viewModel::forge,
        )
    }
}

@Composable
private fun ForgeHeroDialog(
    isForging: Boolean,
    error: UiText?,
    onDismiss: () -> Unit,
    onForge: (String) -> Unit,
) {
    var prompt by rememberSaveable { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = { if (!isForging) onDismiss() },
        title = {
            Text(
                text = stringResource(R.string.character_forge_title),
                style = MaterialTheme.typography.titleMedium,
                color = GoldAccent,
            )
        },
        text = {
            Column {
                GodTextField(
                    value = prompt,
                    onValueChange = { prompt = it },
                    label = stringResource(R.string.character_forge_prompt_label),
                    placeholder = stringResource(R.string.character_forge_prompt_hint),
                    singleLine = false,
                    modifier = Modifier.fillMaxWidth().testTag(GodTags.HERO_FORGE_PROMPT),
                )
                if (isForging) {
                    GodStatusText(
                        text = stringResource(R.string.character_forge_working),
                        modifier = Modifier.padding(top = Spacing.md),
                    )
                }
                error?.let {
                    GodStatusText(
                        text = it.resolve(),
                        tone = GodTone.Critical,
                        color = CritRed,
                        modifier = Modifier.padding(top = Spacing.md),
                    )
                }
            }
        },
        confirmButton = {
            val enabled = !isForging && prompt.isNotBlank()
            Text(
                text = stringResource(R.string.character_forge_action),
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
                color = if (enabled) GoldAccent else TextSecondary,
                modifier = Modifier
                    .testTag(GodTags.HERO_FORGE_SUBMIT)
                    .clickable(
                        enabled = enabled,
                        onClickLabel = stringResource(R.string.a11y_character_forge_submit),
                        role = Role.Button,
                    ) { onForge(prompt) }
                    .godTouchHeight()
                    .padding(Spacing.sm),
            )
        },
        dismissButton = {
            Text(
                text = stringResource(R.string.character_forge_cancel),
                style = MaterialTheme.typography.titleMedium,
                color = if (isForging) TextSecondary else TextPrimary,
                modifier = Modifier
                    .testTag(GodTags.HERO_FORGE_CANCEL)
                    .clickable(
                        enabled = !isForging,
                        onClickLabel = stringResource(R.string.a11y_character_forge_cancel),
                        role = Role.Button,
                        onClick = onDismiss,
                    )
                    .godTouchHeight()
                    .padding(Spacing.sm),
            )
        },
    )
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
                    .testTag(GodTags.heroDelete(character.id))
                    .clickable(
                        onClickLabel = stringResource(R.string.a11y_hero_delete, character.name),
                        role = Role.Button,
                    ) { onDelete() }
                    .godTouchSize()
                    .padding(Spacing.sm),
            )
        }
    }
}
