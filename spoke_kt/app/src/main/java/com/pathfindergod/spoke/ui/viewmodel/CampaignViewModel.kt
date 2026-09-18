// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.pathfindergod.spoke.data.local.CampaignEntity
import com.pathfindergod.spoke.data.repository.CampaignRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class CampaignUiState(
    val campaign: CampaignEntity? = null,
    val isSummarizing: Boolean = false,
    val error: String? = null,
)

class CampaignViewModel(
    private val repository: CampaignRepository,
) : ViewModel() {
    private val _state = MutableStateFlow(CampaignUiState())
    val state: StateFlow<CampaignUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            repository.observeActive().collect { campaign ->
                _state.value = _state.value.copy(campaign = campaign)
            }
        }
    }

    fun createCampaign(name: String, description: String) {
        viewModelScope.launch {
            try {
                repository.createCampaign(name, description)
            } catch (_: Exception) {
                _state.value = _state.value.copy(error = "Campaign creation failed.")
            }
        }
    }

    fun summarizeRecentEvents(events: List<String>) {
        if (_state.value.isSummarizing) return
        viewModelScope.launch {
            _state.value = _state.value.copy(isSummarizing = true, error = null)
            try {
                repository.summarizeRecentEvents(events)
            } catch (_: Exception) {
                _state.value = _state.value.copy(
                    error = "Chronicler silent — is the hub awake?",
                )
            }
            _state.value = _state.value.copy(isSummarizing = false)
        }
    }

    fun clearError() {
        _state.value = _state.value.copy(error = null)
    }
}
