// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.navigation

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.pathfindergod.spoke.ui.character.CharacterDetailScreen
import com.pathfindergod.spoke.ui.character.CharacterDetailScreen
import com.pathfindergod.spoke.ui.character.CharacterListScreen
import com.pathfindergod.spoke.ui.character.rememberCharacterViewModel
import com.pathfindergod.spoke.ui.combat.CombatTrackerScreen
import com.pathfindergod.spoke.ui.dice.DiceScreen
import com.pathfindergod.spoke.ui.map.MapListScreen
import com.pathfindergod.spoke.ui.map.MapViewerScreen
import com.pathfindergod.spoke.ui.map.rememberMapViewModel
import com.pathfindergod.spoke.ui.settings.SettingsScreen
import com.pathfindergod.spoke.ui.theme.GoldAccent
import com.pathfindergod.spoke.ui.theme.TextPrimary
import com.pathfindergod.spoke.ui.theme.TextSecondary
import com.pathfindergod.spoke.ui.theme.VoidBackground
import com.pathfindergod.spoke.ui.theme.rpgPanel

@Composable
fun NavigationShell() {
    var selected by rememberSaveable { mutableIntStateOf(0) }
    var detailId by rememberSaveable { mutableLongStateOf(-1L) }
    var mapId by rememberSaveable { mutableStateOf<String?>(null) }
    val items = NavigationItem.entries
    Scaffold(
        containerColor = VoidBackground,
        bottomBar = {
            NavigationBar(containerColor = VoidBackground) {
                items.forEachIndexed { index, item ->
                    NavigationBarItem(
                        selected = index == selected,
                        onClick = {
                            if (index == selected && items[index] == NavigationItem.HERO) {
                                detailId = -1L
                            }
                            if (index == selected && items[index] == NavigationItem.MAP) {
                                mapId = null
                            }
                            selected = index
                        },
                        icon = { Icon(imageVector = item.icon, contentDescription = item.label) },
                        label = { Text(text = item.label) },
                        colors = NavigationBarItemDefaults.colors(
                            selectedIconColor = VoidBackground,
                            selectedTextColor = GoldAccent,
                            indicatorColor = GoldAccent,
                            unselectedIconColor = TextSecondary,
                            unselectedTextColor = TextSecondary,
                        ),
                    )
                }
            }
        },
    ) { padding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(VoidBackground)
                .padding(padding),
        ) {
            when (items[selected]) {
                NavigationItem.DICE -> DiceScreen()
                NavigationItem.COMBAT -> CombatTrackerScreen()
                NavigationItem.MAP -> {
                    val mapVm = rememberMapViewModel()
                    val mapState by mapVm.state.collectAsStateWithLifecycle()
                    val selected = mapState.maps.firstOrNull { it.id == mapId }
                    if (mapId == null || selected == null) {
                        MapListScreen(
                            viewModel = mapVm,
                            onSelect = { mapId = it },
                        )
                    } else {
                        MapViewerScreen(
                            mapId = selected.id,
                            viewModel = mapVm,
                            onBack = { mapId = null },
                        )
                    }
                }
                NavigationItem.SETUP -> SettingsScreen()
                NavigationItem.HERO -> {
                    val heroVm = rememberCharacterViewModel()
                    val heroState by heroVm.state.collectAsStateWithLifecycle()
                    val detail = heroState.characters.firstOrNull { it.id == detailId }
                    if (detailId < 0 || detail == null) {
                        CharacterListScreen(
                            viewModel = heroVm,
                            onSelect = {
                                heroVm.select(it)
                                detailId = it
                            },
                        )
                    } else {
                        CharacterDetailScreen(
                            entity = detail,
                            onBack = {
                                heroVm.select(null)
                                detailId = -1L
                            },
                        )
                    }
                }
                else -> PlaceholderScreen(label = items[selected].label)
            }
        }
    }
}

@Composable
fun PlaceholderScreen(label: String) {
    Box(
        modifier = Modifier.fillMaxSize(),
        contentAlignment = Alignment.Center,
    ) {
        Box(modifier = Modifier.rpgPanel().padding(horizontal = 32.dp, vertical = 20.dp)) {
            Text(
                text = label,
                style = MaterialTheme.typography.headlineSmall,
                color = TextPrimary,
            )
        }
    }
}
