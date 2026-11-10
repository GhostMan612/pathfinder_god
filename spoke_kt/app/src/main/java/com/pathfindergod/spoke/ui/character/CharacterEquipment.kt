// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.character

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.contentOrNull

data class EquipmentLine(
    val name: String,
    val details: List<Pair<String, String>> = emptyList(),
)

data class EquipmentSummary(
    val weapons: List<EquipmentLine> = emptyList(),
    val armor: List<EquipmentLine> = emptyList(),
    val shield: List<EquipmentLine> = emptyList(),
    val gear: List<EquipmentLine> = emptyList(),
    val coins: List<Pair<String, String>> = emptyList(),
    val other: List<EquipmentLine> = emptyList(),
) {
    val isEmpty: Boolean
        get() = weapons.isEmpty() &&
            armor.isEmpty() &&
            shield.isEmpty() &&
            gear.isEmpty() &&
            coins.isEmpty() &&
            other.isEmpty()
}

/**
 * Renders the free-form equipment object the character builder returns.
 * It stays tolerant on purpose: the LLM may use an array, an object, or a
 * single string for any category, and no shape should take the sheet down.
 */
object CharacterEquipmentParser {

    private val coinKeys = listOf("cp", "sp", "gp", "pp")

    fun parse(raw: String?): EquipmentSummary? {
        if (raw.isNullOrBlank()) return null
        val root = runCatching { Json.parseToJsonElement(raw) }.getOrNull()
        if (root !is JsonObject) return null

        val weapons = root["weapons"].toLines("Weapon")
        val armor = root["armor"].toLines("Armor")
        val shield = root["shield"].toLines("Shield")
        val gear = root["gear"].toGearLines()
        val coins = coinKeys.mapNotNull { key ->
            root[key]?.render()?.takeIf { it.isNotBlank() }?.let { key.uppercase() to it }
        }
        val known = setOf("weapons", "armor", "shield", "gear") + coinKeys
        val other = root.entries
            .filterNot { it.key in known }
            .map { (key, value) ->
                EquipmentLine(
                    name = prettyKey(key),
                    details = value.toDetails(),
                )
            }

        return EquipmentSummary(
            weapons = weapons,
            armor = armor,
            shield = shield,
            gear = gear,
            coins = coins,
            other = other,
        )
    }

    /**
     * Gear objects are name -> quantity maps ({"rope": "50 ft"}), unlike armor
     * and shields which are a single item object. Render each gear key as its
     * own line so the sheet does not collapse the whole pack into "Gear".
     */
    private fun JsonElement?.toGearLines(): List<EquipmentLine> = when (this) {
        null, JsonNull -> emptyList()
        is JsonArray -> flatMap { it.toLines("Gear") }
        is JsonObject -> entries.map { (key, value) ->
            EquipmentLine(
                name = prettyKey(key),
                details = value.toDetails(),
            )
        }
        is JsonPrimitive -> contentOrNull?.takeIf { it.isNotBlank() }
            ?.let { listOf(EquipmentLine(name = it)) }
            ?: emptyList()
    }

    private fun JsonElement?.toLines(fallbackName: String): List<EquipmentLine> = when (this) {
        null, JsonNull -> emptyList()
        is JsonArray -> flatMap { it.toLines(fallbackName) }
        is JsonObject -> {
            val name = (get("name") as? JsonPrimitive)?.contentOrNull?.takeIf { it.isNotBlank() }
                ?: (get("item") as? JsonPrimitive)?.contentOrNull?.takeIf { it.isNotBlank() }
                ?: fallbackName
            val details = entries
                .filterNot { it.key == "name" || it.key == "item" }
                .mapNotNull { (key, value) -> value.render()?.let { prettyKey(key) to it } }
            listOf(EquipmentLine(name = name, details = details))
        }
        is JsonPrimitive -> contentOrNull?.takeIf { it.isNotBlank() }
            ?.let { listOf(EquipmentLine(name = it)) }
            ?: emptyList()
    }

    private fun JsonElement.toDetails(): List<Pair<String, String>> = when (this) {
        is JsonObject -> entries.mapNotNull { (key, value) ->
            value.render()?.let { prettyKey(key) to it }
        }
        is JsonArray -> mapIndexedNotNull { index, value ->
            value.render()?.let { "${index + 1}" to it }
        }
        JsonNull -> emptyList()
        is JsonPrimitive -> contentOrNull?.takeIf { it.isNotBlank() }?.let { listOf("value" to it) }
            ?: emptyList()
    }

    private fun JsonElement.render(): String? = when (this) {
        JsonNull -> null
        is JsonPrimitive -> contentOrNull?.takeIf { it.isNotBlank() }
        is JsonArray -> mapNotNull { it.render() }
            .takeIf { it.isNotEmpty() }
            ?.joinToString(", ")
        is JsonObject -> entries
            .mapNotNull { (key, value) -> value.render()?.let { "${prettyKey(key)} $it" } }
            .takeIf { it.isNotEmpty() }
            ?.joinToString(", ")
    }

    private fun prettyKey(key: String): String {
        val spaced = key
            .replace('_', ' ')
            .replace(Regex("([a-z0-9])([A-Z])"), "$1 $2")
        return spaced.replaceFirstChar { it.uppercase() }
    }
}
