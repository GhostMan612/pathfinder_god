// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.pathfindergod.spoke.R
import com.pathfindergod.spoke.data.local.CharacterEntity
import com.pathfindergod.spoke.data.network.HubCampaignSummary
import com.pathfindergod.spoke.data.repository.CharacterMapper
import com.pathfindergod.spoke.data.repository.CharacterRepository
import com.pathfindergod.spoke.data.repository.CharacterSyncResult
import com.pathfindergod.spoke.data.repository.HandsetAuthResult
import com.pathfindergod.spoke.ui.strings.UiText
import kotlinx.serialization.json.JsonElement
import kotlin.coroutines.CoroutineContext
import kotlin.coroutines.EmptyCoroutineContext
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class PendingCrossHubSync(
    val characterId: Long,
    val campaignId: Int,
    val previousHubUrl: String,
    val targetHubUrl: String,
)

/**
 * A 409 the user has not resolved yet (Issue #33 Phase 4).
 *
 * The Hub holds a newer revision of this character. Nothing is overwritten
 * until the user picks "Keep mine" (re-push at the Hub's revision) or
 * "Use Hub's" (adopt the server row). The server row rides along so the
 * choice needs no extra fetch.
 */
data class PendingSyncConflict(
    val characterId: Long,
    val campaignId: Int,
    val currentRevision: Int,
    val serverCharacter: Map<String, JsonElement>?,
)

data class CharacterUiState(
    val characters: List<CharacterEntity> = emptyList(),
    val selectedId: Long? = null,
    val currentHubIdentity: String = "",
    val selectedCampaignId: Int? = null,
    val hubCampaigns: List<HubCampaignSummary> = emptyList(),
    val isLoading: Boolean = false,
    val isLoadingCampaigns: Boolean = false,
    val isForging: Boolean = false,
    val syncingId: Long? = null,
    val pendingCrossHubSync: PendingCrossHubSync? = null,
    val pendingSyncConflict: PendingSyncConflict? = null,
    val pendingOutboxCount: Int = 0,
    val handsetAuth: HandsetAuthResult? = null,
    val error: UiText? = null,
    val lastForgedId: Long? = null,
)

class CharacterViewModel(
    private val repository: CharacterRepository,
    dispatcher: CoroutineDispatcher? = null,
) : ViewModel() {
    private val launchContext: CoroutineContext = dispatcher ?: EmptyCoroutineContext
    private var loadCampaignsJob: Job? = null

    private val _state = MutableStateFlow(
        CharacterUiState(
            currentHubIdentity = repository.currentHubIdentity(),
            selectedCampaignId = repository.selectedCampaignId(),
            isLoading = true,
        ),
    )
    val state: StateFlow<CharacterUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch(launchContext) {
            repository.observeCharacters().collect { characters ->
                _state.value = _state.value.copy(
                    characters = characters,
                    isLoading = false,
                )
            }
        }
        viewModelScope.launch(launchContext) {
            repository.observePendingOutboxCount().collect { count ->
                _state.value = _state.value.copy(pendingOutboxCount = count)
            }
        }
    }

    fun select(id: Long?) {
        _state.value = _state.value.copy(selectedId = id)
    }

    fun save(entity: CharacterEntity) {
        viewModelScope.launch(launchContext) {
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

        viewModelScope.launch(launchContext) {
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
        viewModelScope.launch(launchContext) {
            repository.deleteCharacter(id)
            if (_state.value.selectedId == id) {
                _state.value = _state.value.copy(selectedId = null)
            }
        }
    }

    suspend fun localCount(): Int = repository.characterCount()

    fun selectCampaign(campaignId: Int) {
        if (campaignId < 1) return
        syncHubContext()
        repository.setSelectedCampaignId(campaignId)
        _state.value = _state.value.copy(selectedCampaignId = campaignId)
    }

    fun syncHubContext() {
        val nextHub = repository.currentHubIdentity()
        val nextSelected = repository.selectedCampaignId()
        if (nextHub != _state.value.currentHubIdentity) {
            loadCampaignsJob?.cancel()
            loadCampaignsJob = null
            _state.value = _state.value.copy(
                currentHubIdentity = nextHub,
                selectedCampaignId = nextSelected,
                hubCampaigns = emptyList(),
                isLoadingCampaigns = false,
                pendingCrossHubSync = null,
                pendingSyncConflict = null,
            )
        } else if (nextSelected != _state.value.selectedCampaignId) {
            _state.value = _state.value.copy(selectedCampaignId = nextSelected)
        }
    }

    fun refreshSelectedCampaignFromPrefs() {
        syncHubContext()
    }

    fun loadHubCampaigns() {
        syncHubContext()
        if (_state.value.isLoadingCampaigns) return
        val requestHub = _state.value.currentHubIdentity
        loadCampaignsJob = viewModelScope.launch(launchContext) {
            _state.value = _state.value.copy(isLoadingCampaigns = true)
            try {
                val campaigns = repository.listHubCampaigns()
                if (repository.currentHubIdentity() == requestHub &&
                    _state.value.currentHubIdentity == requestHub
                ) {
                    _state.value = _state.value.copy(
                        hubCampaigns = campaigns,
                        isLoadingCampaigns = false,
                    )
                }
            } catch (e: CancellationException) {
                throw e
            } catch (_: Exception) {
                if (repository.currentHubIdentity() == requestHub &&
                    _state.value.currentHubIdentity == requestHub
                ) {
                    _state.value = _state.value.copy(isLoadingCampaigns = false)
                }
            }
        }
    }

    fun sync(
        id: Long,
        campaignId: Int? = null,
        confirmCrossHub: Boolean = false,
        confirmedHubUrl: String? = null,
    ) {
        syncHubContext()
        if (_state.value.syncingId != null) return
        val hero = _state.value.characters.firstOrNull { it.id == id }
        val activeHub = _state.value.currentHubIdentity
        val boundCampaign = hero?.campaignId?.takeIf {
            !hero.hubUrl.isNullOrBlank() && hero.hubUrl == activeHub
        }
        val resolvedCampaignId = campaignId
            ?: boundCampaign
            ?: _state.value.selectedCampaignId
            ?: repository.selectedCampaignId()
        viewModelScope.launch(launchContext) {
            _state.value = _state.value.copy(syncingId = id)
            try {
                val outcome = repository.syncCharacter(
                    characterId = id,
                    campaignId = resolvedCampaignId,
                    confirmCrossHub = confirmCrossHub,
                    confirmedHubUrl = confirmedHubUrl,
                )
                val pending = if (outcome is CharacterSyncResult.CrossHubConfirmationRequired) {
                    PendingCrossHubSync(
                        characterId = id,
                        campaignId = outcome.targetCampaignId,
                        previousHubUrl = outcome.previousHubUrl,
                        targetHubUrl = outcome.targetHubUrl,
                    )
                } else {
                    null
                }
                val conflict = if (outcome is CharacterSyncResult.Conflict) {
                    PendingSyncConflict(
                        characterId = id,
                        campaignId = resolvedCampaignId,
                        currentRevision = outcome.currentRevision,
                        serverCharacter = outcome.serverCharacter,
                    )
                } else if (outcome is CharacterSyncResult.Success) {
                    null
                } else {
                    _state.value.pendingSyncConflict?.takeIf { it.characterId == id }
                }
                _state.value = _state.value.copy(
                    pendingCrossHubSync = pending,
                    pendingSyncConflict = conflict,
                )
            } finally {
                _state.value = _state.value.copy(syncingId = null)
            }
        }
    }

    fun confirmCrossHubSync() {
        val pending = _state.value.pendingCrossHubSync ?: return
        _state.value = _state.value.copy(pendingCrossHubSync = null)
        // Carry the approved destination into the call: if Settings moved to a
        // different Hub after this prompt was shown, the repository voids the
        // approval and prompts again instead of transferring somewhere unseen.
        sync(
            id = pending.characterId,
            campaignId = pending.campaignId,
            confirmCrossHub = true,
            confirmedHubUrl = pending.targetHubUrl,
        )
    }

    fun dismissCrossHubSync() {
        if (_state.value.pendingCrossHubSync != null) {
            _state.value = _state.value.copy(pendingCrossHubSync = null)
        }
    }

    /**
     * Resolve a pending 409 by keeping the local sheet: adopt the Hub's
     * revision number, then push the local sheet at that revision. If the
     * Hub moved on again, the conflict simply comes back.
     */
    fun resolveConflictKeepMine() {
        val pending = _state.value.pendingSyncConflict ?: return
        if (_state.value.syncingId != null) return
        _state.value = _state.value.copy(pendingSyncConflict = null)
        viewModelScope.launch(launchContext) {
            _state.value = _state.value.copy(syncingId = pending.characterId)
            try {
                val outcome = repository.resolveConflictKeepMine(
                    characterId = pending.characterId,
                    currentRevision = pending.currentRevision,
                    campaignId = pending.campaignId,
                )
                if (outcome is CharacterSyncResult.Conflict) {
                    _state.value = _state.value.copy(
                        pendingSyncConflict = pending.copy(
                            currentRevision = outcome.currentRevision,
                            serverCharacter = outcome.serverCharacter,
                        ),
                    )
                }
            } finally {
                _state.value = _state.value.copy(syncingId = null)
            }
        }
    }

    /** Resolve a pending 409 by adopting the Hub's character row. */
    fun resolveConflictUseServer() {
        val pending = _state.value.pendingSyncConflict ?: return
        _state.value = _state.value.copy(pendingSyncConflict = null)
        viewModelScope.launch(launchContext) {
            repository.resolveConflictUseServer(
                pending.characterId,
                pending.serverCharacter,
            )
        }
    }

    fun dismissConflict() {
        if (_state.value.pendingSyncConflict != null) {
            _state.value = _state.value.copy(pendingSyncConflict = null)
        }
    }

    /** Discard a queued sync without touching the local sheet. */
    fun dismissQueuedSync(id: Long) {
        viewModelScope.launch(launchContext) {
            repository.clearQueuedSync(id)
        }
    }

    /** Verify this handset can authenticate to its Hub (Issue #33 Phase 4). */
    fun verifyHandset() {
        viewModelScope.launch(launchContext) {
            _state.value = _state.value.copy(handsetAuth = repository.verifyHandsetAuth())
        }
    }

    fun dismissHandsetAuth() {
        if (_state.value.handsetAuth != null) {
            _state.value = _state.value.copy(handsetAuth = null)
        }
    }
}
