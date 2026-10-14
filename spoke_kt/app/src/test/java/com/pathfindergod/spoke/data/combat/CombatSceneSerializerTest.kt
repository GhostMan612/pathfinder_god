// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.combat

import com.pathfindergod.spoke.ui.viewmodel.CombatCondition
import com.pathfindergod.spoke.ui.viewmodel.CombatUiState
import com.pathfindergod.spoke.ui.viewmodel.Combatant
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.boolean
import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The Spoke combat tracker is the producer for POST /combat/scene. These tests
 * pin the JSON schema the Hub GM consumes, including the 4000-char Hub bound.
 */
class CombatSceneSerializerTest {

    private val hero = Combatant(
        id = "hero-1",
        name = "Brann Stonecoil",
        isPc = true,
        initiative = 19,
        currentHp = 27,
        maxHp = 34,
        tempHp = 4,
        ac = 18,
        conditions = listOf(
            CombatCondition("prone", durationRounds = 2),
            CombatCondition("blessed"),
        ),
    )

    private val goblin = Combatant(
        id = "goblin-1",
        name = "Goblin Cutter",
        isPc = false,
        initiative = 7,
        currentHp = 11,
        maxHp = 11,
        ac = 13,
    )

    private val state = CombatUiState(
        combatants = listOf(hero, goblin),
        activeIndex = 0,
        currentRound = 3,
    )

    @Test
    fun `scene carries campaign id round and active combatant`() {
        val scene = CombatSceneSerializer.toSceneJson(state, campaignId = 7)
        val root = CombatSceneSerializer.parse(scene)

        assertEquals(7, root["campaign_id"]!!.jsonPrimitive.int)
        assertEquals(3, root["round"]!!.jsonPrimitive.int)
        assertEquals("hero-1", root["active_combatant"]!!.jsonPrimitive.content)
    }

    @Test
    fun `every combatant is serialised with hp ac and pc flag`() {
        val root = CombatSceneSerializer.parse(
            CombatSceneSerializer.toSceneJson(state, campaignId = 1),
        )
        val list = root["combatants"] as JsonArray

        assertEquals(2, list.size)
        val first = list[0] as JsonObject
        assertEquals("Brann Stonecoil", first["name"]!!.jsonPrimitive.content)
        assertEquals(27, first["current_hp"]!!.jsonPrimitive.int)
        assertEquals(34, first["max_hp"]!!.jsonPrimitive.int)
        assertEquals(4, first["temp_hp"]!!.jsonPrimitive.int)
        assertEquals(18, first["ac"]!!.jsonPrimitive.int)
        assertTrue(first["is_pc"]!!.jsonPrimitive.boolean)

        val second = list[1] as JsonObject
        assertFalse(second["is_pc"]!!.jsonPrimitive.boolean)
        assertEquals(13, second["ac"]!!.jsonPrimitive.int)
    }

    @Test
    fun `conditions preserve name value and duration`() {
        val root = CombatSceneSerializer.parse(
            CombatSceneSerializer.toSceneJson(state, campaignId = 1),
        )
        val conditions = ((root["combatants"] as JsonArray)[0] as JsonObject)["conditions"] as JsonArray

        assertEquals(2, conditions.size)
        val prone = conditions[0] as JsonObject
        assertEquals("prone", prone["name"]!!.jsonPrimitive.content)
        assertEquals(1, prone["value"]!!.jsonPrimitive.int)
        assertEquals(2, prone["duration_rounds"]!!.jsonPrimitive.int)

        val blessed = conditions[1] as JsonObject
        assertEquals("blessed", blessed["name"]!!.jsonPrimitive.content)
        assertFalse(blessed.containsKey("duration_rounds"))
    }

    @Test
    fun `active combatant is empty string when the tracker is cleared`() {
        val empty = CombatUiState()
        val root = CombatSceneSerializer.parse(
            CombatSceneSerializer.toSceneJson(empty, campaignId = 1),
        )

        assertEquals("", root["active_combatant"]!!.jsonPrimitive.content)
        assertEquals(0, (root["combatants"] as JsonArray).size)
    }

    @Test
    fun `out of range active index does not throw`() {
        val stale = state.copy(activeIndex = 99)
        val root = CombatSceneSerializer.parse(
            CombatSceneSerializer.toSceneJson(stale, campaignId = 1),
        )

        assertEquals("", root["active_combatant"]!!.jsonPrimitive.content)
    }

    @Test
    fun `scene never exceeds the hub character bound`() {
        val crowd = CombatUiState(
            combatants = (1..60).map {
                Combatant(
                    id = "npc-$it",
                    name = "Generic Adversary $it",
                    initiative = it,
                    currentHp = 100,
                    maxHp = 100,
                    ac = 15,
                    conditions = listOf(
                        CombatCondition("prone"),
                        CombatCondition("stunned", durationRounds = 3),
                    ),
                )
            },
            activeIndex = 0,
            currentRound = 12,
        )

        val scene = CombatSceneSerializer.toSceneJson(crowd, campaignId = 1)

        assertTrue(scene.length <= CombatSceneSerializer.MAX_SCENE_CHARS)
        assertTrue(scene.length <= 4000)
    }

    @Test
    fun `shouldPublish is false only when nothing is tracked`() {
        assertFalse(CombatSceneSerializer.shouldPublish(CombatUiState()))
        assertTrue(CombatSceneSerializer.shouldPublish(state))
    }

    @Test
    fun `scene round trips through the hub accessor`() {
        val scene = CombatSceneSerializer.toSceneJson(state, campaignId = 4)

        assertEquals(2, CombatSceneSerializer.combatants(scene).size)
    }
}