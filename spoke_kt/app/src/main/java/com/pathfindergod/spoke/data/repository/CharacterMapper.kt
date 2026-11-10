// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.repository

import com.pathfindergod.spoke.data.local.CharacterEntity
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.put

/**
 * Converts the hub's CharacterSheetModel JSON into the Room row.
 *
 * The hub owns the rules and returns nested objects for abilities,
 * proficiencies, feats, spellcasting and equipment. Keeping each nested
 * value as its original JSON lets the sheet render new generator fields
 * without a database migration.
 */
object CharacterMapper {

    fun fromWire(wire: Map<String, JsonElement>): CharacterEntity? {
        val name = text(wire["name"])?.trim().orEmpty()
        if (name.isBlank()) return null

        return CharacterEntity(
            name = name,
            ancestry = text(wire["ancestry"]),
            heritage = text(wire["heritage"]),
            background = text(wire["background"]),
            characterClass = text(wire["character_class"]) ?: text(wire["class"]),
            subclass = text(wire["subclass"]),
            level = int(wire["level"])?.coerceIn(1, 20) ?: 1,
            deity = text(wire["deity"]),
            alignment = text(wire["alignment"]),
            size = text(wire["size"]),
            gender = text(wire["gender"]),
            age = int(wire["age"])?.takeIf { it >= 0 },
            eyes = text(wire["eyes"]),
            hair = text(wire["hair"]),
            height = text(wire["height"]),
            weight = text(wire["weight"]),
            languages = text(wire["languages"]),
            senses = text(wire["senses"]),
            speed = text(wire["speed"]),
            abilities = json(wire["abilities"]),
            proficiencies = json(wire["proficiencies"]),
            feats = json(wire["feats"]),
            spellcasting = json(wire["spellcasting"]),
            equipment = json(wire["equipment"]),
            derived = derived(wire),
            conditions = json(wire["conditions"]),
            notes = text(wire["notes"]),
        )
    }

    /**
     * The character builder does not return a derived block today. Preserve a
     * hub-provided one when present; otherwise copy the flat AC/HP keys an LLM
     * sometimes adds so the existing stat tiles can show them.
     */
    private fun derived(wire: Map<String, JsonElement>): String? {
        val explicit = wire["derived"]
        if (explicit is JsonObject) return explicit.toString()

        val ac = wire["ac"] ?: wire["armor_class"]
        val hp = wire["hp"]
        val maxHp = wire["max_hp"] ?: wire["maxHp"]
        if (ac == null && hp == null && maxHp == null) return null

        return buildJsonObject {
            ac?.let { put("ac", it) }
            hp?.let { put("hp", it) }
            maxHp?.let { put("maxHp", it) }
        }.toString()
    }

    private fun text(element: JsonElement?): String? = when (element) {
        null, JsonNull -> null
        is JsonPrimitive -> element.contentOrNull?.takeIf { it.isNotBlank() }
        else -> element.toString().takeIf { it.isNotBlank() }
    }

    private fun int(element: JsonElement?): Int? =
        (element as? JsonPrimitive)?.intOrNull

    private fun json(element: JsonElement?): String? = when (element) {
        null, JsonNull -> null
        else -> element.toString()
    }
}
