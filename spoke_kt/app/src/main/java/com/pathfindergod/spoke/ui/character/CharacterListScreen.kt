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
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import com.pathfindergod.spoke.ui.motion.StaggerIn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.pathfindergod.spoke.data.local.AppDatabase
import com.pathfindergod.spoke.data.local.CharacterEntity
import com.pathfindergod.spoke.data.local.NetworkPreferences
import com.pathfindergod.spoke.data.network.HubApi
import com.pathfindergod.spoke.data.repository.CharacterRepository
import com.pathfindergod.spoke.ui.theme.CritRed
import com.pathfindergod.spoke.ui.theme.GodTypography
import com.pathfindergod.spoke.ui.theme.TextPrimary
import com.pathfindergod.spoke.ui.theme.TextSecondary
import com.pathfindergod.spoke.ui.theme.rpgPanel
import com.pathfindergod.spoke.ui.viewmodel.CharacterViewModel
import com.pathfindergod.spoke.data.network.HubApiFactory

private class CharacterVmFactory(
    private val repository: CharacterRepository,
) : ViewModelProvider.Factory {
    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>): T =
        CharacterViewModel(repository) as T
}

private fun buildHubApi(baseUrl: String): HubApi = HubApiFactory.create(baseUrl)

@Composable
internal fun rememberCharacterViewModel(): CharacterViewModel {
    val context = LocalContext.current
    val prefs = remember { NetworkPreferences(context) }
    val repository = remember {
        CharacterRepository(
            AppDatabase.create(context.applicationContext),
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
                Text(
                    text = "No heroes yet — forge one with the God.",
                    style = GodTypography.titleMedium,
                    color = TextSecondary,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.padding(horizontal = 32.dp),
                )
            }
        } else {
            LazyColumn(
                modifier = Modifier.fillMaxSize().padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
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
    Row(
        modifier = modifier
            .rpgPanel()
            .clickable { onSelect() }
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = character.name,
                style = GodTypography.titleLarge,
                color = TextPrimary,
            )
            Text(
                text = "${character.ancestry ?: "—"} · ${character.characterClass ?: "—"} · Level ${character.level}",
                style = GodTypography.bodyMedium,
                color = TextSecondary,
            )
        }
        Text(
            text = "✕",
            style = GodTypography.titleLarge,
            fontWeight = FontWeight.Bold,
            color = CritRed,
            modifier = Modifier.clickable { onDelete() }.padding(8.dp),
        )
    }
}
