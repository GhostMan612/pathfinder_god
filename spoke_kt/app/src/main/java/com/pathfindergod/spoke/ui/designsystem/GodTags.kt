// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.designsystem

object GodTags {
    const val TOP_BAR_TITLE = "pg:nav:topbar:title"
    const val TOP_BAR_BACK = "pg:nav:topbar:back"
    const val TOP_BAR_MORE = "pg:nav:topbar:more"

    fun navTab(route: String): String = "pg:nav:tab:$route"

    const val MORE_SHEET = "pg:more:sheet"

    fun moreDestination(route: String): String = "pg:more:destination:$route"

    const val HOME_PARTY = "pg:home:party"
    fun homeQuickDie(sides: Int): String = "pg:home:quickroll:d$sides"
    fun homeDestination(route: String): String = "pg:home:destination:$route"
    const val HOME_ENCOUNTER = "pg:home:encounter"

    const val DICE_PIT = "pg:dice:pit"
    const val DICE_RESULT = "pg:dice:result"
    const val DICE_ROLL_BUTTON = "pg:dice:roll"
    const val DICE_HISTORY_CLEAR = "pg:dice:history:clear"

    fun diceDie(sides: Int): String = "pg:dice:die:d$sides"
    fun diceCount(count: Int): String = "pg:dice:count:$count"
    fun diceModifier(modifier: Int): String = "pg:dice:modifier:$modifier"
    fun diceKeep(keep: Int?): String = "pg:dice:keep:${keep ?: 0}"
    fun diceAdvantage(name: String): String = "pg:dice:advantage:$name"
    fun diceTarget(target: Int?): String = "pg:dice:target:${target ?: 0}"

    const val DICE_EXPLODE = "pg:dice:explode"

    const val COMBAT_ROUND = "pg:combat:round"
    const val COMBAT_ACTIVE = "pg:combat:active"
    const val COMBAT_SUMMON = "pg:combat:summon"
    const val COMBAT_ADD = "pg:combat:add"
    const val COMBAT_END_TURN = "pg:combat:endturn"
    const val COMBAT_DIALOG_CLOSE = "pg:combat:dialog:close"

    fun combatant(id: String): String = "pg:combat:combatant:$id"
    fun combatantDamage(id: String): String = "pg:combat:combatant:$id:damage"
    fun combatantHeal(id: String): String = "pg:combat:combatant:$id:heal"
    fun combatantConditions(id: String): String = "pg:combat:combatant:$id:conditions"
    fun combatantCondition(id: String, name: String): String =
        "pg:combat:combatant:$id:condition:$name"

    fun hero(id: Long): String = "pg:hero:card:$id"
    fun heroDelete(id: Long): String = "pg:hero:card:$id:delete"
    const val heroBack = "pg:hero:back"
    fun heroShare(id: Long): String = "pg:hero:detail:$id:share"

    fun rule(rowId: Long): String = "pg:rules:card:$rowId"
    const val RULES_QUERY = "pg:rules:query"
    const val RULES_CLEAR = "pg:rules:clear"
    const val RULES_RESULT_COUNT = "pg:rules:result:count"

    fun map(mapId: String): String = "pg:map:card:$mapId"
    fun mapBanish(mapId: String): String = "pg:map:card:$mapId:banish"
    const val MAP_FAB = "pg:map:fab"
    const val MAP_CANVAS = "pg:map:viewer:canvas"
    const val MAP_SHARE = "pg:map:viewer:share"
    const val MAP_LAYER_GM = "pg:map:viewer:layer:gm"
    const val MAP_LAYER_PLAYER = "pg:map:viewer:layer:player"

    fun encounter(id: String): String = "pg:encounter:vault:$id"
    fun encounterDelete(id: String): String = "pg:encounter:vault:$id:delete"
    fun encounterDifficulty(difficulty: String): String =
        "pg:encounter:difficulty:$difficulty"

    const val ENCOUNTER_STATUS = "pg:encounter:status"

    const val CAMPAIGN_FAB = "pg:campaign:fab"
    const val CAMPAIGN_SUMMARIZE = "pg:campaign:summarize"

    const val LOOT_STATUS = "pg:loot:status"

    fun settingsToggle(key: String): String = "pg:settings:toggle:$key"
    fun settingsTrack(key: String): String = "pg:settings:track:$key"
    const val SETTINGS_CONNECT = "pg:settings:connect"
    const val SETTINGS_HUB_STATUS = "pg:settings:hub:status"
    const val SETTINGS_CREDITS = "pg:settings:credits"
    const val CREDITS_BACK = "pg:credits:back"
}