// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.dice

import kotlin.random.Random

enum class Die(val sides: Int) {
    D4(4),
    D6(6),
    D8(8),
    D10(10),
    D12(12),
    D20(20),
}

enum class Advantage {
    STRAIGHT,
    ADVANTAGE,
    DISADVANTAGE,
}

enum class Impact {
    NORMAL,
    CRITICAL_SUCCESS,
    CRITICAL_FAILURE,
}

data class DiceSpec(
    val count: Int,
    val sides: Int,
    val keepHighest: Int? = null,
    val keepLowest: Int? = null,
    val modifier: Int = 0,
    val advantage: Advantage = Advantage.STRAIGHT,
)

data class RollRecord(
    val notation: String,
    val rolls: List<Int>,
    val kept: List<Int>,
    val dropped: List<Int>,
    val modifier: Int,
    val total: Int,
    val impact: Impact,
)

class DiceEngine(private val random: Random = Random.Default) {

    private val notationPattern =
        Regex("""^(\d*)d(\d+)(?:(kh|kl)(\d+))?([+-]\d+)?(adv|dis)?$""", RegexOption.IGNORE_CASE)

    private val _history = mutableListOf<RollRecord>()
    val history: List<RollRecord> get() = _history.toList()

    fun clearHistory() {
        _history.clear()
    }

    fun roll(notation: String): RollRecord = roll(parse(notation), notation)

    fun roll(spec: DiceSpec, notation: String? = null): RollRecord {
        if (spec.advantage == Advantage.STRAIGHT) {
            val dice = List(spec.count) { die(spec.sides) }
            return finish(spec, notation, dice, dice)
        }
        val first = List(spec.count) { die(spec.sides) }
        val second = List(spec.count) { die(spec.sides) }
        val paired = first.zip(second) { a, b ->
            if (spec.advantage == Advantage.ADVANTAGE) maxOf(a, b) else minOf(a, b)
        }
        return finish(spec, notation, first + second, paired)
    }

    private fun finish(
        spec: DiceSpec,
        notation: String?,
        physical: List<Int>,
        effective: List<Int>,
    ): RollRecord {
        val ranked = if (spec.keepLowest != null) effective.sorted() else effective.sortedDescending()
        val keepCount = spec.keepHighest ?: spec.keepLowest ?: effective.size
        val kept = ranked.take(keepCount)
        val dropped = ranked.drop(keepCount)
        val impact = when {
            effective.size == 1 && spec.sides == 20 && kept.first() == 20 -> Impact.CRITICAL_SUCCESS
            effective.size == 1 && spec.sides == 20 && kept.first() == 1 -> Impact.CRITICAL_FAILURE
            else -> Impact.NORMAL
        }
        return RollRecord(
            notation = notation ?: spec.toNotation(),
            rolls = physical,
            kept = kept,
            dropped = dropped,
            modifier = spec.modifier,
            total = kept.sum() + spec.modifier,
            impact = impact,
        ).also { _history.add(it) }
    }

    fun parse(notation: String): DiceSpec {
        val match = notationPattern.matchEntire(notation.trim())
            ?: throw IllegalArgumentException("Invalid notation: $notation")
        val count = match.groupValues[1].ifEmpty { "1" }.toInt()
        val sides = match.groupValues[2].toInt()
        val keepKind = match.groupValues[3]
        val keepCount = match.groupValues[4].ifEmpty { null }?.toInt()
        val modifier = match.groupValues[5].ifEmpty { "0" }.toInt()
        val advantage = when (match.groupValues[6].lowercase()) {
            "adv" -> Advantage.ADVANTAGE
            "dis" -> Advantage.DISADVANTAGE
            else -> Advantage.STRAIGHT
        }
        require(count in 1..100 && sides in 2..1000) { "Invalid notation: $notation" }
        if (keepCount != null) {
            require(keepCount in 1..count) { "Invalid notation: $notation" }
        }
        if (advantage != Advantage.STRAIGHT) {
            require(count == 1 && sides == 20) { "Invalid notation: $notation" }
        }
        return DiceSpec(
            count = count,
            sides = sides,
            keepHighest = if (keepKind == "kh") keepCount else null,
            keepLowest = if (keepKind == "kl") keepCount else null,
            modifier = modifier,
            advantage = advantage,
        )
    }

    private fun die(sides: Int): Int = random.nextInt(1, sides + 1)

    private fun DiceSpec.toNotation(): String = buildString {
        append("${count}d$sides")
        if (keepHighest != null) append("kh$keepHighest")
        if (keepLowest != null) append("kl$keepLowest")
        if (modifier > 0) append("+$modifier")
        if (modifier < 0) append("$modifier")
        if (advantage == Advantage.ADVANTAGE) append("adv")
        if (advantage == Advantage.DISADVANTAGE) append("dis")
    }
}
