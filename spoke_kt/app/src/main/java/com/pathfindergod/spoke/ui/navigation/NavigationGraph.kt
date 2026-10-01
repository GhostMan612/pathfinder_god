// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.navigation

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation.NavBackStackEntry
import androidx.navigation.NavGraphBuilder
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.composable
import androidx.navigation.navArgument
import androidx.navigation.navDeepLink
import com.pathfindergod.spoke.ui.campaign.CampaignScreen
import com.pathfindergod.spoke.ui.campaign.rememberCampaignViewModel
import com.pathfindergod.spoke.ui.character.CharacterDetailScreen
import com.pathfindergod.spoke.ui.character.CharacterListScreen
import com.pathfindergod.spoke.ui.combat.CombatTrackerScreen
import com.pathfindergod.spoke.ui.designsystem.GodBackLink
import com.pathfindergod.spoke.ui.designsystem.GodEmptyState
import com.pathfindergod.spoke.ui.designsystem.GodTags
import com.pathfindergod.spoke.ui.designsystem.Spacing
import com.pathfindergod.spoke.ui.designsystem.godRtlText
import com.pathfindergod.spoke.ui.dice.DiceScreen
import com.pathfindergod.spoke.ui.dice.Die
import com.pathfindergod.spoke.ui.encounter.EncounterScreen
import com.pathfindergod.spoke.ui.home.HomeDashboardScreen
import com.pathfindergod.spoke.ui.loot.LootScreen
import com.pathfindergod.spoke.ui.loot.rememberLootViewModel
import com.pathfindergod.spoke.ui.map.MapListScreen
import com.pathfindergod.spoke.ui.map.MapViewerScreen
import com.pathfindergod.spoke.ui.rules.RuleSearchScreen
import com.pathfindergod.spoke.ui.settings.AudioCreditsScreen
import com.pathfindergod.spoke.ui.settings.SettingsScreen
import com.pathfindergod.spoke.ui.viewmodel.CharacterViewModel
import com.pathfindergod.spoke.ui.viewmodel.CombatViewModel
import com.pathfindergod.spoke.ui.viewmodel.EncounterViewModel
import com.pathfindergod.spoke.ui.viewmodel.MapViewModel
import com.pathfindergod.spoke.R
import androidx.compose.ui.res.stringResource

fun NavGraphBuilder.appNavGraph(
    navController: NavHostController,
    characters: CharacterViewModel,
    combat: CombatViewModel,
    encounters: EncounterViewModel,
    maps: MapViewModel,
) {
    composable(
        route = Destinations.Home.route,
        deepLinks = listOf(navDeepLink { uriPattern = Destinations.Home.deepLinkPattern }),
    ) {
        HomeDashboardScreen(
            characters = characters,
            combat = combat,
            encounters = encounters,
            maps = maps,
            onOpen = { navController.navigate(it.deepLink) },
            onQuickRoll = { die ->
                navController.navigate("${NavRoutes.DICE}?die=${die.name}")
            },
        )
    }

    composable(
        route = Destinations.Dice.route,
        arguments = listOf(
            navArgument(NavRoutes.ARG_DIE) {
                type = NavType.StringType
                nullable = true
                defaultValue = null
            },
        ),
        deepLinks = listOf(navDeepLink { uriPattern = Destinations.Dice.deepLinkPattern }),
    ) { entry ->
        DiceScreen(initialDie = entry.dieOrNull())
    }

    composable(
        route = Destinations.Combat.route,
        deepLinks = listOf(navDeepLink { uriPattern = Destinations.Combat.deepLinkPattern }),
    ) {
        CombatTrackerScreen(viewModel = combat)
    }

    composable(
        route = Destinations.Hero.route,
        deepLinks = listOf(navDeepLink { uriPattern = Destinations.Hero.deepLinkPattern }),
    ) {
        CharacterListScreen(
            viewModel = characters,
            onSelect = { id -> navController.navigate(NavRoutes.heroDetailRoute(id)) },
        )
    }

    composable(
        route = NavRoutes.HERO_DETAIL,
        arguments = listOf(
            navArgument(NavRoutes.ARG_CHARACTER_ID) { type = NavType.LongType },
        ),
        deepLinks = listOf(
            navDeepLink { uriPattern = Destinations.heroDetail.deepLinkPattern },
        ),
    ) { entry ->
        val characterId = entry.longArg(NavRoutes.ARG_CHARACTER_ID)
        val state by characters.state.collectAsStateWithLifecycle()
        LaunchedEffect(characterId) { characters.select(characterId) }
        val entity = state.characters.firstOrNull { it.id == characterId }
        if (entity == null) {
            VanishedHero(onBack = { navController.popBackStack() })
        } else {
            CharacterDetailScreen(
                entity = entity,
                onBack = { navController.popBackStack() },
            )
        }
    }

    composable(
        route = Destinations.Rules.route,
        deepLinks = listOf(navDeepLink { uriPattern = Destinations.Rules.deepLinkPattern }),
    ) {
        RuleSearchScreen()
    }

    composable(
        route = Destinations.Campaign.route,
        deepLinks = listOf(navDeepLink { uriPattern = Destinations.Campaign.deepLinkPattern }),
    ) {
        CampaignScreen(viewModel = rememberCampaignViewModel())
    }

    composable(
        route = Destinations.Map.route,
        deepLinks = listOf(navDeepLink { uriPattern = Destinations.Map.deepLinkPattern }),
    ) {
        MapListScreen(
            viewModel = maps,
            onSelect = { id -> navController.navigate(NavRoutes.mapViewerRoute(id)) },
        )
    }

    composable(
        route = NavRoutes.MAP_VIEWER,
        arguments = listOf(
            navArgument(NavRoutes.ARG_MAP_ID) { type = NavType.StringType },
        ),
        deepLinks = listOf(
            navDeepLink { uriPattern = Destinations.mapViewer.deepLinkPattern },
        ),
    ) { entry ->
        MapViewerScreen(
            mapId = entry.stringArg(NavRoutes.ARG_MAP_ID),
            viewModel = maps,
            onBack = { navController.popBackStack() },
        )
    }

    composable(
        route = Destinations.Encounter.route,
        deepLinks = listOf(navDeepLink { uriPattern = Destinations.Encounter.deepLinkPattern }),
    ) {
        EncounterScreen(viewModel = encounters)
    }

    composable(
        route = Destinations.God.route,
        deepLinks = listOf(navDeepLink { uriPattern = Destinations.God.deepLinkPattern }),
    ) {
        LootScreen(viewModel = rememberLootViewModel())
    }

    composable(
        route = Destinations.Setup.route,
        deepLinks = listOf(navDeepLink { uriPattern = Destinations.Setup.deepLinkPattern }),
    ) {
        SettingsScreen(onOpenCredits = { navController.navigate(NavRoutes.AUDIO_CREDITS) })
    }

    composable(
        route = Destinations.AudioCredits.route,
        deepLinks = listOf(
            navDeepLink { uriPattern = Destinations.AudioCredits.deepLinkPattern },
        ),
    ) {
        AudioCreditsScreen(onBack = { navController.popBackStack() })
    }
}

private fun NavBackStackEntry.longArg(name: String): Long =
    arguments?.getLong(name) ?: -1L

private fun NavBackStackEntry.stringArg(name: String): String =
    arguments?.getString(name).orEmpty()

private fun NavBackStackEntry.dieOrNull(): Die? {
    val raw = stringArg(NavRoutes.ARG_DIE)
    return Die.entries.firstOrNull { it.name == raw }
}

@Composable
private fun VanishedHero(onBack: () -> Unit) {
    Column(
        modifier = Modifier.fillMaxSize().padding(Spacing.lg),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        GodEmptyState(text = stringResource(R.string.hero_missing))
        GodBackLink(
            text = godRtlText(
                R.string.hero_missing_back,
                R.string.hero_missing_back_rtl,
            ),
            onClick = onBack,
            testTag = GodTags.heroBack,
            modifier = Modifier.padding(top = Spacing.md),
        )
    }
}