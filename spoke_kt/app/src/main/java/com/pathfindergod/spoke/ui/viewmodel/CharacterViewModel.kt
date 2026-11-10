// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.pathfindergod.spoke.R
import com.pathfindergod.spoke.data.local.CharacterEntity
import com.pathfindergod.spoke.data.repository.CharacterMapper
import com.pathfindergod.spoke.data.repository.CharacterRepository
import com.pathfindergod.spoke.ui.strings.UiText
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class CharacterUiState(
    val characters: List<CharacterEntity> = emptyList(),
    val selectedId: Long? = null,
    val isLoading: Boolean = false,
    val isForging: Boolean = false,
    val error: UiText? = null,
    val lastForgedId: Long? = null,
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

    /**
     * Runs the hub's character builder and persists the validated sheet.
     * The hub is the rules authority; the spoke only maps the returned wire
     * object into Room and opens the new sheet when it was accepted.
     */
    fun forge(prompt: String) {
        val request = prompt.trim()
        if (request.isEmpty()) {
            _state.value = _state.value.copy(
                error = UiText.Resource(R.string.character_forge_empty),
            )
            return
        }
        if (_state.value.isForging) return

        viewModelScope.launch {
            _state.value = _state.value.copy(isForging = true, error = null)
            var error: UiText? = null
            try {
                val response = repository.forgeCharacter(request)
                val wire = response.character
                if (response.valid && wire != null) {
                    val entity = CharacterMapper.fromWire(wire)
                    if (entity == null) {
                        error = UiText.Resource(R.string.character_forge_rejected)
                    } else {
                        val id = repository.saveCharacter(entity)
                        _state.value = _state.value.copy(
                            selectedId = id,
                            isForging = false,
                            error = null,
                            lastForgedId = id,
                        )
                        return@launch
                    }
                } else {
                    error = response.errors
                        .firstOrNull { it.isNotBlank() }
                        ?.let { UiText.Message(it) }
                        ?: UiText.Resource(R.string.character_forge_rejected)
                }
            } catch (_: Exception) {
                error = UiText.Resource(R.string.character_forge_failed)
            }
            _state.value = _state.value.copy(isForging = false, error = error)
        }
    }

    fun clearForgeError() {
        if (_state.value.error != null) {
            _state.value = _state.value.copy(error = null)
        }
    }

    fun consumeForged() {
        if (_state.value.lastForgedId != null) {
            _state.value = _state.value.copy(lastForgedId = null)
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
