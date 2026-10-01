// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.dice

object DiceLabels {
    fun expression(kept: List<Int>, joiner: String, modifier: String?): String {
        val dice = kept.joinToString(joiner)
        if (dice.isEmpty() || modifier == null || modifier.isEmpty()) return dice
        val sign = modifier.first()
        val magnitude = modifier.drop(1)
        val slot = joiner.indexOfFirst { !it.isWhitespace() }
        val operator = if (slot >= 0) {
            joiner.substring(0, slot) + sign + joiner.substring(slot + 1)
        } else {
            joiner.takeWhile { it.isWhitespace() } + sign
        }
        return dice + operator + magnitude
    }

    fun dice(rolls: List<Int>, joiner: String): String = rolls.joinToString(joiner)
}
