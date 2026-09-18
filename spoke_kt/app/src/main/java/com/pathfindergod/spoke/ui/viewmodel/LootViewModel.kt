// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.pathfindergod.spoke.data.network.GenerateRequest
import com.pathfindergod.spoke.data.network.HubApi
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.doubleOrNull
import kotlinx.serialization.json.intOrNull

data class LootItem(
    val name: String,
    val level: Int,
    val priceGp: String,
    val rarity: String,
    val description: String,
)

sealed interface LootState {
    data object Idle : LootState
    data object Loading : LootState
    data class Success(val items: List<LootItem>, val craftDc: Int?) : LootState
    data class Error(val message: String, val items: List<LootItem>) : LootState
}

class LootViewModel(
    private val api: HubApi,
) : ViewModel() {
    private val _state = MutableStateFlow<LootState>(LootState.Idle)
    val state: StateFlow<LootState> = _state.asStateFlow()

    private val hoard = mutableListOf<LootItem>()

    fun generateLoot(partyLevel: Int, budget: Int, theme: String) {
        if (_state.value == LootState.Loading) return
        viewModelScope.launch {
            _state.value = LootState.Loading
            try {
                val wishes = theme.ifBlank { "general adventuring gear" }
                val prompt = "Party level $partyLevel with a $budget gp budget. " +
                    "Theme: $wishes."
                val response = api.generateLoot(GenerateRequest(prompt))
                val item = response.item?.let(::parseItem)
                if (response.valid && item != null) {
                    hoard.add(0, item)
                    _state.value = LootState.Success(hoard.toList(), response.craftDc)
                } else {
                    _state.value = LootState.Error(
                        response.errors.firstOrNull()
                            ?: "The forge refused the commission.",
                        hoard.toList(),
                    )
                }
            } catch (_: Exception) {
                _state.value = LootState.Error(
                    "Loot conjuring failed — is the hub awake?",
                    hoard.toList(),
                )
            }
        }
    }

    fun clearHoard() {
        hoard.clear()
        _state.value = LootState.Idle
    }

    private fun parseItem(raw: Map<String, JsonElement>): LootItem? {
        val name = raw["name"]?.let(::renderText).orEmpty()
        if (name.isBlank()) return null
        return LootItem(
            name = name,
            level = raw["level"]?.let(::renderInt) ?: 1,
            priceGp = raw["price_gp"]?.let(::renderPrice) ?: "—",
            rarity = raw["rarity"]?.let(::renderText)?.ifBlank { "common" } ?: "common",
            description = raw["description"]?.let(::renderText).orEmpty(),
        )
    }

    private fun renderText(element: JsonElement): String = when (element) {
        is JsonPrimitive -> if (element.isString) element.content else element.toString()
        else -> element.toString()
    }

    private fun renderInt(element: JsonElement): Int? =
        (element as? JsonPrimitive)?.intOrNull

    private fun renderPrice(element: JsonElement): String {
        val value = (element as? JsonPrimitive)?.doubleOrNull ?: return "—"
        val whole = value.toLong()
        return if (value == whole.toDouble()) "$whole gp" else "$value gp"
    }
}
