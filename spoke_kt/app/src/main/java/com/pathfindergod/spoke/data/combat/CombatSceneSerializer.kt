// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.combat

import com.pathfindergod.spoke.ui.viewmodel.CombatUiState
import com.pathfindergod.spoke.ui.viewmodel.Combatant
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.add
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put

/**
 * Serialises the Spoke combat tracker into the Hub's `POST /combat/scene`
 * contract so the live GM can reason about HP, turn order and conditions.
 *
 * The Hub endpoint takes `scene` as an opaque JSON *string* (CombatSceneIn),
 * so this class owns the schema and keeps it unit-testable without any network.
 *
 * Deliberately pure - no Retrofit, no coroutines, no Context - which is what
 * makes [toSceneJson] directly testable and keeps the ViewModel free of
 * serialization concerns.
 */
object CombatSceneSerializer {

    /** Hub bounds `scene` at 4000 chars; stay under it with headroom. */
    const val MAX_SCENE_CHARS = 3_500

    /**
     * Per-field caps. These exist so the *minimum* payload (one combatant, the
     * active one) can never itself exceed the budget - which is what lets
     * [toSceneJson] guarantee a bounded result without ever slicing a string.
     * Truncating a single text field is safe; truncating the serialised
     * document is not.
     */
    const val MAX_NAME_CHARS = 120
    const val MAX_CONDITION_NAME_CHARS = 60
    const val MAX_CONDITIONS = 12

    private val json = Json { prettyPrint = false }

    /**
     * Order in which combatants earn their place in the payload: the active
     * combatant first (so it is never trimmed away), then everyone else by
     * initiative, highest first.
     *
     * Ties keep their original relative order, so the ladder a GM sees matches
     * the tracker the player sees.
     */
    private fun priorityOrder(state: CombatUiState): List<Combatant> {
        val active = state.combatants.getOrNull(state.activeIndex)
        if (active == null) {
            return state.combatants.sortedByDescending { it.initiative }
        }
        val rest = state.combatants
            .filterIndexed { index, _ -> index != state.activeIndex }
            .sortedByDescending { it.initiative }
        return listOf(active) + rest
    }

    fun toSceneJson(state: CombatUiState, campaignId: Int): String {
        val ordered = priorityOrder(state)
        // The active combatant must survive, so the floor is 1 when there is
        // anyone at all, otherwise 0.
        val floor = if (ordered.isEmpty()) 0 else 1

        // Render length is non-increasing as we keep fewer combatants, so the
        // largest count that fits can be binary-searched. Trimming the TAIL is
        // what makes that true: the dropped entries are the lowest priority.
        var lo = floor
        var hi = ordered.size
        var best = floor
        while (lo <= hi) {
            val mid = (lo + hi) ushr 1
            val candidate = render(ordered.take(mid), ordered.size - mid, state, campaignId)
            if (candidate.length <= MAX_SCENE_CHARS) {
                best = mid
                lo = mid + 1
            } else {
                hi = mid - 1
            }
        }

        // Defensive: re-verify the search result and step down if the digit
        // width of omitted_count ever broke strict monotonicity.
        var out = render(ordered.take(best), ordered.size - best, state, campaignId)
        var guard = 0
        while (out.length > MAX_SCENE_CHARS && best > floor && guard <= ordered.size) {
            best -= 1
            out = render(ordered.take(best), ordered.size - best, state, campaignId)
            guard += 1
        }
        return out
    }

    private fun render(
        kept: List<Combatant>,
        omitted: Int,
        state: CombatUiState,
        campaignId: Int,
    ): String = buildJsonObject {
        put("campaign_id", campaignId)
        put("round", state.currentRound)
        put(
            "active_combatant",
            state.combatants.getOrNull(state.activeIndex)?.id ?: "",
        )
        // How many combatants the tracker actually holds, and how many this
        // payload had to leave out. The GM can tell "truncated for size" apart
        // from "that is everyone".
        put("total_count", state.combatants.size)
        put("omitted_count", omitted)
        put(
            "combatants",
            buildJsonArray {
                kept.forEach { c ->
                    add(
                        buildJsonObject {
                            put("id", c.id)
                            put("name", c.name.take(MAX_NAME_CHARS))
                            put("is_pc", c.isPc)
                            put("initiative", c.initiative)
                            put("current_hp", c.currentHp)
                            put("max_hp", c.maxHp)
                            put("temp_hp", c.tempHp)
                            put("ac", c.ac)
                            put(
                                "conditions",
                                buildJsonArray {
                                    c.conditions.take(MAX_CONDITIONS).forEach { cond ->
                                        add(
                                            buildJsonObject {
                                                put("name", cond.name.take(MAX_CONDITION_NAME_CHARS))
                                                put("value", cond.value)
                                                cond.durationRounds?.let {
                                                    put("duration_rounds", it)
                                                }
                                            },
                                        )
                                    }
                                },
                            )
                        },
                    )
                }
            },
        )
    }.toString()

    /** Nothing tracked means "combat cleared": publish an empty scene. */
    fun shouldPublish(state: CombatUiState): Boolean = state.combatants.isNotEmpty()

    /** Parse a scene back; used by tests and by the round-trip check. */
    fun parse(scene: String): JsonObject =
        json.parseToJsonElement(scene).jsonObject

    fun combatants(scene: String): JsonArray =
        parse(scene)["combatants"] as? JsonArray ?: JsonArray(emptyList())

    /** How many combatants the payload had to leave out to fit the budget. */
    fun omittedCount(scene: String): Int =
        (parse(scene)["omitted_count"] as? JsonPrimitive)?.jsonPrimitive?.int ?: 0

    /** How many combatants the tracker held when this scene was built. */
    fun totalCount(scene: String): Int =
        (parse(scene)["total_count"] as? JsonPrimitive)?.jsonPrimitive?.int ?: 0
}