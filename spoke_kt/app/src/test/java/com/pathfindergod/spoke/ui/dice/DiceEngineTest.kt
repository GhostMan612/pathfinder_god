// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.dice

import org.junit.Assert.assertEquals
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
        listOf("x", "d", "2d", "d6kh", "2d6kh5", "2d6adv", "3d8dis", "0d6", "d1").forEach {
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
    fun historyAccumulatesAndClears() {
        val engine = DiceEngine(Random(5))
        engine.roll("d6")
        engine.roll("d8+1")
        assertEquals(2, engine.history.size)
        assertEquals("d6", engine.history[0].notation)
        engine.clearHistory()
        assertTrue(engine.history.isEmpty())
    }
}
