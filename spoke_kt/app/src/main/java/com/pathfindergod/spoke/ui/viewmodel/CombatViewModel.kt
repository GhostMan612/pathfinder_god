// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.viewmodel

import androidx.lifecycle.ViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

data class CombatCondition(
    val name: String,
    val value: Int = 1,
    val durationRounds: Int? = null,
)

data class Combatant(
    val id: String,
    val name: String,
    val isPc: Boolean = false,
    val initiative: Int = 0,
    val currentHp: Int = 0,
    val maxHp: Int = 0,
    val tempHp: Int = 0,
    val ac: Int = 10,
    val conditions: List<CombatCondition> = emptyList(),
)

data class CombatUiState(
    val combatants: List<Combatant> = emptyList(),
    val activeIndex: Int = 0,
    val currentRound: Int = 1,
    val lastNotes: String = "",
    val isProcessing: Boolean = false,
)

class CombatViewModel : ViewModel() {
    private val _state = MutableStateFlow(CombatUiState())
    val state: StateFlow<CombatUiState> = _state.asStateFlow()

    val activeCombatant: Combatant?
        get() = _state.value.combatants.getOrNull(_state.value.activeIndex)

    fun addCombatant(combatant: Combatant) {
        val sorted = (_state.value.combatants + combatant)
            .sortedByDescending { it.initiative }
        _state.value = _state.value.copy(combatants = sorted)
    }

    fun removeCombatant(id: String) {
        val remaining = _state.value.combatants.filterNot { it.id == id }
        val index = _state.value.activeIndex.coerceAtMost(
            (remaining.size - 1).coerceAtLeast(0),
        )
        _state.value = _state.value.copy(
            combatants = remaining,
            activeIndex = index,
        )
    }

    fun updateHp(id: String, delta: Int) {
        _state.value = _state.value.copy(
            combatants = _state.value.combatants.map {
                if (it.id == id) {
                    it.copy(currentHp = (it.currentHp + delta).coerceIn(0, it.maxHp))
                } else {
                    it
                }
            },
        )
    }

    fun addCondition(id: String, condition: CombatCondition) {
        _state.value = _state.value.copy(
            combatants = _state.value.combatants.map {
                if (it.id == id) {
                    it.copy(conditions = it.conditions + condition)
                } else {
                    it
                }
            },
        )
    }

    fun removeCondition(id: String, name: String) {
        _state.value = _state.value.copy(
            combatants = _state.value.combatants.map {
                if (it.id == id) {
                    it.copy(conditions = it.conditions.filterNot { c -> c.name == name })
                } else {
                    it
                }
            },
        )
    }

    fun nextTurn(): String {
        val current = _state.value
        if (current.combatants.isEmpty() || current.isProcessing) return ""
        val notes = StringBuilder()
        val ticked = current.combatants.mapIndexed { index, combatant ->
            if (index != current.activeIndex) {
                combatant
            } else {
                combatant.copy(conditions = tickConditions(combatant, notes))
            }
        }
        val nextIndex = current.activeIndex + 1
        val wrapped = nextIndex >= ticked.size
        _state.value = current.copy(
            combatants = ticked,
            activeIndex = if (wrapped) 0 else nextIndex,
            currentRound = if (wrapped) current.currentRound + 1 else current.currentRound,
            lastNotes = notes.toString().trim(),
        )
        return _state.value.lastNotes
    }

    private fun tickConditions(
        combatant: Combatant,
        notes: StringBuilder,
    ): List<CombatCondition> {
        val kept = mutableListOf<CombatCondition>()
        for (cond in combatant.conditions) {
            when {
                cond.name.startsWith("Persistent", ignoreCase = true) -> {
                    kept.add(cond)
                    notes.append(combatant.name).append(": ").append(cond.name)
                        .append(" persists. ")
                }
                cond.name.equals("frightened", ignoreCase = true) -> {
                    if (cond.value > 1) {
                        kept.add(cond.copy(value = cond.value - 1))
                    } else {
                        notes.append(combatant.name).append(" shakes off Frightened. ")
                    }
                }
                cond.durationRounds != null -> {
                    val remaining = cond.durationRounds - 1
                    if (remaining > 0) {
                        kept.add(cond.copy(durationRounds = remaining))
                    } else {
                        notes.append(combatant.name).append(": ").append(cond.name)
                            .append(" expires. ")
                    }
                }
                else -> kept.add(cond)
            }
        }
        return kept
    }

    fun clearEncounter() {
        _state.value = CombatUiState()
    }
}
