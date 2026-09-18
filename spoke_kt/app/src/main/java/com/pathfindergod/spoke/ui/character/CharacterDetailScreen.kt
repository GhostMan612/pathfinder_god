// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.character

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.pathfindergod.spoke.data.local.CharacterEntity
import com.pathfindergod.spoke.ui.theme.CrimsonPrimary
import com.pathfindergod.spoke.ui.theme.CritRed
import com.pathfindergod.spoke.ui.theme.GodTypography
import com.pathfindergod.spoke.ui.theme.GoldAccent
import com.pathfindergod.spoke.ui.theme.ParchmentSurface
import com.pathfindergod.spoke.ui.theme.TextPrimary
import com.pathfindergod.spoke.ui.theme.TextSecondary
import com.pathfindergod.spoke.ui.theme.rpgPanel
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.intOrNull

private val abilityOrder = listOf("str", "dex", "con", "int", "wis", "cha")

private fun flatEntries(raw: String?): List<Pair<String, String>> {
    if (raw.isNullOrBlank()) return emptyList()
    return try {
        when (val element = Json.parseToJsonElement(raw)) {
            is JsonObject -> element.entries.map { (key, value) -> key to renderValue(value) }
            is JsonArray -> element.mapIndexed { index, value -> "${index + 1}" to renderValue(value) }
            else -> listOf("value" to renderValue(element))
        }
    } catch (_: Exception) {
        listOf("text" to raw)
    }
}

private fun renderValue(element: JsonElement): String = when (element) {
    is JsonPrimitive -> element.intOrNull?.toString() ?: element.content
    else -> element.toString()
}

private fun abilityModifier(score: Int): Int = Math.floorDiv(score - 10, 2)

@Composable
fun CharacterDetailScreen(
    entity: CharacterEntity,
    onBack: () -> Unit,
) {
    val derived = remember(entity.derived) { flatEntries(entity.derived).toMap() }
    val abilities = remember(entity.abilities) { flatEntries(entity.abilities).toMap() }
    val proficiencies = remember(entity.proficiencies) { flatEntries(entity.proficiencies) }
    val feats = remember(entity.feats) { flatEntries(entity.feats) }
    Column(
        modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text(
            text = "‹ Roster",
            style = GodTypography.labelLarge,
            color = GoldAccent,
            modifier = Modifier.clickable { onBack() }.padding(vertical = 4.dp),
        )
        Row(
            modifier = Modifier.rpgPanel().fillMaxWidth().padding(16.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Box(
                modifier = Modifier.size(56.dp).background(CrimsonPrimary, CircleShape),
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    text = entity.name.firstOrNull()?.uppercase() ?: "?",
                    style = GodTypography.headlineSmall,
                    color = ParchmentSurface,
                )
            }
            Column(modifier = Modifier.padding(start = 16.dp)) {
                Text(
                    text = entity.name,
                    style = GodTypography.headlineSmall,
                    color = GoldAccent,
                )
                Text(
                    text = "${entity.ancestry ?: "—"} · ${entity.characterClass ?: "—"} · Level ${entity.level}",
                    style = GodTypography.bodyMedium,
                    color = TextSecondary,
                )
            }
        }
        Row(
            modifier = Modifier.rpgPanel().fillMaxWidth().padding(vertical = 12.dp),
            horizontalArrangement = Arrangement.SpaceEvenly,
        ) {
            SheetStat(label = "AC", value = derived["ac"] ?: "10", color = TextPrimary)
            SheetStat(
                label = "HP",
                value = "${derived["hp"] ?: "0"}/${derived["maxHp"] ?: "0"}",
                color = CritRed,
            )
            SheetStat(
                label = "Speed",
                value = "${derived["speed"] ?: entity.speed ?: "25"} ft",
                color = TextPrimary,
            )
        }
        Column(modifier = Modifier.rpgPanel().fillMaxWidth().padding(16.dp)) {
            Text(
                text = "Ability Scores",
                style = GodTypography.titleMedium,
                color = GoldAccent,
            )
            abilityOrder.chunked(3).forEach { row ->
                Row(
                    modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
                    horizontalArrangement = Arrangement.SpaceEvenly,
                ) {
                    row.forEach { key ->
                        val score = abilities[key]?.toIntOrNull() ?: 10
                        val mod = abilityModifier(score)
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Text(
                                text = key.uppercase(),
                                style = GodTypography.labelLarge,
                                color = TextSecondary,
                            )
                            Text(
                                text = "$score",
                                style = GodTypography.titleLarge,
                                fontWeight = FontWeight.Bold,
                                color = TextPrimary,
                            )
                            Text(
                                text = if (mod >= 0) "+$mod" else "$mod",
                                style = GodTypography.bodyMedium,
                                color = GoldAccent,
                            )
                        }
                    }
                }
            }
        }
        SheetSection(title = "Proficiencies", entries = proficiencies)
        SheetSection(title = "Feats", entries = feats)
    }
}

@Composable
private fun SheetStat(
    label: String,
    value: String,
    color: androidx.compose.ui.graphics.Color,
) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Text(
            text = value,
            style = GodTypography.titleLarge,
            fontWeight = FontWeight.Bold,
            color = color,
        )
        Text(
            text = label,
            style = GodTypography.bodyMedium,
            color = TextSecondary,
        )
    }
}

@Composable
private fun SheetSection(
    title: String,
    entries: List<Pair<String, String>>,
) {
    Column(modifier = Modifier.rpgPanel().fillMaxWidth().padding(16.dp)) {
        Text(
            text = title,
            style = GodTypography.titleMedium,
            color = GoldAccent,
        )
        if (entries.isEmpty()) {
            Text(
                text = "—",
                style = GodTypography.bodyMedium,
                color = TextSecondary,
                modifier = Modifier.padding(top = 4.dp),
            )
        } else {
            entries.forEach { (key, value) ->
                Text(
                    text = "$key · $value",
                    style = GodTypography.bodyMedium,
                    color = TextPrimary,
                    modifier = Modifier.padding(top = 4.dp),
                )
            }
        }
    }
}
