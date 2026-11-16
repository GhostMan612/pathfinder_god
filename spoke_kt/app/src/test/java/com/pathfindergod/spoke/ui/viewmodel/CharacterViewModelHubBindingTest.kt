// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.viewmodel

import com.pathfindergod.spoke.data.local.CharacterDao
import com.pathfindergod.spoke.data.local.CharacterEntity
import com.pathfindergod.spoke.data.network.AskRequest
import com.pathfindergod.spoke.data.network.AskResponse
import com.pathfindergod.spoke.data.network.BuildCharacterRequest
import com.pathfindergod.spoke.data.network.BuildCharacterResponse
import com.pathfindergod.spoke.data.network.CombatSceneRequest
import com.pathfindergod.spoke.data.network.CombatSceneResponse
import com.pathfindergod.spoke.data.network.CreateCampaignRequest
import com.pathfindergod.spoke.data.network.CreateCampaignResponse
import com.pathfindergod.spoke.data.network.EncounterRequest
import com.pathfindergod.spoke.data.network.EncounterResponse
import com.pathfindergod.spoke.data.network.EndTurnRequest
import com.pathfindergod.spoke.data.network.EndTurnResponse
import com.pathfindergod.spoke.data.network.GenerateRequest
import com.pathfindergod.spoke.data.network.HubApi
import com.pathfindergod.spoke.data.network.HubCampaignSummary
import com.pathfindergod.spoke.data.network.LootResponse
import com.pathfindergod.spoke.data.network.MapGenerateResponse
import com.pathfindergod.spoke.data.network.MapRequest
import com.pathfindergod.spoke.data.network.PartySyncRequest
import com.pathfindergod.spoke.data.network.PartySyncResponse
import com.pathfindergod.spoke.data.network.SoloStateResponse
import com.pathfindergod.spoke.data.network.StrikeRequest
import com.pathfindergod.spoke.data.network.StrikeResponse
import com.pathfindergod.spoke.data.network.SummarizeRequest
import com.pathfindergod.spoke.data.network.SummarizeResponse
import com.pathfindergod.spoke.data.network.TurnRequest
import com.pathfindergod.spoke.data.network.TurnResponse
import com.pathfindergod.spoke.data.repository.CharacterRepository
import com.pathfindergod.spoke.data.repository.HubBinding
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.serialization.json.JsonElement
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class CharacterViewModelHubBindingTest {

    private class InMemoryCharacterDao(
        initial: List<CharacterEntity> = emptyList(),
    ) : CharacterDao {
        private val items = initial.associateBy { it.id }.toMutableMap()
        private val flow = MutableStateFlow(items.values.toList())

        override fun observeAll(): Flow<List<CharacterEntity>> = flow.asStateFlow()
        override suspend fun getById(id: Long): CharacterEntity? = items[id]
        override suspend fun upsert(entity: CharacterEntity): Long {
            val id = if (entity.id == 0L) (items.keys.maxOrNull() ?: 0L) + 1L else entity.id
            items[id] = entity.copy(id = id)
            flow.value = items.values.toList()
            return id
        }
        override suspend fun delete(id: Long) {
            items.remove(id)
            flow.value = items.values.toList()
        }
        override suspend fun count(): Int = items.size
        override suspend fun getByUuid(uuid: String): CharacterEntity? =
            items.values.firstOrNull { it.uuid == uuid }
        override suspend fun backfillUuidIfBlank(id: Long, uuid: String): Int = 0
        override suspend fun updateSyncState(
            id: Long,
            uuid: String,
            hubUrl: String?,
            campaignId: Int?,
            serverRevision: Int?,
            syncStatus: String,
            lastSyncedAt: String?,
        ) {
            val current = items[id] ?: return
            items[id] = current.copy(
                uuid = uuid,
                hubUrl = hubUrl,
                campaignId = campaignId,
                serverRevision = serverRevision,
                syncStatus = syncStatus,
                lastSyncedAt = lastSyncedAt,
            )
            flow.value = items.values.toList()
        }
    }

    private class FakeHubApi : HubApi {
        var onListCampaigns: (suspend () -> List<HubCampaignSummary>)? = null
        var onSync: (suspend (Int, PartySyncRequest) -> PartySyncResponse)? = null

        override suspend fun listCampaigns(): List<HubCampaignSummary> =
            onListCampaigns?.invoke() ?: emptyList()

        override suspend fun syncPartyMember(campaignId: Int, request: PartySyncRequest): PartySyncResponse =
            onSync?.invoke(campaignId, request) ?: error("onSync not configured")

        override suspend fun getCampaignParty(campaignId: Int): List<Map<String, JsonElement>> = emptyList()
        override suspend fun ask(request: AskRequest): AskResponse = error("unused")
        override suspend fun createSoloCampaign(request: CreateCampaignRequest): CreateCampaignResponse = error("unused")
        override suspend fun takeSoloTurn(campaignId: Int, request: TurnRequest): TurnResponse = error("unused")
        override suspend fun getSoloState(campaignId: Int): SoloStateResponse = error("unused")
        override suspend fun resolveStrike(request: StrikeRequest): StrikeResponse = error("unused")
        override suspend fun endTurn(request: EndTurnRequest): EndTurnResponse = error("unused")
        override suspend fun generateCharacter(request: BuildCharacterRequest): BuildCharacterResponse = error("unused")
        override suspend fun generateLoot(request: GenerateRequest): LootResponse = error("unused")
        override suspend fun generateEncounter(request: EncounterRequest): EncounterResponse = error("unused")
        override suspend fun generateMap(request: MapRequest): MapGenerateResponse = error("unused")
        override suspend fun setCombatScene(request: CombatSceneRequest): CombatSceneResponse = error("unused")
        override suspend fun summarizeSession(request: SummarizeRequest): SummarizeResponse = error("unused")
    }

    @Test
    fun switchingHubClearsLoadedCampaignChipsAndRequiresFreshSelection() {
        var currentHub = "https://hub-a.example:8443"
        var selectedCampaignByHub: Pair<String, Int>? = "https://hub-a.example:8443" to 7
        val dao = InMemoryCharacterDao(
            listOf(
                CharacterEntity(
                    id = 1L,
                    name = "Valeros",
                    characterClass = "Fighter",
                    level = 4,
                    uuid = "valeros-uuid",
                    hubUrl = "https://hub-a.example:8443",
                    campaignId = 7,
                    serverRevision = 3,
                    syncStatus = "synced",
                ),
            ),
        )
        val apiA = FakeHubApi().apply {
            onListCampaigns = { listOf(HubCampaignSummary(id = 7, name = "Hub A Seven")) }
        }
        val apiB = FakeHubApi().apply {
            onListCampaigns = { listOf(HubCampaignSummary(id = 7, name = "Hub B Seven")) }
        }
        var syncCalls = 0
        apiA.onSync = { _, _ -> syncCalls += 1; error("unexpected sync") }
        apiB.onSync = { _, _ -> syncCalls += 1; error("unexpected sync") }

        val repo = CharacterRepository(
            dao = dao,
            apiProvider = { if (currentHub.contains("hub-a")) apiA else apiB },
            selectedCampaignIdProvider = {
                selectedCampaignByHub?.takeIf { it.first == currentHub }?.second
            },
            onCampaignSelected = { cid -> selectedCampaignByHub = currentHub to cid },
            hubUrlProvider = { currentHub },
        )
        val vm = CharacterViewModel(repo, dispatcher = Dispatchers.Unconfined)

        vm.loadHubCampaigns()
        assertEquals(listOf(HubCampaignSummary(7, "Hub A Seven")), vm.state.value.hubCampaigns)
        assertEquals(7, vm.state.value.selectedCampaignId)

        currentHub = "https://hub-b.example:8443"
        selectedCampaignByHub = null
        vm.syncHubContext()

        assertEquals("https://hub-b.example:8443", vm.state.value.currentHubIdentity)
        assertNull(vm.state.value.selectedCampaignId)
        assertTrue(vm.state.value.hubCampaigns.isEmpty())

        vm.sync(1L)
        assertEquals(0, syncCalls)
        assertEquals("campaign_required", vm.state.value.characters.single().syncStatus)

        vm.loadHubCampaigns()
        assertEquals(listOf(HubCampaignSummary(7, "Hub B Seven")), vm.state.value.hubCampaigns)
    }

    @Test
    fun switchingHubCancelsAndDiscardsInFlightCampaignLoad() {
        var currentHub = "https://hub-a.example:8443"
        val pendingA = CompletableDeferred<List<HubCampaignSummary>>()
        val apiA = FakeHubApi().apply { onListCampaigns = { pendingA.await() } }
        val apiB = FakeHubApi().apply {
            onListCampaigns = { listOf(HubCampaignSummary(id = 12, name = "Fresh Hub B")) }
        }
        val repo = CharacterRepository(
            dao = InMemoryCharacterDao(),
            apiProvider = { if (currentHub.contains("hub-a")) apiA else apiB },
            hubUrlProvider = { currentHub },
        )
        val vm = CharacterViewModel(repo, dispatcher = Dispatchers.Unconfined)

        vm.loadHubCampaigns()
        assertTrue(vm.state.value.isLoadingCampaigns)

        currentHub = "https://hub-b.example:8443"
        vm.syncHubContext()

        assertFalse(vm.state.value.isLoadingCampaigns)
        assertTrue(vm.state.value.hubCampaigns.isEmpty())

        pendingA.complete(listOf(HubCampaignSummary(id = 7, name = "Stale Hub A")))
        assertTrue(vm.state.value.hubCampaigns.isEmpty())

        vm.loadHubCampaigns()
        assertEquals(listOf(HubCampaignSummary(12, "Fresh Hub B")), vm.state.value.hubCampaigns)
    }

    @Test
    fun viewModelSyncPrioritizesCharactersOwnBoundCampaignOnSameHubOverGlobalSelection() {
        val dao = InMemoryCharacterDao(
            listOf(
                CharacterEntity(
                    id = 1L,
                    name = "Kyra",
                    characterClass = "Cleric",
                    level = 5,
                    uuid = "kyra-uuid",
                    hubUrl = "https://hub-a.example:8443",
                    campaignId = 3,
                    serverRevision = 2,
                    syncStatus = "synced",
                ),
            ),
        )
        var seenCampaignId = -1
        var seenExpectedRevision: Int? = -1
        val api = FakeHubApi().apply {
            onSync = { cid, req ->
                seenCampaignId = cid
                seenExpectedRevision = req.expectedRevision
                PartySyncResponse(
                    id = 31,
                    uuid = req.uuid,
                    name = req.name,
                    revision = 3,
                    updatedAt = "2026-11-14T02:20:00Z",
                    status = "synced",
                )
            }
        }
        val repo = CharacterRepository(
            dao = dao,
            apiProvider = { api },
            selectedCampaignIdProvider = { 9 },
            hubUrlProvider = { "https://hub-a.example:8443" },
        )
        val vm = CharacterViewModel(repo, dispatcher = Dispatchers.Unconfined)

        vm.sync(1L)
        assertEquals(3, seenCampaignId)
        assertEquals(2, seenExpectedRevision)
        assertEquals(3, vm.state.value.characters.single().campaignId)
        assertEquals(3, vm.state.value.characters.single().serverRevision)
    }

    @Test
    fun viewModelCrossHubConfirmationFlowOnlySyncsAfterExplicitConfirm() {
        var currentHub = "https://hub-a.example:8443"
        var selectedCampaign: Int? = null
        val dao = InMemoryCharacterDao(
            listOf(
                CharacterEntity(
                    id = 1L,
                    name = "Amiri",
                    characterClass = "Barbarian",
                    level = 4,
                    uuid = "amiri-uuid",
                    hubUrl = "https://hub-a.example:8443",
                    campaignId = 7,
                    serverRevision = 4,
                    syncStatus = "synced",
                ),
            ),
        )
        var syncCalls = 0
        var seenCampaignId = -1
        var seenExpectedRevision: Int? = -1
        val api = FakeHubApi().apply {
            onSync = { cid, req ->
                syncCalls += 1
                seenCampaignId = cid
                seenExpectedRevision = req.expectedRevision
                PartySyncResponse(
                    id = 88,
                    uuid = req.uuid,
                    name = req.name,
                    revision = 1,
                    updatedAt = "2026-11-14T02:30:00Z",
                    status = "synced",
                )
            }
        }
        val repo = CharacterRepository(
            dao = dao,
            apiProvider = { api },
            selectedCampaignIdProvider = { selectedCampaign },
            onCampaignSelected = { selectedCampaign = it },
            hubUrlProvider = { currentHub },
        )
        val vm = CharacterViewModel(repo, dispatcher = Dispatchers.Unconfined)

        currentHub = "https://hub-b.example:8443"
        vm.syncHubContext()
        vm.selectCampaign(7)

        vm.sync(1L)
        assertEquals(0, syncCalls)
        val pending = vm.state.value.pendingCrossHubSync
        assertNotNull(pending)
        assertEquals(1L, pending!!.characterId)
        assertEquals(7, pending.campaignId)
        assertEquals("https://hub-a.example:8443", pending.previousHubUrl)
        assertEquals("https://hub-b.example:8443", pending.targetHubUrl)

        vm.dismissCrossHubSync()
        assertNull(vm.state.value.pendingCrossHubSync)
        assertEquals(0, syncCalls)

        vm.sync(1L)
        assertNotNull(vm.state.value.pendingCrossHubSync)
        vm.confirmCrossHubSync()

        assertNull(vm.state.value.pendingCrossHubSync)
        assertEquals(1, syncCalls)
        assertEquals(7, seenCampaignId)
        assertEquals(0, seenExpectedRevision)
        assertEquals("https://hub-b.example:8443", vm.state.value.characters.single().hubUrl)
    }

    private fun syncResponse(request: PartySyncRequest) = PartySyncResponse(
        id = 77,
        uuid = request.uuid,
        name = request.name,
        revision = 1,
        updatedAt = "2026-11-15T00:00:00Z",
        status = "synced",
    )

    @Test
    fun confirmCrossHubSyncRePromptsWhenHubMovesAfterApproval() {
        val hubA = "https://hub-a.example:8443"
        val hubB = "https://hub-b.example:8443"
        val hubC = "https://hub-c.example:8443"
        var currentHub = hubB
        val dao = InMemoryCharacterDao(
            listOf(
                CharacterEntity(
                    id = 1L,
                    name = "Amiri",
                    characterClass = "Barbarian",
                    level = 4,
                    uuid = "amiri-reprompt-uuid",
                    hubUrl = hubA,
                    campaignId = 7,
                    serverRevision = 4,
                    syncStatus = "synced",
                ),
            ),
        )
        var callsA = 0
        var callsB = 0
        var callsC = 0
        val apiA = FakeHubApi().apply {
            onSync = { _, _ ->
                callsA += 1
                error("hub A was never approved")
            }
        }
        val apiB = FakeHubApi().apply {
            onSync = { _, request ->
                callsB += 1
                syncResponse(request)
            }
        }
        val apiC = FakeHubApi().apply {
            onSync = { _, request ->
                callsC += 1
                syncResponse(request)
            }
        }
        val repo = CharacterRepository(
            dao = dao,
            apiProvider = { error("legacy provider must not be consulted") },
            selectedCampaignIdProvider = { 7 },
            hubUrlProvider = { currentHub },
            bindingProvider = {
                HubBinding.of(currentHub) { url ->
                    when {
                        url.contains("hub-a") -> apiA
                        url.contains("hub-b") -> apiB
                        else -> apiC
                    }
                }
            },
        )
        val vm = CharacterViewModel(repo, dispatcher = Dispatchers.Unconfined)

        vm.syncHubContext()
        vm.sync(1L)
        val first = vm.state.value.pendingCrossHubSync
        assertNotNull(first)
        assertEquals(hubA, first!!.previousHubUrl)
        assertEquals(hubB, first.targetHubUrl)
        assertEquals(0, callsB)

        // Settings moves to hub C, but the preference listener has not run yet,
        // so the dialog is still holding the hub B approval.
        currentHub = hubC
        vm.confirmCrossHubSync()

        assertEquals(0, callsA)
        assertEquals(0, callsB)
        assertEquals(0, callsC)
        val second = vm.state.value.pendingCrossHubSync
        assertNotNull(second)
        assertEquals("hub C must be approved explicitly", hubC, second!!.targetHubUrl)
        assertEquals(hubA, second.previousHubUrl)
        assertEquals(hubA, vm.state.value.characters.single().hubUrl)

        vm.confirmCrossHubSync()
        assertNull(vm.state.value.pendingCrossHubSync)
        assertEquals(1, callsC)
        assertEquals(0, callsB)
        assertEquals(hubC, vm.state.value.characters.single().hubUrl)
    }
}
