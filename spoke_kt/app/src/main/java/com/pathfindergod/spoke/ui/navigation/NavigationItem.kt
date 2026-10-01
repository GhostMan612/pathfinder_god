// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.navigation

import android.net.Uri
import androidx.annotation.DrawableRes
import androidx.compose.runtime.Composable
import androidx.compose.ui.res.stringResource
import com.pathfindergod.spoke.R

object NavRoutes {
    const val HOME = "home"
    const val DICE = "dice"
    const val COMBAT = "combat"
    const val HERO = "hero"
    const val RULES = "rules"
    const val CAMPAIGN = "campaign"
    const val MAP = "map"
    const val ENCOUNTER = "encounter"
    const val GOD = "god"
    const val SETUP = "setup"

    const val DICE_PATTERN = "$DICE?die={die}"
    const val HERO_DETAIL = "hero/detail/{characterId}"
    const val MAP_VIEWER = "map/viewer/{mapId}"
    const val AUDIO_CREDITS = "setup/credits"

    const val ARG_DIE = "die"
    const val ARG_CHARACTER_ID = "characterId"
    const val ARG_MAP_ID = "mapId"

    const val DEEP_LINK_SCHEME = "pathfindergod"

    fun heroDetailRoute(characterId: Long): String = "hero/detail/$characterId"

    fun mapViewerRoute(mapId: String): String = "map/viewer/$mapId"
}

data class Destination(
    val route: String,
    val labelRes: Int,
    @DrawableRes val iconRes: Int,
    val entry: String = route,
    val deepLinkPattern: String = "${NavRoutes.DEEP_LINK_SCHEME}://$entry",
    val testTag: String = "pg:nav:route:$route",
) {
    val deepLink: Uri get() = Uri.parse(deepLinkPattern)
}

object Destinations {
    val Home = Destination(NavRoutes.HOME, R.string.nav_home, R.drawable.ki_home)
    val Dice = Destination(
        route = NavRoutes.DICE_PATTERN,
        labelRes = R.string.nav_dice,
        iconRes = R.drawable.ki_dice,
        entry = NavRoutes.DICE,
    )
    val Combat = Destination(NavRoutes.COMBAT, R.string.nav_combat, R.drawable.ki_combat)
    val Hero = Destination(NavRoutes.HERO, R.string.nav_hero, R.drawable.ki_hero)
    val Rules = Destination(NavRoutes.RULES, R.string.nav_rules, R.drawable.ki_rules)
    val Campaign = Destination(NavRoutes.CAMPAIGN, R.string.nav_campaign, R.drawable.ki_campaign)
    val Map = Destination(NavRoutes.MAP, R.string.nav_map, R.drawable.ki_map)
    val Encounter = Destination(NavRoutes.ENCOUNTER, R.string.nav_encounter, R.drawable.ki_encounter)
    val God = Destination(NavRoutes.GOD, R.string.nav_god, R.drawable.ki_god)
    val Setup = Destination(NavRoutes.SETUP, R.string.nav_setup, R.drawable.ki_setup)
    val AudioCredits = Destination(
        NavRoutes.AUDIO_CREDITS,
        R.string.more_audio_credits,
        R.drawable.ki_credits,
    )

    val heroDetail = Destination(
        route = NavRoutes.HERO_DETAIL,
        labelRes = R.string.hero_detail_title,
        iconRes = R.drawable.ki_hero,
        entry = NavRoutes.HERO_DETAIL,
        deepLinkPattern = "${NavRoutes.DEEP_LINK_SCHEME}://hero/detail/{characterId}",
    )

    val mapViewer = Destination(
        route = NavRoutes.MAP_VIEWER,
        labelRes = R.string.map_viewer_title,
        iconRes = R.drawable.ki_map,
        entry = NavRoutes.MAP_VIEWER,
        deepLinkPattern = "${NavRoutes.DEEP_LINK_SCHEME}://map/viewer/{mapId}",
    )
}

val overflowDestinations: List<Destination> = listOf(
    Destinations.Home,
    Destinations.Campaign,
    Destinations.Map,
    Destinations.Encounter,
    Destinations.God,
    Destinations.Setup,
    Destinations.AudioCredits,
)

enum class NavigationItem(val destination: Destination) {
    DICE(Destinations.Dice),
    COMBAT(Destinations.Combat),
    HERO(Destinations.Hero),
    RULES(Destinations.Rules);

    fun matches(route: String?): Boolean = destination.route == route
}

@Composable
fun NavigationItem.label(): String = stringResource(destination.labelRes)

fun titleResFor(route: String?): Int = when (route) {
    NavRoutes.HOME -> R.string.home_title
    NavRoutes.DICE_PATTERN -> R.string.nav_dice
    NavRoutes.COMBAT -> R.string.nav_combat
    NavRoutes.HERO -> R.string.nav_hero
    NavRoutes.HERO_DETAIL -> R.string.hero_detail_title
    NavRoutes.RULES -> R.string.nav_rules
    NavRoutes.CAMPAIGN -> R.string.nav_campaign
    NavRoutes.MAP -> R.string.nav_map
    NavRoutes.MAP_VIEWER -> R.string.map_viewer_title
    NavRoutes.ENCOUNTER -> R.string.nav_encounter
    NavRoutes.GOD -> R.string.nav_god
    NavRoutes.SETUP -> R.string.nav_setup
    NavRoutes.AUDIO_CREDITS -> R.string.credits_title
    else -> R.string.app_name
}