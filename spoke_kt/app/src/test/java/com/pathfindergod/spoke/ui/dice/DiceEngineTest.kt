// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.dice

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.random.Random

private class FixedRandom(private val values: IntArray) : Random() {
    private var index = 0
    override fun nextBits(bitCount: Int): Int {
        val value = values[index % values.size]
        index++
        return if (bitCount >= 32) value else value and ((1 shl bitCount) - 1)
    }
}

private fun rawFor(sides: Int, face: Int): Int {
    var candidate = 0
    while (candidate < 2 * sides) {
        val probe = DiceEngine(FixedRandom(intArrayOf(candidate)))
        if (probe.roll("d$sides").kept.single() == face) return candidate
        candidate++
    }
    throw AssertionError("No scripted value produces $face on d$sides")
}

private fun scripted(sides: Int, vararg faces: Int): DiceEngine =
    DiceEngine(FixedRandom(IntArray(faces.size) { rawFor(sides, faces[it]) }))

private fun d20(vararg faces: Int): DiceEngine = scripted(20, *faces)

class DiceEngineTest {

    @Test
    fun parseSimpleNotation() {
        val engine = DiceEngine()
        assertEquals(DiceSpec(count = 2, sides = 6, modifier = 3), engine.parse("2d6+3"))
        assertEquals(DiceSpec(count = 1, sides = 20), engine.parse("d20"))
        assertEquals(DiceSpec(count = 1, sides = 8, modifier = -1), engine.parse("d8-1"))
    }

    @Test
    fun parseKeepNotation() {
        val engine = DiceEngine()
        assertEquals(DiceSpec(count = 4, sides = 6, keepHighest = 3), engine.parse("4d6kh3"))
        assertEquals(DiceSpec(count = 4, sides = 6, keepLowest = 2), engine.parse("4d6kl2"))
    }

    @Test
    fun parseAdvantageNotation() {
        val engine = DiceEngine()
        assertEquals(Advantage.ADVANTAGE, engine.parse("d20adv").advantage)
        assertEquals(Advantage.DISADVANTAGE, engine.parse("D20DIS").advantage)
        assertEquals(Advantage.STRAIGHT, engine.parse("d20").advantage)
    }

    @Test
    fun parseRejectsInvalidNotation() {
        val engine = DiceEngine()
        listOf(
            "x",
            "d",
            "2d",
            "d6kh",
            "2d6kh5",
            "2d6adv",
            "3d8dis",
            "0d6",
            "d1",
            "101d6",
            "d1001",
            "d20kh0",
            "d6+",
            "2d6 3",
        ).forEach {
            try {
                engine.parse(it)
                throw AssertionError("Expected rejection of $it")
            } catch (expected: IllegalArgumentException) {
                assertTrue(expected.message!!.startsWith("Invalid notation"))
            }
        }
    }

    @Test
    fun rollStaysWithinBounds() {
        val engine = DiceEngine(Random(7))
        repeat(200) {
            val record = engine.roll("3d8+2")
            assertEquals(3, record.kept.size)
            assertEquals(record.kept.sum() + 2, record.total)
            assertTrue(record.total in 5..26)
        }
    }

    @Test
    fun keepHighestDropsLowestDie() {
        val engine = DiceEngine(Random(11))
        repeat(100) {
            val record = engine.roll("4d6kh3")
            assertEquals(3, record.kept.size)
            assertEquals(1, record.dropped.size)
            assertEquals(record.kept.sum(), record.total)
            assertTrue(record.kept.min() >= record.dropped.max())
        }
    }

    @Test
    fun advantageKeepsHigherDie() {
        val engine = DiceEngine(FixedRandom(intArrayOf(39, 1)))
        val record = engine.roll("d20adv")
        assertEquals(listOf(20, 1), record.rolls)
        assertEquals(listOf(20), record.kept)
        assertEquals(20, record.total)
        assertEquals(Impact.CRITICAL_SUCCESS, record.impact)
    }

    @Test
    fun disadvantageKeepsLowerDie() {
        val engine = DiceEngine(FixedRandom(intArrayOf(39, 1)))
        val record = engine.roll("d20dis")
        assertEquals(listOf(20, 1), record.rolls)
        assertEquals(listOf(1), record.kept)
        assertEquals(1, record.total)
        assertEquals(Impact.CRITICAL_FAILURE, record.impact)
    }

    @Test
    fun naturalTwentyAndOneSetImpact() {
        val crit = DiceEngine(FixedRandom(intArrayOf(39)))
        assertEquals(Impact.CRITICAL_SUCCESS, crit.roll("d20").impact)
        val fail = DiceEngine(FixedRandom(intArrayOf(1)))
        assertEquals(Impact.CRITICAL_FAILURE, fail.roll("d20").impact)
        val normal = DiceEngine(Random(3))
        assertEquals(Impact.NORMAL, normal.roll("2d6").impact)
    }

    @Test
    fun engineHoldsNoRollHistory() {
        val first = d20(20, 3).roll("d20adv")
        val second = d20(20, 3).roll("d20adv")
        assertEquals(first, second)
        val engine = d20(20, 3)
        val opening = engine.roll("d20adv")
        val again = engine.roll("d20adv")
        assertEquals(opening, again)
    }

    @Test
    fun advantageNatTwentyIsCriticalSuccess() {
        val record = d20(20, 7).roll("d20adv")
        assertEquals(listOf(20, 7), record.rolls)
        assertEquals(listOf(20), record.kept)
        assertEquals(listOf(7), record.dropped)
        assertEquals(20, record.total)
        assertEquals(Impact.CRITICAL_SUCCESS, record.impact)
    }

    @Test
    fun advantageNatOneIsCancelledByHigherDie() {
        val record = d20(1, 15).roll("d20adv")
        assertEquals(listOf(15), record.kept)
        assertEquals(listOf(1), record.dropped)
        assertEquals(15, record.total)
        assertEquals(Impact.NORMAL, record.impact)
    }

    @Test
    fun advantageDoubleOneIsCriticalFailure() {
        val record = d20(1, 1).roll("d20adv")
        assertEquals(listOf(1), record.kept)
        assertEquals(Impact.CRITICAL_FAILURE, record.impact)
    }

    @Test
    fun disadvantageNatTwentyRequiresBothDice() {
        val record = d20(20, 15).roll("d20dis")
        assertEquals(listOf(15), record.kept)
        assertEquals(listOf(20), record.dropped)
        assertEquals(Impact.NORMAL, record.impact)
    }

    @Test
    fun disadvantageDoubleTwentyIsCriticalSuccess() {
        val record = d20(20, 20).roll("d20dis")
        assertEquals(listOf(20), record.kept)
        assertEquals(Impact.CRITICAL_SUCCESS, record.impact)
    }

    @Test
    fun naturalTwentyInD20PoolIsCriticalSuccess() {
        val record = d20(20, 7).roll("2d20kh1")
        assertEquals(listOf(20), record.kept)
        assertEquals(listOf(7), record.dropped)
        assertEquals(20, record.total)
        assertEquals(Impact.CRITICAL_SUCCESS, record.impact)
    }

    @Test
    fun naturalOneInD20PoolIsCriticalFailure() {
        val record = d20(20, 1).roll("2d20kl1")
        assertEquals(listOf(1), record.kept)
        assertEquals(listOf(20), record.dropped)
        assertEquals(1, record.total)
        assertEquals(Impact.CRITICAL_FAILURE, record.impact)
    }

    @Test
    fun d20PoolKeepsTheHighestNaturalTwenty() {
        val record = d20(20, 20, 4).roll("3d20kh2")
        assertEquals(listOf(20, 20), record.kept)
        assertEquals(listOf(4), record.dropped)
        assertEquals(Impact.CRITICAL_SUCCESS, record.impact)
    }

    @Test
    fun nonD20MaximumIsNeverCritical() {
        val record = scripted(6, 6, 6).roll("2d6")
        assertEquals(listOf(6, 6), record.kept)
        assertEquals(12, record.total)
        assertEquals(Impact.NORMAL, record.impact)
    }

    @Test
    fun advantageCritIgnoresNegativeModifier() {
        val record = d20(20, 3).roll("d20adv-5")
        assertEquals(listOf(20), record.kept)
        assertEquals(15, record.total)
        assertEquals(Impact.CRITICAL_SUCCESS, record.impact)
    }

    @Test
    fun parseModifierAlongsideAdvantage() {
        val engine = DiceEngine()
        val early = engine.parse("d20adv+5")
        assertEquals(5, early.modifier)
        assertEquals(Advantage.ADVANTAGE, early.advantage)
        val late = engine.parse("d20+5adv")
        assertEquals(5, late.modifier)
        assertEquals(Advantage.ADVANTAGE, late.advantage)
        val dis = engine.parse("d20dis-2")
        assertEquals(-2, dis.modifier)
        assertEquals(Advantage.DISADVANTAGE, dis.advantage)
    }

    @Test
    fun poolWithModifierTotalsCorrectly() {
        val record = scripted(6, 6, 5, 4, 1).roll("4d6kh3+2")
        assertEquals(3, record.kept.size)
        assertEquals(listOf(6, 5, 4), record.kept)
        assertEquals(listOf(1), record.dropped)
        assertEquals(17, record.total)
        assertEquals("4d6kh3+2", record.notation)
    }

    @Test
    fun poolKeepLowestDropsTheHighestDice() {
        val record = scripted(6, 6, 5, 4, 3).roll("4d6kl2")
        assertEquals(listOf(3, 4), record.kept)
        assertEquals(listOf(6, 5), record.dropped)
        assertEquals(7, record.total)
    }

    @Test
    fun poolWithoutKeepKeepsEveryDie() {
        val record = scripted(8, 8, 3, 5, 6).roll("4d8")
        assertEquals(4, record.kept.size)
        assertTrue(record.dropped.isEmpty())
        assertEquals(22, record.total)
    }

    @Test
    fun straightRollReportsNoDroppedDice() {
        val record = d20(7).roll("d20")
        assertEquals(listOf(7), record.rolls)
        assertEquals(listOf(7), record.kept)
        assertTrue(record.dropped.isEmpty())
    }

    @Test
    fun notationRoundTripsThroughParse() {
        val engine = DiceEngine()
        listOf(
            "d20",
            "2d6+3",
            "d8-1",
            "4d6kh3",
            "4d6kl2",
            "d20adv",
            "d20dis",
            "d6!!",
            "2d6!!kh1+2",
            "d20kh1adv",
        ).forEach { text ->
            val spec = engine.parse(text)
            assertEquals(text, spec.notation())
            assertEquals(spec, engine.parse(spec.notation()))
        }
    }

    @Test
    fun explodingDieRerollsOnMaximum() {
        val record = scripted(6, 6, 3).roll("d6!!")
        assertEquals(listOf(6, 3), record.rolls)
        assertEquals(listOf(6, 3), record.kept)
        assertTrue(record.dropped.isEmpty())
        assertEquals(9, record.total)
    }

    @Test
    fun explodingChainAccumulatesEveryFace() {
        val record = scripted(6, 6, 6, 6, 6, 2).roll("d6!!")
        assertEquals(listOf(6, 6, 6, 6, 2), record.rolls)
        assertEquals(listOf(6, 6, 6, 6, 2), record.kept)
        assertEquals(26, record.total)
    }

    @Test
    fun plainDieNeverExplodes() {
        val record = scripted(6, 6).roll("d6")
        assertEquals(listOf(6), record.rolls)
        assertEquals(6, record.total)
    }

    @Test
    fun explodingPoolAddsFacesToThePool() {
        val record = scripted(6, 6, 3, 5).roll("2d6!!kh1")
        assertEquals(listOf(6, 3, 5), record.rolls)
        assertEquals(listOf(6), record.kept)
        assertEquals(listOf(5, 3), record.dropped)
        assertEquals(6, record.total)
    }

    @Test
    fun explodingChainIsCapped() {
        val record = scripted(6, 6, 6, 6, 6, 6).roll("d6!!")
        assertEquals(1 + MAX_EXPLOSIONS, record.rolls.size)
        assertEquals(1 + MAX_EXPLOSIONS, record.kept.size)
        assertEquals(6 * (1 + MAX_EXPLOSIONS), record.total)
    }

    @Test
    fun explodingNotationIsParsedAndFlagged() {
        val engine = DiceEngine()
        val spec = engine.parse("2d6!!kh1+2")
        assertTrue(spec.exploding)
        assertEquals(2, spec.count)
        assertEquals(1, spec.keepHighest)
        assertEquals(2, spec.modifier)
        assertTrue(engine.parse("2d6").exploding.not())
    }

    @Test
    fun explodingNonD20DiceNeverCrit() {
        val record = scripted(10, 10, 3).roll("d10!!")
        assertEquals(listOf(10, 3), record.kept)
        assertEquals(13, record.total)
        assertEquals(Impact.NORMAL, record.impact)
    }

    @Test
    fun modifierAppliesToTotalNotToTheDie() {
        val record = scripted(8, 1).roll("d8-1")
        assertEquals(listOf(1), record.kept)
        assertEquals(0, record.total)
    }

    @Test
    fun degreeOfSuccessComparesAgainstTarget() {
        val engine = DiceEngine()
        val plain = d20(14).roll("d20")
        assertEquals(DegreeOfSuccess.FAILURE, engine.degreeOfSuccess(plain, 15))
        assertEquals(DegreeOfSuccess.SUCCESS, engine.degreeOfSuccess(plain, 14))
        assertEquals(
            DegreeOfSuccess.FAILURE,
            engine.degreeOfSuccess(d20(9).roll("d20+4"), 15),
        )
        assertEquals(
            DegreeOfSuccess.SUCCESS,
            engine.degreeOfSuccess(d20(9).roll("d20+4"), 13),
        )
        assertEquals(
            DegreeOfSuccess.CRITICAL_SUCCESS,
            engine.degreeOfSuccess(d20(9).roll("d20+4"), 3),
        )
        assertEquals(
            DegreeOfSuccess.CRITICAL_SUCCESS,
            engine.degreeOfSuccess(d20(14).roll("d20"), 4),
        )
    }

    @Test
    fun naturalTwentyIsAlwaysCriticalSuccessInTwoE() {
        val engine = DiceEngine()
        val record = d20(20).roll("d20")
        assertEquals(
            DegreeOfSuccess.CRITICAL_SUCCESS,
            engine.degreeOfSuccess(record, 30),
        )
    }

    @Test
    fun naturalOneIsAlwaysCriticalFailureInTwoE() {
        val engine = DiceEngine()
        val record = d20(1).roll("d20+10")
        assertEquals(11, record.total)
        assertEquals(
            DegreeOfSuccess.CRITICAL_FAILURE,
            engine.degreeOfSuccess(record, 5),
        )
    }

    @Test
    fun degreeUsesBestKeptDieOfAPool() {
        val engine = DiceEngine()
        val record = scripted(6, 6, 3).roll("2d6kh1")
        assertEquals(listOf(6), record.kept)
        assertEquals(DegreeOfSuccess.SUCCESS, engine.degreeOfSuccess(record, 6))
        assertEquals(DegreeOfSuccess.FAILURE, engine.degreeOfSuccess(record, 11))
        val boosted = scripted(6, 6).roll("d6+6")
        assertEquals(
            DegreeOfSuccess.CRITICAL_SUCCESS,
            engine.degreeOfSuccess(boosted, 1),
        )
    }

    @Test
    fun degreeIsAbsentWithoutATarget() {
        val engine = DiceEngine()
        val record = d20(11).roll("d20")
        val untargeted = engine.withDegree(record, null)
        assertNull(untargeted.degree)
        assertNull(untargeted.targetNumber)
        val targeted = engine.withDegree(record, 12)
        assertEquals(12, targeted.targetNumber)
        assertEquals(DegreeOfSuccess.FAILURE, targeted.degree)
    }

    @Test
    fun specAndRecordCarryStableIdentifiers() {
        val record = d20(20).roll("d20")
        assertEquals(0L, record.id)
        assertEquals(0L, record.rolledAt)
        assertEquals(record.copy(id = 7L, rolledAt = 42L).id, 7L)
        assertEquals(record.copy(id = 7L, rolledAt = 42L).rolledAt, 42L)
    }

    @Test
    fun everyDieInTheEnumRolls() {
        val engine = DiceEngine(Random(19))
        Die.entries.forEach { die ->
            val record = engine.roll("d${die.sides}")
            assertEquals(1, record.kept.size)
            assertTrue(record.kept.single() in 1..die.sides)
        }
    }

    @Test
    fun diceExpressionSeparatesModifier() {
        val joiner = " + "
        assertEquals(
            "6 + 5 + 4 + 2",
            DiceLabels.expression(listOf(6, 5, 4), joiner, "+2"),
        )
        assertEquals(
            "6 + 5 + 4 - 2",
            DiceLabels.expression(listOf(6, 5, 4), joiner, "-2"),
        )
        assertEquals("14", DiceLabels.expression(listOf(14), joiner, null))
        assertEquals("", DiceLabels.expression(emptyList(), joiner, "+2"))
    }

    @Test
    fun diceExpressionNeverGluesDigitsToModifier() {
        val record = d20(14).roll("d20-2")
        val expression = DiceLabels.expression(record.kept, " ", "-2")
        assertEquals("14 -2", expression)
        assertFalse(expression.contains("14-2"))
        assertTrue(DiceLabels.dice(record.dropped, " ").isNotEmpty().not())
    }

    @Test
    fun droppedDiceAreLabelled() {
        val record = d20(20, 3).roll("d20adv")
        assertEquals("3", DiceLabels.dice(record.dropped, " + "))
        assertEquals("20 + 3", DiceLabels.dice(record.rolls, " + "))
    }
}
