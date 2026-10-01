// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.dice

import kotlin.random.Random

const val MAX_EXPLOSIONS = 20
const val CRITICAL_MARGIN = 10

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

enum class DegreeOfSuccess {
    CRITICAL_FAILURE,
    FAILURE,
    SUCCESS,
    CRITICAL_SUCCESS,
}

data class DiceSpec(
    val count: Int = 1,
    val sides: Int = 20,
    val keepHighest: Int? = null,
    val keepLowest: Int? = null,
    val modifier: Int = 0,
    val advantage: Advantage = Advantage.STRAIGHT,
    val exploding: Boolean = false,
) {
    fun notation(): String = buildString {
        if (count != 1) append(count)
        append("d$sides")
        if (exploding) append("!!")
        if (keepHighest != null) append("kh$keepHighest")
        if (keepLowest != null) append("kl$keepLowest")
        if (modifier > 0) append("+$modifier")
        if (modifier < 0) append("$modifier")
        if (advantage == Advantage.ADVANTAGE) append("adv")
        if (advantage == Advantage.DISADVANTAGE) append("dis")
    }
}

data class RollRecord(
    val notation: String,
    val rolls: List<Int>,
    val kept: List<Int>,
    val dropped: List<Int>,
    val modifier: Int,
    val total: Int,
    val impact: Impact,
    val id: Long = 0L,
    val rolledAt: Long = 0L,
    val targetNumber: Int? = null,
    val degree: DegreeOfSuccess? = null,
)

class DiceEngine(private val random: Random = Random.Default) {

    private val notationPattern = Regex(
        """^(\d*)d(\d+)(!!)?(?:(adv|dis))?(?:(kh|kl)(\d+))?([+-]\d+)?(?:(adv|dis))?$""",
        RegexOption.IGNORE_CASE,
    )

    fun roll(notation: String): RollRecord = roll(parse(notation), notation)

    fun roll(spec: DiceSpec, notation: String? = null): RollRecord {
        val raw = mutableListOf<Int>()
        val cancelled = mutableListOf<Int>()
        val base = mutableListOf<Int>()
        repeat(spec.count.coerceAtLeast(0)) {
            val first = die(spec.sides)
            raw += first
            val face = when (spec.advantage) {
                Advantage.STRAIGHT -> first
                else -> {
                    val second = die(spec.sides)
                    raw += second
                    val best = if (spec.advantage == Advantage.ADVANTAGE) {
                        maxOf(first, second)
                    } else {
                        minOf(first, second)
                    }
                    cancelled += if (best == first) second else first
                    best
                }
            }
            base += face
        }
        val pool = base.toMutableList()
        if (spec.exploding) {
            base.forEach { seed ->
                var face = seed
                var guard = 0
                while (face == spec.sides && guard < MAX_EXPLOSIONS) {
                    face = die(spec.sides)
                    raw += face
                    pool += face
                    guard++
                }
            }
        }
        val keepLowest = spec.keepLowest != null
        val ranked = if (keepLowest) pool.sorted() else pool.sortedDescending()
        val keepCount = (spec.keepHighest ?: spec.keepLowest ?: pool.size)
            .coerceIn(0, ranked.size)
        val kept = ranked.take(keepCount)
        val dropped = (cancelled + ranked.drop(keepCount)).sortedDescending()
        return RollRecord(
            notation = notation ?: spec.notation(),
            rolls = raw,
            kept = kept,
            dropped = dropped,
            modifier = spec.modifier,
            total = kept.sum() + spec.modifier,
            impact = impactFor(spec, kept),
        )
    }

    fun parse(notation: String): DiceSpec {
        val match = notationPattern.matchEntire(notation.trim())
            ?: invalid(notation)
        val count = match.groupValues[1].ifEmpty { "1" }.toInt()
        val sides = match.groupValues[2].toInt()
        val exploding = match.groupValues[3] == "!!"
        val keepKind = match.groupValues[5].lowercase()
        val keepCount = match.groupValues[6].ifEmpty { null }?.toInt()
        val modifier = match.groupValues[7].ifEmpty { "0" }.toInt()
        val advToken = match.groupValues[8].ifEmpty { match.groupValues[4] }
            .lowercase()
        val advantage = when (advToken) {
            "adv" -> Advantage.ADVANTAGE
            "dis" -> Advantage.DISADVANTAGE
            else -> Advantage.STRAIGHT
        }
        require(count in 1..100 && sides in 2..1000) { invalidMessage(notation) }
        if (keepCount != null) {
            require(keepCount in 1..count) { invalidMessage(notation) }
        }
        if (advantage != Advantage.STRAIGHT) {
            require(count == 1 && sides == 20) { invalidMessage(notation) }
        }
        return DiceSpec(
            count = count,
            sides = sides,
            keepHighest = if (keepKind == "kh") keepCount else null,
            keepLowest = if (keepKind == "kl") keepCount else null,
            modifier = modifier,
            advantage = advantage,
            exploding = exploding,
        )
    }

    fun withDegree(record: RollRecord, targetNumber: Int?): RollRecord {
        if (targetNumber == null) return record
        return record.copy(
            targetNumber = targetNumber,
            degree = degreeOfSuccess(record, targetNumber),
        )
    }

    fun degreeOfSuccess(record: RollRecord, targetNumber: Int): DegreeOfSuccess {
        val best = record.kept.maxOrNull() ?: 0
        val result = best + record.modifier
        return when {
            best >= 20 -> DegreeOfSuccess.CRITICAL_SUCCESS
            best <= 1 -> DegreeOfSuccess.CRITICAL_FAILURE
            result >= targetNumber + CRITICAL_MARGIN -> DegreeOfSuccess.CRITICAL_SUCCESS
            result >= targetNumber -> DegreeOfSuccess.SUCCESS
            else -> DegreeOfSuccess.FAILURE
        }
    }

    private fun impactFor(spec: DiceSpec, kept: List<Int>): Impact = when {
        spec.sides != 20 || kept.isEmpty() -> Impact.NORMAL
        kept.any { it == 20 } -> Impact.CRITICAL_SUCCESS
        kept.any { it == 1 } -> Impact.CRITICAL_FAILURE
        else -> Impact.NORMAL
    }

    private fun die(sides: Int): Int = random.nextInt(1, sides + 1)

    private fun invalid(notation: String): Nothing =
        throw IllegalArgumentException(invalidMessage(notation))

    private fun invalidMessage(notation: String): String = "Invalid notation: $notation"
}
