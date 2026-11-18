// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.repository

import com.pathfindergod.spoke.data.local.CharacterEntity
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class CharacterMapperTest {

    private fun wire(payload: String) = Json.parseToJsonElement(payload).jsonObject

    @Test
    fun mapsTheHubCharacterSheetIntoTheRoomRow() {
        val entity = CharacterMapper.fromWire(
            wire(
                """
                {
                  "name": "Borin Emberforge",
                  "ancestry": "Dwarf",
                  "heritage": "Ancient-Blooded",
                  "background": "Martial Disciple",
                  "character_class": "Champion",
                  "subclass": "Paladin",
                  "level": 3,
                  "deity": "Torag",
                  "alignment": "LG",
                  "size": "Medium",
                  "speed": "20",
                  "abilities": {"str": 18, "dex": 10, "con": 16, "int": 8, "wis": 12, "cha": 14},
                  "proficiencies": {"skills": {"athletics": 2}, "defenses": {"fortitude": 2}},
                  "feats": [{"name": "Power Attack", "type": "class", "level": 1}],
                  "spellcasting": {"tradition": "divine", "focusPool": 1},
                  "equipment": {
                    "weapons": [{"name": "Warhammer", "damage": "1d8", "traits": ["shove"]}],
                    "armor": {"name": "Scale Mail", "acBonus": 4},
                    "gear": {"rope": "50 ft"},
                    "gp": 12
                  },
                  "notes": "Sworn to the forge."
                }
                """.trimIndent(),
            ),
        )

        assertNotNull(entity)
        val mapped = entity!!
        assertEquals("Borin Emberforge", mapped.name)
        assertEquals("Dwarf", mapped.ancestry)
        assertEquals("Ancient-Blooded", mapped.heritage)
        assertEquals("Champion", mapped.characterClass)
        assertEquals("Paladin", mapped.subclass)
        assertEquals(3, mapped.level)
        assertEquals("Torag", mapped.deity)
        assertEquals("20", mapped.speed)
        assertTrue(mapped.abilities!!.contains("\"str\":18"))
        assertTrue(mapped.proficiencies!!.contains("athletics"))
        assertTrue(mapped.feats!!.contains("Power Attack"))
        assertTrue(mapped.spellcasting!!.contains("divine"))
        assertTrue(mapped.equipment!!.contains("Warhammer"))
        assertEquals("Sworn to the forge.", mapped.notes)
    }

    @Test
    fun acceptsTheClassAliasAndClampsTheLevel() {
        val entity = CharacterMapper.fromWire(
            wire("""{"name":"Mira","class":"Rogue","level":99}"""),
        )

        assertEquals("Rogue", entity?.characterClass)
        assertEquals(20, entity?.level)
    }

    @Test
    fun rejectsASheetWithoutAName() {
        assertNull(CharacterMapper.fromWire(wire("""{"ancestry":"Elf"}""")))
        assertNull(CharacterMapper.fromWire(wire("""{"name":"   "}""")))
    }

    @Test
    fun preservesFlatArmorClassAndHitPointsWhenTheHubSuppliesThem() {
        val entity = CharacterMapper.fromWire(
            wire("""{"name":"Mira","ac":18,"hp":22,"max_hp":30}"""),
        )

        val mapped = entity!!
        val derived = mapped.derived!!
        assertTrue(derived.contains("\"ac\":18"))
        assertTrue(derived.contains("\"hp\":22"))
        assertTrue(derived.contains("\"maxHp\":30"))
    }

    @Test
    fun serializesEntityToWireFormatAndPreservesIdentity() {
        val original = CharacterEntity(
            id = 42,
            name = "Kyra",
            ancestry = "Human",
            characterClass = "Cleric",
            level = 5,
            uuid = "test-uuid-kyra",
            serverRevision = 3,
            abilities = """{"wis":18,"str":14}""",
            derived = """{"ac":19,"hp":45,"maxHp":45}""",
            notes = "Devoted to Sarenrae.",
        )

        val wire = CharacterMapper.toWire(original)
        val roundTripped = CharacterMapper.fromWire(wire)!!

        assertEquals("Kyra", roundTripped.name)
        assertEquals("Human", roundTripped.ancestry)
        assertEquals("Cleric", roundTripped.characterClass)
        assertEquals(5, roundTripped.level)
        assertEquals("test-uuid-kyra", roundTripped.uuid)
        assertEquals(3, roundTripped.serverRevision)
        assertTrue(roundTripped.abilities!!.contains("\"wis\":18"))
        assertTrue(roundTripped.derived!!.contains("\"ac\":19"))
        assertEquals("Devoted to Sarenrae.", roundTripped.notes)
    }
}
