// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.pathfindergod.spoke.data.local.EncounterEntity
import com.pathfindergod.spoke.data.network.EncounterMonster
import com.pathfindergod.spoke.data.repository.EncounterRepository
import com.pathfindergod.spoke.ui.dice.DiceEngine
import java.util.UUID
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.serialization.json.Json

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

class CombatViewModel(
    private val encounters: EncounterRepository,
) : ViewModel() {
    private val json = Json { ignoreUnknownKeys = true }
    private val _state = MutableStateFlow(CombatUiState())
    val state: StateFlow<CombatUiState> = _state.asStateFlow()

    private val _vault = MutableStateFlow(emptyList<EncounterEntity>())
    val vault: StateFlow<List<EncounterEntity>> = _vault.asStateFlow()

    init {
        viewModelScope.launch {
            encounters.observeEncounters().collect { _vault.value = it }
        }
    }

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

    fun loadEncounter(id: String) {
        viewModelScope.launch {
            val target = try {
                encounters.getEncounters().firstOrNull { it.id == id }
            } catch (_: Exception) {
                null
            } ?: return@launch
            val monsters = try {
                json.decodeFromString<List<EncounterMonster>>(target.monstersJson)
            } catch (_: Exception) {
                emptyList()
            }
            if (monsters.isEmpty()) return@launch
            val dice = DiceEngine()
            val ladder = monsters.flatMap { monster ->
                List(monster.count.coerceIn(1, 12)) { index ->
                    val hp = 10 + monster.level * 5
                    Combatant(
                        id = UUID.randomUUID().toString(),
                        name = if (monster.count > 1) {
                            "${monster.name} ${index + 1}"
                        } else {
                            monster.name
                        },
                        isPc = false,
                        initiative = dice.roll("1d20").total,
                        currentHp = hp,
                        maxHp = hp,
                    )
                }
            }.sortedByDescending { it.initiative }
            _state.value = CombatUiState(
                combatants = ladder,
                activeIndex = 0,
                currentRound = 1,
                lastNotes = "",
            )
        }
    }
}
