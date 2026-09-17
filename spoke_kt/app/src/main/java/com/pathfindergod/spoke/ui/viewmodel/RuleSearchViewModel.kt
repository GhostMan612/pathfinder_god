// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.pathfindergod.spoke.data.local.RuleFtsEntity
import com.pathfindergod.spoke.data.repository.RuleRepository
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class RuleSearchUiState(
    val query: String = "",
    val results: List<RuleFtsEntity> = emptyList(),
    val isLoading: Boolean = false,
)

class RuleSearchViewModel(
    private val repository: RuleRepository,
) : ViewModel() {
    private val _state = MutableStateFlow(RuleSearchUiState())
    val state: StateFlow<RuleSearchUiState> = _state.asStateFlow()

    private var searchJob: Job? = null

    fun search(query: String, system: String? = null, limit: Int = 25) {
        searchJob?.cancel()
        val trimmed = query.trim()
        if (trimmed.isEmpty()) {
            _state.value = RuleSearchUiState()
            return
        }
        searchJob = viewModelScope.launch {
            _state.value = _state.value.copy(query = trimmed, isLoading = true)
            val results = if (system.isNullOrEmpty()) {
                repository.search(trimmed, limit)
            } else {
                repository.searchInSystem(trimmed, system, limit)
            }
            _state.value = _state.value.copy(results = results, isLoading = false)
        }
    }

    fun clear() {
        searchJob?.cancel()
        _state.value = RuleSearchUiState()
    }
}
