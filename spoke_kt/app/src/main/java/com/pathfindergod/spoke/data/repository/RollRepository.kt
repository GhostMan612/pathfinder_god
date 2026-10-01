// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.repository

import com.pathfindergod.spoke.data.local.RollDao
import com.pathfindergod.spoke.data.local.RollEntity
import com.pathfindergod.spoke.ui.dice.DegreeOfSuccess
import com.pathfindergod.spoke.ui.dice.Impact
import com.pathfindergod.spoke.ui.dice.RollRecord

const val MAX_ROLL_HISTORY = 200

class RollRepository(
    private val dao: RollDao,
) {
    suspend fun recent(limit: Int = MAX_ROLL_HISTORY): List<RollRecord> =
        dao.recent(limit).map(::toRecord)

    suspend fun persist(record: RollRecord): RollRecord {
        val id = dao.insert(toEntity(record))
        dao.trimTo(MAX_ROLL_HISTORY)
        return record.copy(id = id)
    }

    suspend fun clear() {
        dao.clear()
    }

    private fun toEntity(record: RollRecord) = RollEntity(
        id = record.id,
        notation = record.notation,
        rolls = record.rolls.encode(),
        kept = record.kept.encode(),
        dropped = record.dropped.encode(),
        modifier = record.modifier,
        total = record.total,
        impact = record.impact.name,
        degree = record.degree?.name.orEmpty(),
        targetNumber = record.targetNumber,
        rolledAt = record.rolledAt,
    )

    private fun toRecord(entity: RollEntity) = RollRecord(
        id = entity.id,
        notation = entity.notation,
        rolls = entity.rolls.decode(),
        kept = entity.kept.decode(),
        dropped = entity.dropped.decode(),
        modifier = entity.modifier,
        total = entity.total,
        impact = enumOrDefault(entity.impact, Impact.NORMAL),
        rolledAt = entity.rolledAt,
        targetNumber = entity.targetNumber,
        degree = degreeOrNull(entity.degree),
    )

    private fun List<Int>.encode(): String = joinToString(SEPARATOR)

    private fun String.decode(): List<Int> =
        if (isBlank()) emptyList() else split(SEPARATOR).mapNotNull { it.toIntOrNull() }

    private inline fun <reified T : Enum<T>> enumOrDefault(name: String, fallback: T): T =
        enumValues<T>().firstOrNull { it.name == name } ?: fallback

    private inline fun <reified T : Enum<T>> degreeOrNull(name: String): T? =
        enumValues<T>().firstOrNull { it.name == name }

    companion object {
        const val SEPARATOR = ","
    }
}
