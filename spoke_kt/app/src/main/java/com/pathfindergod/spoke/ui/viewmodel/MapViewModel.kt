// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.pathfindergod.spoke.R
import com.pathfindergod.spoke.data.local.MapEntity
import com.pathfindergod.spoke.data.network.MapRequest
import com.pathfindergod.spoke.data.network.HubApi
import com.pathfindergod.spoke.data.repository.MapRepository
import com.pathfindergod.spoke.ui.strings.UiText
import java.util.UUID
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class MapUiState(
    val maps: List<MapEntity> = emptyList(),
    val isGenerating: Boolean = false,
    val error: UiText? = null,
)

class MapViewModel(
    private val repository: MapRepository,
    private val api: HubApi,
) : ViewModel() {
    private val _state = MutableStateFlow(MapUiState())
    val state: StateFlow<MapUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            repository.observeMaps().collect { maps ->
                _state.value = _state.value.copy(maps = maps)
            }
        }
    }

    fun generate(prompt: String) {
        if (_state.value.isGenerating) return
        viewModelScope.launch {
            _state.value = _state.value.copy(isGenerating = true, error = null)
            try {
                val response = api.generateMap(MapRequest(prompt))
                val gm = response.gmBase64Png.orEmpty()
                if (response.valid && gm.isNotBlank()) {
                    repository.saveMap(
                        id = UUID.randomUUID().toString(),
                        prompt = prompt,
                        gmBase64Png = gm,
                        playerBase64Png = response.playerBase64Png?.takeIf { it.isNotBlank() } ?: gm,
                        width = response.width ?: 0,
                        height = response.height ?: 0,
                    )
                } else {
                    _state.value = _state.value.copy(
                        error = UiText.Resource(R.string.map_forge_empty),
                    )
                }
            } catch (_: Exception) {
                _state.value = _state.value.copy(
                    error = UiText.Resource(R.string.map_conjure_failed),
                )
            }
            _state.value = _state.value.copy(isGenerating = false)
        }
    }

    fun delete(id: String) {
        viewModelScope.launch { repository.deleteMap(id) }
    }
}
