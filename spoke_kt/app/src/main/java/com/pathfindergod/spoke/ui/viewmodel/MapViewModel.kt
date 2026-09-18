// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.pathfindergod.spoke.data.local.MapEntity
import com.pathfindergod.spoke.data.network.GenerateRequest
import com.pathfindergod.spoke.data.network.HubApi
import com.pathfindergod.spoke.data.repository.MapRepository
import java.util.UUID
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class MapUiState(
    val maps: List<MapEntity> = emptyList(),
    val isGenerating: Boolean = false,
    val error: String? = null,
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
                val response = api.generateMap(GenerateRequest(prompt))
                if (response.valid && response.gmBase64Png.isNotBlank()) {
                    repository.saveMap(
                        id = UUID.randomUUID().toString(),
                        prompt = prompt,
                        gmBase64Png = response.gmBase64Png,
                        playerBase64Png = response.playerBase64Png.ifBlank {
                            response.gmBase64Png
                        },
                        width = response.width,
                        height = response.height,
                    )
                } else {
                    _state.value = _state.value.copy(error = "The forge returned no map.")
                }
            } catch (_: Exception) {
                _state.value = _state.value.copy(
                    error = "Map conjuring failed — is the hub awake?",
                )
            }
            _state.value = _state.value.copy(isGenerating = false)
        }
    }

    fun delete(id: String) {
        viewModelScope.launch { repository.deleteMap(id) }
    }
}
