// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.character

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class CharacterEquipmentTest {

    @Test
    fun parsesWeaponsArmorGearAndCoins() {
        val summary = CharacterEquipmentParser.parse(
            """
            {
              "weapons": [
                {"name": "Warhammer", "attackBonus": 8, "damage": "1d8+4", "traits": ["shove", "versatile P"]},
                {"name": "Dagger", "damage": "1d4", "range": "thrown 10 ft"}
              ],
              "armor": {"name": "Scale Mail", "acBonus": 4, "dexCap": 2},
              "shield": {"name": "Steel Shield", "acBonus": 2},
              "gear": {"rope": "50 ft", "torches": 5},
              "cp": 7,
              "gp": 12
            }
            """.trimIndent(),
        )

        val parsed = summary!!
        assertEquals(2, parsed.weapons.size)
        assertEquals("Warhammer", parsed.weapons[0].name)
        assertTrue(parsed.weapons[0].details.contains("Attack Bonus" to "8"))
        assertTrue(parsed.weapons[0].details.contains("Damage" to "1d8+4"))
        assertTrue(parsed.weapons[0].details.contains("Traits" to "shove, versatile P"))
        assertEquals("Scale Mail", parsed.armor.single().name)
        assertEquals("Steel Shield", parsed.shield.single().name)
        assertEquals(2, parsed.gear.size)
        assertEquals(listOf("CP" to "7", "GP" to "12"), parsed.coins)
        assertTrue(parsed.other.isEmpty())
    }

    @Test
    fun toleratesArrayAndPrimitiveShapes() {
        val summary = CharacterEquipmentParser.parse(
            """
            {
              "weapons": "Club",
              "armor": [{"name":"Leather","acBonus":1}],
              "gear": ["Backpack", "Bedroll"]
            }
            """.trimIndent(),
        )!!

        assertEquals("Club", summary.weapons.single().name)
        assertEquals("Leather", summary.armor.single().name)
        assertEquals(listOf("Backpack", "Bedroll"), summary.gear.map { it.name })
    }

    @Test
    fun keepsUnknownKeysAsReadableLines() {
        val summary = CharacterEquipmentParser.parse(
            """{"wands":{"healing":2},"notes":"spare chalk"}""",
        )!!

        assertTrue(summary.other.any { it.name == "Wands" })
        assertTrue(summary.other.any { it.name == "Notes" })
    }

    @Test
    fun malformedOrEmptyInputYieldsNoSummary() {
        assertNull(CharacterEquipmentParser.parse(null))
        assertNull(CharacterEquipmentParser.parse(""))
        assertNull(CharacterEquipmentParser.parse("not json"))
    }
}
