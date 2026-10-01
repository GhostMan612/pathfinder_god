// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.pathfindergod.spoke.R
import com.pathfindergod.spoke.data.repository.MAX_ROLL_HISTORY
import com.pathfindergod.spoke.data.repository.RollRepository
import com.pathfindergod.spoke.service.AudioService
import com.pathfindergod.spoke.ui.dice.Advantage
import com.pathfindergod.spoke.ui.dice.DiceEngine
import com.pathfindergod.spoke.ui.dice.DiceSpec
import com.pathfindergod.spoke.ui.dice.Die
import com.pathfindergod.spoke.ui.dice.Impact
import com.pathfindergod.spoke.ui.dice.RollRecord
import com.pathfindergod.spoke.ui.strings.UiText
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

const val MAX_DICE_COUNT = 20
const val MAX_MODIFIER = 20
const val MAX_TARGET_NUMBER = 40

data class RollEntry(
    val key: Long,
    val record: RollRecord,
)

data class DiceUiState(
    val die: Die = Die.D20,
    val count: Int = 1,
    val advantage: Advantage = Advantage.STRAIGHT,
    val keepHighest: Int? = null,
    val modifier: Int = 0,
    val exploding: Boolean = false,
    val targetNumber: Int? = null,
    val record: RollRecord? = null,
    val history: List<RollEntry> = emptyList(),
    val rollToken: Int = 0,
    val error: UiText? = null,
) {
    val sides: Int get() = die.sides
    val face: Int get() = record?.kept?.firstOrNull() ?: die.sides
    val supportsAdvantage: Boolean get() = die == Die.D20 && count == 1
    val supportsKeep: Boolean get() = count > 1

    fun spec(): DiceSpec = DiceSpec(
        count = count,
        sides = die.sides,
        keepHighest = keepHighest,
        modifier = modifier,
        advantage = if (supportsAdvantage) advantage else Advantage.STRAIGHT,
        exploding = exploding,
    )

    fun notation(): String = spec().notation()
}

class DiceViewModel(
    private val repository: RollRepository,
    private val audio: AudioService,
    private val engine: DiceEngine = DiceEngine(),
) : ViewModel() {
    private val _state = MutableStateFlow(DiceUiState())
    val state: StateFlow<DiceUiState> = _state.asStateFlow()

    private var sequence = 0L

    init {
        viewModelScope.launch { restoreHistory() }
    }

    fun selectDie(die: Die) {
        val current = _state.value
        _state.value = if (die == current.die) {
            current
        } else {
            current.copy(die = die, advantage = Advantage.STRAIGHT)
        }
    }

    fun setCount(count: Int) {
        val current = _state.value
        val bounded = count.coerceIn(1, MAX_DICE_COUNT)
        val keep = current.keepHighest?.coerceIn(1, bounded)
        _state.value = current.copy(count = bounded, keepHighest = keep)
    }

    fun setModifier(modifier: Int) {
        val bounded = modifier.coerceIn(-MAX_MODIFIER, MAX_MODIFIER)
        _state.value = _state.value.copy(modifier = bounded)
    }

    fun setAdvantage(advantage: Advantage) {
        val current = _state.value
        if (!current.supportsAdvantage && advantage != Advantage.STRAIGHT) return
        _state.value = current.copy(advantage = advantage)
    }

    fun setKeepHighest(count: Int?) {
        val current = _state.value
        val bounded = count?.coerceIn(1, current.count)
        _state.value = current.copy(keepHighest = bounded)
    }

    fun setExploding(exploding: Boolean) {
        _state.value = _state.value.copy(exploding = exploding)
    }

    fun setTargetNumber(target: Int?) {
        val bounded = target?.coerceIn(1, MAX_TARGET_NUMBER)
        _state.value = _state.value.copy(targetNumber = bounded)
    }

    fun roll() {
        val current = _state.value
        val rolled = try {
            engine.withDegree(engine.roll(current.spec()), current.targetNumber)
        } catch (_: IllegalArgumentException) {
            _state.value = current.copy(
                error = UiText.Resource(R.string.dice_notation_rejected),
            )
            audio.playError()
            return
        }
        val stamped = rolled.copy(rolledAt = System.currentTimeMillis())
        val entry = RollEntry(key = ++sequence, record = stamped)
        _state.value = current.copy(
            record = stamped,
            history = (listOf(entry) + current.history).take(MAX_ROLL_HISTORY),
            rollToken = current.rollToken + 1,
            error = null,
        )
        audio.buttonPress()
        viewModelScope.launch {
            runCatching { repository.persist(stamped) }
        }
    }

    fun playImpact() {
        val record = _state.value.record ?: return
        val sides = _state.value.sides
        when (record.impact) {
            Impact.CRITICAL_SUCCESS -> audio.playCritChime(sides)
            Impact.CRITICAL_FAILURE -> audio.playFumble(sides)
            Impact.NORMAL -> audio.playClatter(sides, record.rolls.size)
        }
    }

    fun clearHistory() {
        _state.value = _state.value.copy(history = emptyList())
        viewModelScope.launch { runCatching { repository.clear() } }
    }

    private suspend fun restoreHistory() {
        val rows = runCatching { repository.recent(MAX_ROLL_HISTORY) }
            .getOrDefault(emptyList())
        if (rows.isEmpty()) return
        val fresh = _state.value.history.map { it.record }
        val unseen = rows.filter { row ->
            fresh.none { it.rolledAt == row.rolledAt && it.notation == row.notation }
        }
        if (unseen.isEmpty()) return
        val restored = unseen.reversed().mapIndexed { index, record ->
            RollEntry(key = -(index + 1L), record = record)
        }
        _state.value = _state.value.copy(
            history = (_state.value.history + restored).takeLast(MAX_ROLL_HISTORY),
        )
    }
}
