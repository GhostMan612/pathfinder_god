// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.pathfindergod.spoke.data.local.EncounterEntity
import com.pathfindergod.spoke.data.network.EncounterMonster
import com.pathfindergod.spoke.data.network.EncounterRequest
import com.pathfindergod.spoke.data.network.HubApi
import com.pathfindergod.spoke.data.repository.EncounterRepository
import java.util.UUID
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.serialization.json.Json

sealed interface EncounterPhase {
    data object Idle : EncounterPhase
    data object Loading : EncounterPhase
    data object Success : EncounterPhase
    data class Error(val message: String) : EncounterPhase
}

data class EncounterUiState(
    val encounters: List<EncounterEntity> = emptyList(),
    val phase: EncounterPhase = EncounterPhase.Idle,
    val activeMonsters: List<EncounterMonster> = emptyList(),
    val activeLabel: String = "",
    val activeTargetXp: Int = 0,
)

class EncounterViewModel(
    private val repository: EncounterRepository,
    private val api: HubApi,
) : ViewModel() {
    private val json = Json { ignoreUnknownKeys = true }

    private val _state = MutableStateFlow(EncounterUiState())
    val state: StateFlow<EncounterUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            repository.observeEncounters().collect { encounters ->
                _state.value = _state.value.copy(encounters = encounters)
            }
        }
    }

    fun generateEncounter(partyLevel: Int, difficulty: String, theme: String) {
        if (_state.value.phase == EncounterPhase.Loading) return
        viewModelScope.launch {
            _state.value = _state.value.copy(phase = EncounterPhase.Loading)
            try {
                val response = api.generateEncounter(
                    EncounterRequest(partyLevel, 4, difficulty, theme),
                )
                repository.saveEncounter(
                    id = UUID.randomUUID().toString(),
                    theme = response.theme.ifBlank { theme },
                    threat = response.threat.ifBlank { difficulty },
                    monstersJson = json.encodeToString(response.monsters),
                    targetXp = response.targetXp,
                )
                _state.value = _state.value.copy(
                    phase = EncounterPhase.Success,
                    activeMonsters = response.monsters,
                    activeLabel = "${response.threat} · ${response.theme}",
                    activeTargetXp = response.targetXp,
                )
            } catch (_: Exception) {
                _state.value = _state.value.copy(
                    phase = EncounterPhase.Error("Encounter conjuring failed — is the hub awake?"),
                )
            }
        }
    }

    fun inspect(encounter: EncounterEntity) {
        val monsters = try {
            json.decodeFromString<List<EncounterMonster>>(encounter.monstersJson)
        } catch (_: Exception) {
            emptyList()
        }
        _state.value = _state.value.copy(
            phase = EncounterPhase.Success,
            activeMonsters = monsters,
            activeLabel = "${encounter.threat} · ${encounter.theme}",
            activeTargetXp = encounter.targetXp,
        )
    }

    fun delete(id: String) {
        viewModelScope.launch { repository.deleteEncounter(id) }
    }
}
