// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.navigation

import androidx.compose.animation.core.spring
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.consumeWindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.adaptive.navigationsuite.NavigationSuiteDefaults
import androidx.compose.material3.adaptive.navigationsuite.NavigationSuiteScaffold
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.LayoutDirection
import androidx.navigation.NavHostController
import androidx.navigation.NavOptions
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.pathfindergod.spoke.service.AudioService
import com.pathfindergod.spoke.ui.character.rememberCharacterViewModel
import com.pathfindergod.spoke.ui.combat.rememberCombatViewModel
import com.pathfindergod.spoke.ui.designsystem.GodTags
import com.pathfindergod.spoke.ui.encounter.rememberEncounterViewModel
import com.pathfindergod.spoke.ui.home.MoreSheet
import com.pathfindergod.spoke.ui.map.rememberMapViewModel
import com.pathfindergod.spoke.ui.theme.GoldAccent
import com.pathfindergod.spoke.ui.theme.TextSecondary
import com.pathfindergod.spoke.ui.theme.VoidBackground

@Composable
fun NavigationShell() {
    val navController = rememberNavController()
    val context = LocalContext.current
    val audio = remember(context) { AudioService.get(context) }
    val characters = rememberCharacterViewModel()
    val combat = rememberCombatViewModel()
    val encounters = rememberEncounterViewModel()
    val maps = rememberMapViewModel()
    val backStackEntry by navController.currentBackStackEntryAsState()
    val currentRoute = backStackEntry?.destination?.route
    val canNavigateUp = backStackEntry != null && navController.previousBackStackEntry != null
    var moreOpen by rememberSaveable { mutableStateOf(false) }
    var lastBarRoute by remember { mutableStateOf<String?>(null) }
    val forwardSign = if (LocalLayoutDirection.current == LayoutDirection.Ltr) 1 else -1

    DisposableEffect(Unit) {
        audio.warmUp()
        audio.syncMusic()
        onDispose { audio.release() }
    }

    LaunchedEffect(currentRoute) {
        audio.syncMusic()
        val bar = NavigationItem.entries.firstOrNull { it.matches(currentRoute) }
        if (bar != null && bar.destination.route != lastBarRoute) {
            audio.tabChange()
            lastBarRoute = bar.destination.route
        }
    }

    val suiteColors = NavigationSuiteDefaults.colors(
        navigationBarContainerColor = VoidBackground,
        navigationRailContainerColor = VoidBackground,
    )
    val itemColors = NavigationSuiteDefaults.itemColors(
        navigationBarItemColors = NavigationBarItemDefaults.colors(
            selectedIconColor = VoidBackground,
            selectedTextColor = GoldAccent,
            indicatorColor = GoldAccent,
            unselectedIconColor = TextSecondary,
            unselectedTextColor = TextSecondary,
        ),
    )

    Box(modifier = Modifier.fillMaxSize()) {
        NavigationSuiteScaffold(
            navigationSuiteItems = {
                NavigationItem.entries.forEach { bar ->
                    item(
                        selected = bar.matches(currentRoute),
                        onClick = { navController.selectTab(bar.destination) },
                        icon = { Icon(painterResource(bar.destination.iconRes), null) },
                        label = {
                            Text(
                                text = bar.label(),
                                modifier = Modifier.testTag(GodTags.navTab(bar.destination.entry)),
                            )
                        },
                        colors = itemColors,
                    )
                }
            },
            navigationSuiteColors = suiteColors,
            containerColor = VoidBackground,
        ) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .windowInsetsPadding(WindowInsets.safeDrawing)
                    .consumeWindowInsets(WindowInsets.safeDrawing),
            ) {
                AppTopBar(
                    title = stringResource(titleResFor(currentRoute)),
                    canNavigateUp = canNavigateUp,
                    onNavigateUp = { navController.popBackStack() },
                    onHome = { navController.goHome() },
                    onMore = {
                        audio.buttonPress()
                        moreOpen = true
                    },
                )
                NavHost(
                    navController = navController,
                    startDestination = NavRoutes.HOME,
                    modifier = Modifier.fillMaxWidth().weight(1f),
                    enterTransition = {
                        slideInHorizontally(spring(stiffness = 400f)) { width ->
                            width / 3 * forwardSign
                        } + fadeIn()
                    },
                    exitTransition = {
                        slideOutHorizontally(spring(stiffness = 400f)) { width ->
                            -width / 3 * forwardSign
                        } + fadeOut()
                    },
                    popEnterTransition = {
                        slideInHorizontally(spring(stiffness = 400f)) { width ->
                            -width / 3 * forwardSign
                        } + fadeIn()
                    },
                    popExitTransition = {
                        slideOutHorizontally(spring(stiffness = 400f)) { width ->
                            width / 3 * forwardSign
                        } + fadeOut()
                    },
                ) {
                    appNavGraph(
                        navController = navController,
                        characters = characters,
                        combat = combat,
                        encounters = encounters,
                        maps = maps,
                    )
                }
            }
        }

        if (moreOpen) {
            MoreSheet(
                currentRoute = currentRoute,
                onOpen = { destination ->
                    moreOpen = false
                    audio.buttonPress()
                    navController.openDestination(destination)
                },
                onDismiss = { moreOpen = false },
            )
        }
    }
}

private fun NavHostController.selectTab(destination: Destination) {
    navigate(destination.entry) {
        popUpTo(NavRoutes.HOME) { saveState = true }
        launchSingleTop = true
        restoreState = true
    }
}

private fun NavHostController.openDestination(destination: Destination) {
    if (destination.route == NavRoutes.HOME) {
        goHome()
    } else {
        navigate(
            destination.deepLink,
            NavOptions.Builder().setLaunchSingleTop(true).build(),
        )
    }
}

private fun NavHostController.goHome() {
    navigate(NavRoutes.HOME) {
        popUpTo(NavRoutes.HOME) { inclusive = true }
        launchSingleTop = true
    }
}