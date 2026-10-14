// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.combat

import com.pathfindergod.spoke.ui.viewmodel.CombatUiState
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.add
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
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

    private val json = Json { prettyPrint = false }

    fun toSceneJson(state: CombatUiState, campaignId: Int): String {
        val root: JsonObject = buildJsonObject {
            put("campaign_id", campaignId)
            put("round", state.currentRound)
            put(
                "active_combatant",
                state.combatants.getOrNull(state.activeIndex)?.id ?: "",
            )
            put(
                "combatants",
                buildJsonArray {
                    state.combatants.forEach { c ->
                        add(
                            buildJsonObject {
                                put("id", c.id)
                                put("name", c.name)
                                put("is_pc", c.isPc)
                                put("initiative", c.initiative)
                                put("current_hp", c.currentHp)
                                put("max_hp", c.maxHp)
                                put("temp_hp", c.tempHp)
                                put("ac", c.ac)
                                put(
                                    "conditions",
                                    buildJsonArray {
                                        c.conditions.forEach { cond ->
                                            add(
                                                buildJsonObject {
                                                    put("name", cond.name)
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
        }
        val compact = root.toString()
        return if (compact.length <= MAX_SCENE_CHARS) {
            compact
        } else {
            compact.take(MAX_SCENE_CHARS)
        }
    }

    /** Nothing tracked means "combat cleared": publish an empty scene. */
    fun shouldPublish(state: CombatUiState): Boolean = state.combatants.isNotEmpty()

    /** Parse a scene back; used by tests and by the round-trip check. */
    fun parse(scene: String): JsonObject =
        json.parseToJsonElement(scene).jsonObject

    fun combatants(scene: String): JsonArray =
        parse(scene)["combatants"] as? JsonArray ?: JsonArray(emptyList())
}