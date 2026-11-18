// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.repository

import com.pathfindergod.spoke.data.local.CharacterDao
import com.pathfindergod.spoke.data.local.CharacterEntity
import com.pathfindergod.spoke.data.local.SyncOutboxDao
import com.pathfindergod.spoke.data.local.SyncOutboxEntry
import com.pathfindergod.spoke.data.network.AskRequest
import com.pathfindergod.spoke.data.network.AskResponse
import com.pathfindergod.spoke.data.network.BuildCharacterRequest
import com.pathfindergod.spoke.data.network.BuildCharacterResponse
import com.pathfindergod.spoke.data.network.CombatSceneRequest
import com.pathfindergod.spoke.data.network.CombatSceneResponse
import com.pathfindergod.spoke.data.network.CreateCampaignRequest
import com.pathfindergod.spoke.data.network.CreateCampaignResponse
import com.pathfindergod.spoke.data.network.EndTurnRequest
import com.pathfindergod.spoke.data.network.EndTurnResponse
import com.pathfindergod.spoke.data.network.EncounterRequest
import com.pathfindergod.spoke.data.network.EncounterResponse
import com.pathfindergod.spoke.data.network.GenerateRequest
import com.pathfindergod.spoke.data.network.HubApi
import com.pathfindergod.spoke.data.network.HubCampaignSummary
import com.pathfindergod.spoke.data.network.HubEndpoint
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
import java.io.IOException
import javax.net.ssl.SSLException
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import retrofit2.HttpException
import retrofit2.Response

/**
 * Issue #33 Phases 3-4: the durable outbox, the retry worker's replay, the
 * 409 reconciliation and the handset verification — all at repository level,
 * where the logic lives. The worker itself is a thin shell over
 * [CharacterRepository.replayDueOutboxEntries] and needs no WorkManager test
 * infrastructure.
 */
class SyncOutboxTest {

    private companion object {
        val DEFAULT_HUB = HubEndpoint.canonicalOrigin(HubEndpoint.DEFAULT_BASE_URL)
    }

    private class FakeCharacterDao(
        val characters: MutableMap<Long, CharacterEntity> = mutableMapOf(),
    ) : CharacterDao {
        override fun observeAll(): Flow<List<CharacterEntity>> = flowOf(characters.values.toList())
        override suspend fun getById(id: Long): CharacterEntity? = characters[id]
        override suspend fun upsert(entity: CharacterEntity): Long {
            val id = if (entity.id == 0L) (characters.keys.maxOrNull() ?: 0L) + 1L else entity.id
            characters[id] = entity.copy(id = id)
            return id
        }
        override suspend fun delete(id: Long) { characters.remove(id) }
        override suspend fun count(): Int = characters.size
        override suspend fun getByUuid(uuid: String): CharacterEntity? =
            characters.values.firstOrNull { it.uuid == uuid }
        override suspend fun backfillUuidIfBlank(id: Long, uuid: String): Int {
            val current = characters[id] ?: return 0
            if (current.uuid.isNotBlank()) return 0
            characters[id] = current.copy(uuid = uuid)
            return 1
        }
        override suspend fun updateSyncState(
            id: Long,
            uuid: String,
            hubUrl: String?,
            campaignId: Int?,
            serverRevision: Int?,
            syncStatus: String,
            lastSyncedAt: String?,
        ) {
            val current = characters[id]
            if (current != null) {
                characters[id] = current.copy(
                    uuid = uuid,
                    hubUrl = hubUrl,
                    campaignId = campaignId,
                    serverRevision = serverRevision,
                    syncStatus = syncStatus,
                    lastSyncedAt = lastSyncedAt,
                )
            }
        }
    }

    private class FakeSyncOutboxDao : SyncOutboxDao {
        val entries = mutableMapOf<Long, SyncOutboxEntry>()
        private var nextId = 1L

        override suspend fun enqueue(entry: SyncOutboxEntry) {
            deleteForCharacter(entry.characterId)
            insert(entry)
        }
        override suspend fun insert(entry: SyncOutboxEntry): Long {
            val id = nextId++
            entries[id] = entry.copy(id = id)
            return id
        }
        override suspend fun dueEntries(now: Long): List<SyncOutboxEntry> =
            entries.values.filter { it.nextAttemptAt <= now }.sortedBy { it.nextAttemptAt }
        override suspend fun entryForCharacter(characterId: Long): SyncOutboxEntry? =
            entries.values.firstOrNull { it.characterId == characterId }
        override suspend fun deleteForCharacter(characterId: Long) {
            entries.entries.removeIf { it.value.characterId == characterId }
        }
        override suspend fun deleteById(id: Long) { entries.remove(id) }
        override suspend fun markAttempt(id: Long, attemptCount: Int, nextAttemptAt: Long, lastError: String?) {
            entries[id]?.let { entries[id] = it.copy(attemptCount = attemptCount, nextAttemptAt = nextAttemptAt, lastError = lastError) }
        }
        override suspend fun refreshPayload(
            id: Long,
            payloadJson: String,
            expectedRevision: Int,
            idempotencyKey: String,
            nextAttemptAt: Long,
        ) {
            entries[id]?.let {
                entries[id] = it.copy(
                    payloadJson = payloadJson,
                    expectedRevision = expectedRevision,
                    idempotencyKey = idempotencyKey,
                    attemptCount = 0,
                    nextAttemptAt = nextAttemptAt,
                    lastError = null,
                )
            }
        }
        override suspend fun countPending(): Int = entries.size
        override fun observePendingCount(): Flow<Int> = flowOf(entries.size)
    }

    private class FakeHubApi : HubApi {
        var onSync: (suspend (Int, PartySyncRequest) -> PartySyncResponse)? = null
        var onListCampaigns: (suspend () -> List<HubCampaignSummary>)? = null

        override suspend fun syncPartyMember(campaignId: Int, request: PartySyncRequest): PartySyncResponse {
            val handler = onSync ?: throw IllegalStateException("onSync not configured")
            return handler(campaignId, request)
        }
        override suspend fun getCampaignParty(campaignId: Int): List<Map<String, JsonElement>> = emptyList()
        override suspend fun listCampaigns(): List<HubCampaignSummary> =
            onListCampaigns?.invoke() ?: emptyList()
        override suspend fun ask(request: AskRequest): AskResponse = error("unused")
        override suspend fun createSoloCampaign(request: CreateCampaignRequest): CreateCampaignResponse = error("unused")
        override suspend fun takeSoloTurn(campaignId: Int, request: TurnRequest): TurnResponse = error("unused")
        override suspend fun getSoloState(campaignId: Int): SoloStateResponse = error("unused")
        override suspend fun resolveStrike(request: StrikeRequest): StrikeResponse = error("unused")
        override suspend fun setCombatScene(request: CombatSceneRequest): CombatSceneResponse = error("unused")
        override suspend fun endTurn(request: EndTurnRequest): EndTurnResponse = error("unused")
        override suspend fun generateLoot(request: GenerateRequest): LootResponse = error("unused")
        override suspend fun generateMap(request: MapRequest): MapGenerateResponse = error("unused")
        override suspend fun generateCharacter(request: BuildCharacterRequest): BuildCharacterResponse = error("unused")
        override suspend fun summarizeSession(request: SummarizeRequest): SummarizeResponse = error("unused")
        override suspend fun generateEncounter(request: EncounterRequest): EncounterResponse = error("unused")
    }

    private fun makeRepo(
        dao: FakeCharacterDao,
        api: FakeHubApi,
        outbox: FakeSyncOutboxDao,
        hub: () -> String,
        schedules: MutableList<Unit>,
    ): CharacterRepository =
        CharacterRepository(
            dao = dao,
            apiProvider = { api },
            hubUrlProvider = hub,
            bindingProvider = { HubBinding.of(hub(), { api }) },
            outboxDao = outbox,
            scheduleRetry = { schedules.add(Unit) },
        )

    private fun hero(id: Long = 1L, name: String = "Valeros", level: Int = 1): CharacterEntity =
        CharacterEntity(
            id = id,
            name = name,
            characterClass = "Fighter",
            level = level,
            uuid = "hero-valeros-1",
            hubUrl = DEFAULT_HUB,
            campaignId = 1,
            serverRevision = 1,
        )

    private fun httpError(code: Int, body: String = """{"detail":"error"}"""): HttpException =
        HttpException(
            Response.error<PartySyncResponse>(
                code,
                body.toResponseBody("application/json".toMediaType()),
            ),
        )

    @Test
    fun networkFailureEnqueuesOutboxAndSchedulesRetry() = runBlocking {
        val dao = FakeCharacterDao()
        val api = FakeHubApi()
        val outbox = FakeSyncOutboxDao()
        val schedules = mutableListOf<Unit>()
        val repo = makeRepo(dao, api, outbox, { DEFAULT_HUB }, schedules)
        dao.upsert(hero())
        var attempted: PartySyncRequest? = null
        api.onSync = { _, req ->
            attempted = req
            throw IOException("Failed to connect")
        }

        val result = repo.syncCharacter(1L, campaignId = 1)

        assertTrue(result is CharacterSyncResult.Error)
        assertEquals("network_error", dao.getById(1L)?.syncStatus)
        val entry = outbox.entryForCharacter(1L)
        assertNotNull(entry)
        assertEquals(attempted?.idempotencyKey, entry?.idempotencyKey)
        assertEquals(1, schedules.size)
    }

    @Test
    fun authFailureDoesNotEnqueue() = runBlocking {
        val dao = FakeCharacterDao()
        val api = FakeHubApi()
        val outbox = FakeSyncOutboxDao()
        val repo = makeRepo(dao, api, outbox, { DEFAULT_HUB }, mutableListOf())
        dao.upsert(hero())
        api.onSync = { _, _ -> throw httpError(403) }

        val result = repo.syncCharacter(1L, campaignId = 1)

        assertTrue(result is CharacterSyncResult.Error)
        assertEquals("auth_error", dao.getById(1L)?.syncStatus)
        assertNull(outbox.entryForCharacter(1L))
    }

    @Test
    fun notFoundDoesNotEnqueue() = runBlocking {
        val dao = FakeCharacterDao()
        val api = FakeHubApi()
        val outbox = FakeSyncOutboxDao()
        val repo = makeRepo(dao, api, outbox, { DEFAULT_HUB }, mutableListOf())
        dao.upsert(hero())
        api.onSync = { _, _ -> throw httpError(404) }

        repo.syncCharacter(1L, campaignId = 1)

        assertEquals("campaign_not_found", dao.getById(1L)?.syncStatus)
        assertNull(outbox.entryForCharacter(1L))
    }

    @Test
    fun conflictDoesNotEnqueue() = runBlocking {
        val dao = FakeCharacterDao()
        val api = FakeHubApi()
        val outbox = FakeSyncOutboxDao()
        val repo = makeRepo(dao, api, outbox, { DEFAULT_HUB }, mutableListOf())
        dao.upsert(hero())
        api.onSync = { _, _ ->
            throw httpError(
                409,
                """{"detail":{"error":"conflict","current_revision":2,"expected_revision":1,"server_character":{"id":10,"uuid":"hero-valeros-1","name":"Valeros Server","level":2}}}""",
            )
        }

        val result = repo.syncCharacter(1L, campaignId = 1)

        assertTrue(result is CharacterSyncResult.Conflict)
        assertEquals("conflict", dao.getById(1L)?.syncStatus)
        assertNull(outbox.entryForCharacter(1L))
    }

    @Test
    fun serverErrorEnqueues() = runBlocking {
        val dao = FakeCharacterDao()
        val api = FakeHubApi()
        val outbox = FakeSyncOutboxDao()
        val repo = makeRepo(dao, api, outbox, { DEFAULT_HUB }, mutableListOf())
        dao.upsert(hero())
        api.onSync = { _, _ -> throw httpError(500) }

        repo.syncCharacter(1L, campaignId = 1)

        assertEquals("error", dao.getById(1L)?.syncStatus)
        assertNotNull(outbox.entryForCharacter(1L))
    }

    @Test
    fun successClearsOutbox() = runBlocking {
        val dao = FakeCharacterDao()
        val api = FakeHubApi()
        val outbox = FakeSyncOutboxDao()
        val repo = makeRepo(dao, api, outbox, { DEFAULT_HUB }, mutableListOf())
        dao.upsert(hero())
        api.onSync = { _, _ -> throw IOException("down") }
        repo.syncCharacter(1L, campaignId = 1)
        assertNotNull(outbox.entryForCharacter(1L))

        api.onSync = { _, req ->
            PartySyncResponse(10, req.uuid, req.name, 2, "2026-11-17T00:00:00Z", "synced")
        }
        val result = repo.syncCharacter(1L, campaignId = 1)

        assertTrue(result is CharacterSyncResult.Success)
        assertNull(outbox.entryForCharacter(1L))
        assertEquals("synced", dao.getById(1L)?.syncStatus)
    }

    @Test
    fun replayDeliversStoredPayloadVerbatim() = runBlocking {
        val dao = FakeCharacterDao()
        val api = FakeHubApi()
        val outbox = FakeSyncOutboxDao()
        val repo = makeRepo(dao, api, outbox, { DEFAULT_HUB }, mutableListOf())
        dao.upsert(hero())
        var first: PartySyncRequest? = null
        api.onSync = { _, req ->
            first = req
            throw IOException("down")
        }
        repo.syncCharacter(1L, campaignId = 1)
        val storedKey = first?.idempotencyKey
        assertNotNull(storedKey)

        var replayed: PartySyncRequest? = null
        api.onSync = { _, req ->
            replayed = req
            PartySyncResponse(10, req.uuid, req.name, 2, "2026-11-17T00:00:00Z", "synced")
        }
        val processed = repo.replayDueOutboxEntries(System.currentTimeMillis() + 60_000)

        assertEquals(1, processed)
        assertEquals(storedKey, replayed?.idempotencyKey)
        assertEquals(first?.stats, replayed?.stats)
        assertEquals(first?.expectedRevision, replayed?.expectedRevision)
        assertNull(outbox.entryForCharacter(1L))
        assertEquals("synced", dao.getById(1L)?.syncStatus)
        assertEquals(2, dao.getById(1L)?.serverRevision)
    }

    @Test
    fun replayReplacesStalePayloadWithFreshSync() = runBlocking {
        val dao = FakeCharacterDao()
        val api = FakeHubApi()
        val outbox = FakeSyncOutboxDao()
        val repo = makeRepo(dao, api, outbox, { DEFAULT_HUB }, mutableListOf())
        dao.upsert(hero())
        api.onSync = { _, _ -> throw IOException("down") }
        repo.syncCharacter(1L, campaignId = 1)
        assertNotNull(outbox.entryForCharacter(1L))

        // The user edits the sheet while the Hub is down.
        val edited = dao.getById(1L)!!.copy(level = 4)
        dao.upsert(edited)
        var seenLevel: Int? = null
        api.onSync = { _, req ->
            seenLevel = req.level
            PartySyncResponse(10, req.uuid, req.name, 2, "2026-11-17T00:00:00Z", "synced")
        }
        val processed = repo.replayDueOutboxEntries(System.currentTimeMillis() + 60_000)

        assertEquals(1, processed)
        assertEquals(4, seenLevel)
        assertNull(outbox.entryForCharacter(1L))
        assertEquals("synced", dao.getById(1L)?.syncStatus)
    }

    @Test
    fun replayBacksOffAfterRetryableFailure() = runBlocking {
        val dao = FakeCharacterDao()
        val api = FakeHubApi()
        val outbox = FakeSyncOutboxDao()
        val repo = makeRepo(dao, api, outbox, { DEFAULT_HUB }, mutableListOf())
        dao.upsert(hero())
        api.onSync = { _, _ -> throw IOException("down") }
        repo.syncCharacter(1L, campaignId = 1)
        val firstAttemptAt = System.currentTimeMillis() + 60_000

        val processed = repo.replayDueOutboxEntries(firstAttemptAt)

        assertEquals(1, processed)
        val entry = outbox.entryForCharacter(1L)
        assertNotNull(entry)
        assertEquals(1, entry?.attemptCount)
        assertEquals(firstAttemptAt + 120_000L, entry?.nextAttemptAt)
        // Not due yet: the next sweep finds nothing to do.
        assertEquals(0, repo.replayDueOutboxEntries(firstAttemptAt + 60_000))
    }

    @Test
    fun replayDropsEntryOnConflict() = runBlocking {
        val dao = FakeCharacterDao()
        val api = FakeHubApi()
        val outbox = FakeSyncOutboxDao()
        val repo = makeRepo(dao, api, outbox, { DEFAULT_HUB }, mutableListOf())
        dao.upsert(hero())
        api.onSync = { _, _ -> throw IOException("down") }
        repo.syncCharacter(1L, campaignId = 1)
        assertNotNull(outbox.entryForCharacter(1L))

        api.onSync = { _, _ ->
            throw httpError(
                409,
                """{"detail":{"error":"conflict","current_revision":2,"expected_revision":1,"server_character":{"id":10,"uuid":"hero-valeros-1","name":"Valeros Server","level":2}}}""",
            )
        }
        repo.replayDueOutboxEntries(System.currentTimeMillis() + 60_000)

        assertNull(outbox.entryForCharacter(1L))
        assertEquals("conflict", dao.getById(1L)?.syncStatus)
    }

    @Test
    fun replaySkipsEntryForOtherHub() = runBlocking {
        val dao = FakeCharacterDao()
        val api = FakeHubApi()
        val outbox = FakeSyncOutboxDao()
        var currentHub = DEFAULT_HUB
        val repo = makeRepo(dao, api, outbox, { currentHub }, mutableListOf())
        dao.upsert(hero())
        api.onSync = { _, _ -> throw IOException("down") }
        repo.syncCharacter(1L, campaignId = 1)
        assertNotNull(outbox.entryForCharacter(1L))

        // The user moved Settings to another Hub; the worker must not
        // deliver the queued attempt there.
        currentHub = "http://10.9.9.9:8000"
        var calls = 0
        api.onSync = { _, req ->
            calls++
            PartySyncResponse(10, req.uuid, req.name, 2, "2026-11-17T00:00:00Z", "synced")
        }
        val processed = repo.replayDueOutboxEntries(System.currentTimeMillis() + 60_000)

        assertEquals(1, processed)
        assertEquals(0, calls)
        assertNotNull(outbox.entryForCharacter(1L))
    }

    @Test
    fun keepMineRepushesAtServerRevision() = runBlocking {
        val dao = FakeCharacterDao()
        val api = FakeHubApi()
        val outbox = FakeSyncOutboxDao()
        val repo = makeRepo(dao, api, outbox, { DEFAULT_HUB }, mutableListOf())
        dao.upsert(hero())
        api.onSync = { _, _ ->
            throw httpError(
                409,
                """{"detail":{"error":"conflict","current_revision":2,"expected_revision":1,"server_character":{"id":10,"uuid":"hero-valeros-1","name":"Valeros Server","level":2}}}""",
            )
        }
        val conflict = repo.syncCharacter(1L, campaignId = 1)
        assertTrue(conflict is CharacterSyncResult.Conflict)

        var seenRevision: Int? = null
        api.onSync = { _, req ->
            seenRevision = req.expectedRevision
            PartySyncResponse(10, req.uuid, req.name, 3, "2026-11-17T00:00:00Z", "synced")
        }
        val result = repo.resolveConflictKeepMine(1L, 2, campaignId = 1)

        assertTrue(result is CharacterSyncResult.Success)
        assertEquals(2, seenRevision)
        assertEquals(3, (result as CharacterSyncResult.Success).revision)
        assertEquals("synced", dao.getById(1L)?.syncStatus)
        assertEquals(3, dao.getById(1L)?.serverRevision)
    }

    @Test
    fun useServerAdoptsServerRow() = runBlocking {
        val dao = FakeCharacterDao()
        val api = FakeHubApi()
        val outbox = FakeSyncOutboxDao()
        val repo = makeRepo(dao, api, outbox, { DEFAULT_HUB }, mutableListOf())
        dao.upsert(hero(name = "Valeros Local", level = 3))
        val serverCharacter = Json.parseToJsonElement(
            """
            {
              "id": 10,
              "uuid": "hero-valeros-1",
              "name": "Valeros Server",
              "revision": 2,
              "updated_at": "2026-11-17T00:00:00Z",
              "stats": {
                "uuid": "hero-valeros-1",
                "name": "Valeros Server",
                "level": 5,
                "class": "Fighter",
                "character_class": "Fighter",
                "ancestry": "Human"
              }
            }
            """.trimIndent(),
        ) as JsonObject

        val result = repo.resolveConflictUseServer(1L, serverCharacter)

        assertTrue(result is CharacterSyncResult.Success)
        assertEquals(2, (result as CharacterSyncResult.Success).revision)
        val adopted = dao.getById(1L)
        assertEquals("Valeros Server", adopted?.name)
        assertEquals(5, adopted?.level)
        assertEquals("Human", adopted?.ancestry)
        assertEquals(2, adopted?.serverRevision)
        assertEquals("synced", adopted?.syncStatus)
        assertEquals("2026-11-17T00:00:00Z", adopted?.lastSyncedAt)
        assertEquals("hero-valeros-1", adopted?.uuid)
    }

    @Test
    fun verifyHandsetDistinguishesFailures() = runBlocking {
        val dao = FakeCharacterDao()
        val api = FakeHubApi()
        val outbox = FakeSyncOutboxDao()
        val repo = makeRepo(dao, api, outbox, { DEFAULT_HUB }, mutableListOf())

        api.onListCampaigns = { listOf(HubCampaignSummary(1, "Test Campaign")) }
        assertTrue(repo.verifyHandsetAuth() is HandsetAuthResult.Ok)

        api.onListCampaigns = { throw httpError(401) }
        val auth = repo.verifyHandsetAuth()
        assertTrue(auth is HandsetAuthResult.AuthFailed)
        assertEquals(401, (auth as HandsetAuthResult.AuthFailed).statusCode)

        api.onListCampaigns = { throw SSLException("certificate pin mismatch") }
        assertTrue(repo.verifyHandsetAuth() is HandsetAuthResult.TlsFailed)

        api.onListCampaigns = { throw IOException("Failed to connect") }
        assertTrue(repo.verifyHandsetAuth() is HandsetAuthResult.Unreachable)
    }

    @Test
    fun backoffSchedule() {
        assertEquals(30_000L, CharacterRepository.outboxBackoffMillis(0))
        assertEquals(120_000L, CharacterRepository.outboxBackoffMillis(1))
        assertEquals(600_000L, CharacterRepository.outboxBackoffMillis(2))
        assertEquals(3_600_000L, CharacterRepository.outboxBackoffMillis(3))
        assertEquals(3_600_000L, CharacterRepository.outboxBackoffMillis(10))
    }

    @Test
    fun clearQueuedSyncDiscardsEntry() = runBlocking {
        val dao = FakeCharacterDao()
        val api = FakeHubApi()
        val outbox = FakeSyncOutboxDao()
        val repo = makeRepo(dao, api, outbox, { DEFAULT_HUB }, mutableListOf())
        dao.upsert(hero())
        api.onSync = { _, _ -> throw IOException("down") }
        repo.syncCharacter(1L, campaignId = 1)
        assertNotNull(outbox.entryForCharacter(1L))

        repo.clearQueuedSync(1L)

        assertNull(outbox.entryForCharacter(1L))
        assertEquals("network_error", dao.getById(1L)?.syncStatus)
    }
}
