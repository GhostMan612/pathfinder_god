// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.pathfindergod.spoke.R
import com.pathfindergod.spoke.data.network.AskRequest
import com.pathfindergod.spoke.data.network.GmStreamSource
import com.pathfindergod.spoke.data.network.HubApi
import com.pathfindergod.spoke.data.network.TurnRequest
import com.pathfindergod.spoke.data.network.TurnResponse
import com.pathfindergod.spoke.ui.strings.UiText
import java.util.UUID
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.intOrNull

data class GmDiceRollUi(
    val notation: String,
    val rolls: List<Int>,
    val total: Int,
)

data class GmHpChangeUi(
    val name: String,
    val hp: Int,
    val maxHp: Int,
    val deltaAmount: Int,
    val isHeal: Boolean,
)

data class GmConditionUi(
    val combatant: String,
    val name: String,
    val value: Int,
)

data class GmCampaignStateUi(
    val campaignId: Int = 1,
    val name: String = "",
    val phase: String = "exploration",
    val round: Int = 0,
    val location: String? = null,
    val activeCombatant: String? = null,
    val conditions: List<GmConditionUi> = emptyList(),
)

data class GmChatEntry(
    val id: String,
    val turnNum: Int? = null,
    val isAsk: Boolean = false,
    val prompt: String,
    val narration: String = "",
    val backend: String = "",
    val diceRolls: List<GmDiceRollUi> = emptyList(),
    val hpChanges: List<GmHpChangeUi> = emptyList(),
    val conditions: List<GmConditionUi> = emptyList(),
    val choices: List<String> = emptyList(),
    val sources: List<String> = emptyList(),
    val isStreaming: Boolean = false,
)

data class GmChatUiState(
    val campaignState: GmCampaignStateUi = GmCampaignStateUi(),
    val entries: List<GmChatEntry> = emptyList(),
    val activeChoices: List<String> = emptyList(),
    val isBusy: Boolean = false,
    val error: UiText? = null,
)

class GmChatViewModel(
    private val api: HubApi,
    private val streamClient: GmStreamSource,
    private val streamUrlProvider: () -> String,
    private val dispatcher: CoroutineDispatcher = Dispatchers.Main,
) : ViewModel() {
    private val _state = MutableStateFlow(GmChatUiState())
    val state: StateFlow<GmChatUiState> = _state.asStateFlow()

    private val askHistory = mutableListOf<List<String>>()

    fun ask(query: String, edition: String = "2e") {
        val trimmed = query.trim()
        if (trimmed.isEmpty() || _state.value.isBusy) return
        val entryId = UUID.randomUUID().toString()
        val placeholder = GmChatEntry(
            id = entryId,
            isAsk = true,
            prompt = trimmed,
            isStreaming = true,
        )
        _state.value = _state.value.copy(
            entries = _state.value.entries + placeholder,
            isBusy = true,
            error = null,
        )
        viewModelScope.launch(dispatcher) {
            try {
                val response = api.ask(
                    AskRequest(
                        query = trimmed,
                        edition = edition,
                        history = askHistory.takeLast(20),
                        campaignId = _state.value.campaignState.campaignId,
                    ),
                )
                askHistory.add(listOf(trimmed, response.answer))
                if (askHistory.size > 20) {
                    askHistory.removeAt(0)
                }
                val parsedSources = response.sources.mapNotNull(::parseSourceLabel)
                updateEntry(entryId) { current ->
                    current.copy(
                        narration = response.answer,
                        backend = response.backend,
                        sources = parsedSources,
                        isStreaming = false,
                    )
                }
                _state.value = _state.value.copy(isBusy = false)
            } catch (_: Exception) {
                removeIfEmpty(entryId)
                _state.value = _state.value.copy(
                    isBusy = false,
                    error = UiText.Resource(R.string.gm_chat_failed),
                )
            }
        }
    }

    fun takeTurn(action: String, seed: Int? = null) {
        val trimmed = action.trim()
        if (trimmed.isEmpty() || _state.value.isBusy) return
        val campaignId = _state.value.campaignState.campaignId
        val entryId = UUID.randomUUID().toString()
        val initial = GmChatEntry(
            id = entryId,
            isAsk = false,
            prompt = trimmed,
            isStreaming = true,
        )
        _state.value = _state.value.copy(
            entries = _state.value.entries + initial,
            isBusy = true,
            error = null,
        )
        viewModelScope.launch(dispatcher) {
            var completed = false
            var wsErrorText: String? = null
            try {
                streamClient.streamTurn(
                    url = streamUrlProvider(),
                    campaignId = campaignId,
                    action = trimmed,
                    actor = "player",
                    seed = seed,
                ).collect { event ->
                    when (event.type) {
                        "start" -> {
                            updateEntry(entryId) { current ->
                                current.copy(turnNum = event.turnNum ?: current.turnNum)
                            }
                            _state.value = _state.value.copy(
                                campaignState = _state.value.campaignState.copy(
                                    phase = event.phase ?: _state.value.campaignState.phase,
                                    round = event.round ?: _state.value.campaignState.round,
                                ),
                            )
                        }
                        "dice" -> {
                            val rolls = event.diceRolls.mapNotNull(::parseDiceRoll)
                            updateEntry(entryId) { current ->
                                current.copy(diceRolls = rolls)
                            }
                        }
                        "hp" -> {
                            val changes = event.hpChanges.mapNotNull(::parseHpChange)
                            updateEntry(entryId) { current ->
                                current.copy(hpChanges = changes)
                            }
                        }
                        "conditions" -> {
                            val conds = event.conditions.mapNotNull(::parseCondition)
                            updateEntry(entryId) { current ->
                                current.copy(conditions = conds)
                            }
                            _state.value = _state.value.copy(
                                campaignState = _state.value.campaignState.copy(
                                    conditions = conds,
                                ),
                            )
                        }
                        "narration", "chunk" -> {
                            val chunk = event.text.orEmpty()
                            if (chunk.isNotEmpty()) {
                                updateEntry(entryId) { current ->
                                    current.copy(narration = current.narration + chunk)
                                }
                            }
                        }
                        "end" -> {
                            val result = event.result
                            if (result != null) {
                                applyTurnResponse(entryId, result)
                            } else {
                                updateEntry(entryId) { current ->
                                    current.copy(isStreaming = false)
                                }
                            }
                            completed = true
                        }
                        "error" -> {
                            wsErrorText = event.message
                        }
                    }
                }
            } catch (_: Exception) {
                completed = false
            }

            if (!completed) {
                try {
                    val restResult = api.takeSoloTurn(
                        campaignId = campaignId,
                        request = TurnRequest(action = trimmed, seed = seed),
                    )
                    applyTurnResponse(entryId, restResult)
                    completed = true
                } catch (_: Exception) {
                    removeIfEmpty(entryId)
                    val err = wsErrorText?.takeIf { it.isNotBlank() }?.let { UiText.Message(it) }
                        ?: UiText.Resource(R.string.gm_chat_failed)
                    _state.value = _state.value.copy(
                        isBusy = false,
                        error = err,
                    )
                    return@launch
                }
            }

            _state.value = _state.value.copy(isBusy = false)
        }
    }

    fun refreshCampaignState(campaignId: Int = _state.value.campaignState.campaignId) {
        viewModelScope.launch(dispatcher) {
            try {
                val remote = api.getSoloState(campaignId)
                val conds = remote.combatants.flatMap { combatant ->
                    val cName = combatant["name"]?.let(::renderString).orEmpty()
                    val arr = combatant["conditions"] as? JsonArray ?: return@flatMap emptyList()
                    arr.mapNotNull { el ->
                        val obj = el as? Map<*, *> ?: return@mapNotNull null
                        val condName = (obj["name"] as? JsonElement)?.let(::renderString).orEmpty()
                        if (condName.isBlank()) return@mapNotNull null
                        val value = (obj["value"] as? JsonElement)?.let(::renderInt) ?: 1
                        GmConditionUi(combatant = cName, name = condName, value = value)
                    }
                }
                val activeName = remote.combatants.firstOrNull { combatant ->
                    combatant["id"]?.let(::renderInt) == remote.activeCombatantId
                }?.get("name")?.let(::renderString)
                _state.value = _state.value.copy(
                    campaignState = GmCampaignStateUi(
                        campaignId = remote.campaignId,
                        name = remote.name,
                        phase = remote.phase,
                        round = remote.round,
                        location = remote.location,
                        activeCombatant = activeName,
                        conditions = conds,
                    ),
                )
            } catch (_: Exception) {
            }
        }
    }

    fun setCampaignId(campaignId: Int) {
        val valid = campaignId.coerceAtLeast(1)
        _state.value = _state.value.copy(
            campaignState = _state.value.campaignState.copy(campaignId = valid),
        )
        refreshCampaignState(valid)
    }

    fun clearError() {
        _state.value = _state.value.copy(error = null)
    }

    private fun applyTurnResponse(entryId: String, result: TurnResponse) {
        val rolls = result.diceRolls.mapNotNull(::parseDiceRoll)
        val hp = result.hpChanges.mapNotNull(::parseHpChange)
        val conds = result.conditions.mapNotNull(::parseCondition)
        updateEntry(entryId) { current ->
            current.copy(
                turnNum = result.turnNum,
                narration = result.narration.ifBlank { current.narration },
                backend = result.source,
                diceRolls = if (rolls.isNotEmpty()) rolls else current.diceRolls,
                hpChanges = if (hp.isNotEmpty()) hp else current.hpChanges,
                conditions = if (conds.isNotEmpty()) conds else current.conditions,
                choices = result.choices,
                isStreaming = false,
            )
        }
        _state.value = _state.value.copy(
            campaignState = _state.value.campaignState.copy(
                campaignId = result.campaignId,
                phase = result.phase,
                round = result.round,
                location = result.location ?: _state.value.campaignState.location,
                activeCombatant = result.activeCombatant,
                conditions = if (conds.isNotEmpty()) conds else _state.value.campaignState.conditions,
            ),
            activeChoices = result.choices,
        )
    }

    private fun updateEntry(entryId: String, transform: (GmChatEntry) -> GmChatEntry) {
        _state.value = _state.value.copy(
            entries = _state.value.entries.map { entry ->
                if (entry.id == entryId) transform(entry) else entry
            },
        )
    }

    private fun removeIfEmpty(entryId: String) {
        _state.value = _state.value.copy(
            entries = _state.value.entries.filterNot { entry ->
                entry.id == entryId &&
                    entry.narration.isBlank() &&
                    entry.diceRolls.isEmpty() &&
                    entry.hpChanges.isEmpty()
            },
        )
    }

    private fun parseDiceRoll(raw: Map<String, JsonElement>): GmDiceRollUi? {
        val notation = raw["notation"]?.let(::renderString).orEmpty()
        val total = raw["total"]?.let(::renderInt) ?: return null
        val rolls = (raw["rolls"] as? JsonArray)
            ?.mapNotNull { (it as? JsonPrimitive)?.intOrNull }
            .orEmpty()
        return GmDiceRollUi(
            notation = notation.ifBlank { "d20" },
            rolls = rolls,
            total = total,
        )
    }

    private fun parseHpChange(raw: Map<String, JsonElement>): GmHpChangeUi? {
        val name = raw["name"]?.let(::renderString).orEmpty()
        if (name.isBlank()) return null
        val hp = raw["hp"]?.let(::renderInt) ?: 0
        val maxHp = raw["max_hp"]?.let(::renderInt) ?: hp
        val damage = raw["damage"]?.let(::renderInt)
        val healed = raw["healed"]?.let(::renderInt)
        val isHeal = healed != null && healed > 0
        val delta = if (healed != null && healed > 0) healed else damage ?: 0
        return GmHpChangeUi(
            name = name,
            hp = hp,
            maxHp = maxHp,
            deltaAmount = delta,
            isHeal = isHeal,
        )
    }

    private fun parseCondition(raw: Map<String, JsonElement>): GmConditionUi? {
        val name = raw["name"]?.let(::renderString).orEmpty()
        if (name.isBlank()) return null
        val combatant = raw["combatant"]?.let(::renderString).orEmpty().ifBlank { "Party" }
        val value = raw["value"]?.let(::renderInt) ?: 1
        return GmConditionUi(
            combatant = combatant,
            name = name,
            value = value,
        )
    }

    private fun parseSourceLabel(raw: Map<String, JsonElement>): String? {
        val book = raw["source_book"]?.let(::renderString).orEmpty()
        val name = raw["name"]?.let(::renderString).orEmpty()
        return when {
            book.isNotBlank() && name.isNotBlank() -> "$book - $name"
            name.isNotBlank() -> name
            book.isNotBlank() -> book
            else -> null
        }
    }

    private fun renderString(element: JsonElement): String = when (element) {
        is JsonPrimitive -> if (element.isString) element.content else element.toString()
        else -> element.toString()
    }

    private fun renderInt(element: JsonElement): Int? =
        (element as? JsonPrimitive)?.intOrNull
}
