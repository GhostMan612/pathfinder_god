// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.pathfindergod.spoke.data.local.CharacterEntity
import com.pathfindergod.spoke.data.repository.CharacterRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class CharacterUiState(
    val characters: List<CharacterEntity> = emptyList(),
    val selectedId: Long? = null,
    val isLoading: Boolean = false,
)

class CharacterViewModel(
    private val repository: CharacterRepository,
) : ViewModel() {
    private val _state = MutableStateFlow(CharacterUiState(isLoading = true))
    val state: StateFlow<CharacterUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            repository.observeCharacters().collect { characters ->
                _state.value = _state.value.copy(
                    characters = characters,
                    isLoading = false,
                )
            }
        }
    }

    fun select(id: Long?) {
        _state.value = _state.value.copy(selectedId = id)
    }

    fun save(entity: CharacterEntity) {
        viewModelScope.launch {
            val id = repository.saveCharacter(entity)
            _state.value = _state.value.copy(selectedId = id)
        }
    }

    fun delete(id: Long) {
        viewModelScope.launch {
            repository.deleteCharacter(id)
            if (_state.value.selectedId == id) {
                _state.value = _state.value.copy(selectedId = null)
            }
        }
    }

    suspend fun localCount(): Int = repository.characterCount()
}
