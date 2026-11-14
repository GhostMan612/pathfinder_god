// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.repository

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
import com.pathfindergod.spoke.data.network.EndTurnRequest
import com.pathfindergod.spoke.data.network.EndTurnResponse
import com.pathfindergod.spoke.data.network.EncounterRequest
import com.pathfindergod.spoke.data.network.EncounterResponse
import com.pathfindergod.spoke.data.network.GenerateRequest
import com.pathfindergod.spoke.data.network.HubApi
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
import kotlinx.serialization.json.JsonElement
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import retrofit2.HttpException
import retrofit2.Response

class CharacterRepositorySyncTest {

    private class FakeCharacterDao(
        val characters: MutableMap<Long, CharacterEntity> = mutableMapOf(),
    ) : CharacterDao {
        var lastUpdatedSyncState: Triple<Long, Int?, String>? = null

        override fun observeAll(): Flow<List<CharacterEntity>> = flowOf(characters.values.toList())
        override suspend fun getById(id: Long): CharacterEntity? = characters[id]
        override suspend fun upsert(entity: CharacterEntity): Long {
            val id = if (entity.id == 0L) (characters.keys.maxOrNull() ?: 0L) + 1L else entity.id
            val saved = entity.copy(id = id)
            characters[id] = saved
            return id
        }
        override suspend fun delete(id: Long) { characters.remove(id) }
        override suspend fun count(): Int = characters.size
        override suspend fun getByUuid(uuid: String): CharacterEntity? =
            characters.values.firstOrNull { it.uuid == uuid }
        override suspend fun updateSyncState(
            id: Long,
            uuid: String,
            campaignId: Int,
            serverRevision: Int?,
            syncStatus: String,
            lastSyncedAt: String?,
        ) {
            lastUpdatedSyncState = Triple(id, serverRevision, syncStatus)
            val current = characters[id]
            if (current != null) {
                characters[id] = current.copy(
                    uuid = uuid,
                    campaignId = campaignId,
                    serverRevision = serverRevision,
                    syncStatus = syncStatus,
                    lastSyncedAt = lastSyncedAt,
                )
            }
        }
    }

    private class FakeHubApi : HubApi {
        var onSync: ((Int, PartySyncRequest) -> PartySyncResponse)? = null

        override suspend fun syncPartyMember(campaignId: Int, request: PartySyncRequest): PartySyncResponse {
            val handler = onSync ?: throw IllegalStateException("onSync not configured")
            return handler(campaignId, request)
        }

        override suspend fun getCampaignParty(campaignId: Int): List<Map<String, JsonElement>> = emptyList()
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

    @Test
    fun syncCharacterSuccessUpdatesRevisionAndStatus() = runBlocking {
        val dao = FakeCharacterDao()
        val api = FakeHubApi()
        val repo = CharacterRepository(dao, api)

        val hero = CharacterEntity(
            id = 1L,
            name = "Valeros",
            characterClass = "Fighter",
            level = 1,
            uuid = "hero-valeros-1",
        )
        dao.upsert(hero)

        api.onSync = { campaignId, req ->
            assertEquals(1, campaignId)
            assertEquals("hero-valeros-1", req.uuid)
            assertEquals("Valeros", req.name)
            PartySyncResponse(
                id = 10,
                uuid = req.uuid,
                name = req.name,
                revision = 1,
                updatedAt = "2026-11-12T00:00:00Z",
                status = "synced",
            )
        }

        val result = repo.syncCharacter(1L, campaignId = 1)
        assertTrue(result is CharacterSyncResult.Success)
        assertEquals(1, (result as CharacterSyncResult.Success).revision)

        val updated = dao.getById(1L)
        assertNotNull(updated)
        assertEquals(1, updated?.serverRevision)
        assertEquals("synced", updated?.syncStatus)
        assertEquals("2026-11-12T00:00:00Z", updated?.lastSyncedAt)
    }

    @Test
    fun syncCharacterConflictPreservesLocalData() = runBlocking {
        val dao = FakeCharacterDao()
        val api = FakeHubApi()
        val repo = CharacterRepository(dao, api)

        val localHero = CharacterEntity(
            id = 1L,
            name = "Valeros Local",
            characterClass = "Fighter",
            level = 3,
            uuid = "hero-valeros-1",
            serverRevision = 1,
            notes = "Local edits that must not be lost",
        )
        dao.upsert(localHero)

        api.onSync = { _, _ ->
            val conflictBody = """
                {
                  "detail": {
                    "error": "conflict",
                    "message": "Revision conflict: current revision is 2, expected 1",
                    "current_revision": 2,
                    "expected_revision": 1,
                    "server_character": {
                      "id": 10,
                      "uuid": "hero-valeros-1",
                      "name": "Valeros Server",
                      "level": 2
                    }
                  }
                }
            """.trimIndent()
            val response = Response.error<PartySyncResponse>(
                409,
                conflictBody.toResponseBody("application/json".toMediaType()),
            )
            throw HttpException(response)
        }

        val result = repo.syncCharacter(1L, campaignId = 1)
        assertTrue(result is CharacterSyncResult.Conflict)
        val conflict = result as CharacterSyncResult.Conflict
        assertEquals(2, conflict.currentRevision)
        assertNotNull(conflict.serverCharacter)

        val inDb = dao.getById(1L)
        assertNotNull(inDb)
        assertEquals("Valeros Local", inDb?.name)
        assertEquals(3, inDb?.level)
        assertEquals("Local edits that must not be lost", inDb?.notes)
        assertEquals(1, inDb?.serverRevision)
        assertEquals("conflict", inDb?.syncStatus)
    }

    @Test
    fun syncCharacterAuthFailurePreservesLocalData() = runBlocking {
        val dao = FakeCharacterDao()
        val api = FakeHubApi()
        val repo = CharacterRepository(dao, api)

        val localHero = CharacterEntity(
            id = 1L,
            name = "Seoni",
            characterClass = "Sorcerer",
            level = 1,
            uuid = "hero-seoni-1",
        )
        dao.upsert(localHero)

        api.onSync = { _, _ ->
            val response = Response.error<PartySyncResponse>(
                403,
                """{"detail":"Invalid API key"}""".toResponseBody("application/json".toMediaType()),
            )
            throw HttpException(response)
        }

        val result = repo.syncCharacter(1L, campaignId = 1)
        assertTrue(result is CharacterSyncResult.Error)
        assertEquals(403, (result as CharacterSyncResult.Error).statusCode)

        val inDb = dao.getById(1L)
        assertNotNull(inDb)
        assertEquals("Seoni", inDb?.name)
        assertEquals("auth_error", inDb?.syncStatus)
    }

    @Test
    fun syncCharacterNetworkFailurePreservesLocalData() = runBlocking {
        val dao = FakeCharacterDao()
        val api = FakeHubApi()
        val repo = CharacterRepository(dao, api)

        val localHero = CharacterEntity(
            id = 1L,
            name = "Kyra",
            characterClass = "Cleric",
            level = 2,
            uuid = "hero-kyra-1",
        )
        dao.upsert(localHero)

        api.onSync = { _, _ ->
            throw IOException("Failed to connect to /192.168.1.100:8000")
        }

        val result = repo.syncCharacter(1L, campaignId = 1)
        assertTrue(result is CharacterSyncResult.Error)

        val inDb = dao.getById(1L)
        assertNotNull(inDb)
        assertEquals("Kyra", inDb?.name)
        assertEquals("network_error", inDb?.syncStatus)
    }

    @Test
    fun syncCharacterNotFoundReturnsError() = runBlocking {
        val dao = FakeCharacterDao()
        val api = FakeHubApi()
        val repo = CharacterRepository(dao, api)

        val result = repo.syncCharacter(999L)
        assertTrue(result is CharacterSyncResult.Error)
        assertEquals("Character not found", (result as CharacterSyncResult.Error).message)
    }

    @Test
    fun syncCharacterRetryUsesDeterministicIdempotencyKeyAndChangesOnEdit() = runBlocking {
        val dao = FakeCharacterDao()
        val api = FakeHubApi()
        val repo = CharacterRepository(dao, api)

        val hero = CharacterEntity(
            id = 1L,
            name = "Amiri",
            characterClass = "Barbarian",
            level = 2,
            uuid = "hero-amiri-1",
            campaignId = 1,
        )
        dao.upsert(hero)

        val seenKeys = mutableListOf<String>()
        api.onSync = { _, req ->
            val key = req.idempotencyKey!!
            seenKeys += key
            if (seenKeys.size == 1) {
                throw IOException("Transient drop")
            }
            PartySyncResponse(
                id = 12,
                uuid = req.uuid,
                name = req.name,
                revision = 1,
                updatedAt = "2026-11-12T00:00:00Z",
                status = "synced",
            )
        }

        val firstAttempt = repo.syncCharacter(1L)
        assertTrue(firstAttempt is CharacterSyncResult.Error)

        val retryAttempt = repo.syncCharacter(1L)
        assertTrue(retryAttempt is CharacterSyncResult.Success)
        assertEquals(2, seenKeys.size)
        assertEquals(seenKeys[0], seenKeys[1])
        assertTrue(seenKeys[0].length <= 64)

        dao.upsert(dao.getById(1L)!!.copy(level = 3))
        api.onSync = { _, req ->
            seenKeys += req.idempotencyKey!!
            assertEquals(1, req.expectedRevision)
            PartySyncResponse(
                id = 12,
                uuid = req.uuid,
                name = req.name,
                revision = 2,
                updatedAt = "2026-11-12T00:01:00Z",
                status = "synced",
            )
        }
        val editedAttempt = repo.syncCharacter(1L)
        assertTrue(editedAttempt is CharacterSyncResult.Success)
        assertEquals(3, seenKeys.size)
        assertNotEquals(seenKeys[1], seenKeys[2])
    }

    @Test
    fun syncCharacterBackfillsBlankUuidBeforeRequest() = runBlocking {
        val dao = FakeCharacterDao()
        val api = FakeHubApi()
        val repo = CharacterRepository(dao, api)

        dao.upsert(
            CharacterEntity(
                id = 1L,
                name = "Ezren",
                characterClass = "Wizard",
                level = 1,
                uuid = "   ",
            ),
        )

        var capturedUuid = ""
        api.onSync = { _, req ->
            capturedUuid = req.uuid
            assertTrue(req.uuid.isNotBlank())
            PartySyncResponse(
                id = 15,
                uuid = req.uuid,
                name = req.name,
                revision = 1,
                updatedAt = "2026-11-12T00:00:00Z",
                status = "synced",
            )
        }

        val result = repo.syncCharacter(1L)
        assertTrue(result is CharacterSyncResult.Success)
        val stored = dao.getById(1L)!!
        assertEquals(capturedUuid, stored.uuid)
        assertTrue(stored.uuid.isNotBlank())
    }

    @Test
    fun syncCharacterTlsFailurePreservesLocalDataAndSetsTlsErrorStatus() = runBlocking {
        val dao = FakeCharacterDao()
        val api = FakeHubApi()
        val repo = CharacterRepository(dao, api)

        dao.upsert(
            CharacterEntity(
                id = 1L,
                name = "Merisiel",
                characterClass = "Rogue",
                level = 4,
                uuid = "hero-merisiel-1",
                serverRevision = 2,
                lastSyncedAt = "2026-11-11T00:00:00Z",
            ),
        )

        api.onSync = { _, _ ->
            throw SSLException("Certificate pinning failure")
        }

        val result = repo.syncCharacter(1L)
        assertTrue(result is CharacterSyncResult.Error)

        val stored = dao.getById(1L)!!
        assertEquals("Merisiel", stored.name)
        assertEquals(4, stored.level)
        assertEquals(2, stored.serverRevision)
        assertEquals("2026-11-11T00:00:00Z", stored.lastSyncedAt)
        assertEquals("tls_error", stored.syncStatus)
    }

    @Test
    fun syncCharacterToAnotherCampaignSendsExpectedRevisionZeroAndUpdatesCampaignOnlyOnSuccess() = runBlocking {
        val dao = FakeCharacterDao()
        val api = FakeHubApi()
        val repo = CharacterRepository(dao, api)

        dao.upsert(
            CharacterEntity(
                id = 1L,
                name = "Harsk",
                characterClass = "Ranger",
                level = 5,
                uuid = "hero-harsk-1",
                campaignId = 1,
                serverRevision = 3,
                lastSyncedAt = "2026-11-11T00:00:00Z",
            ),
        )

        api.onSync = { _, _ ->
            throw IOException("Offline")
        }
        val failedCross = repo.syncCharacter(1L, campaignId = 2)
        assertTrue(failedCross is CharacterSyncResult.Error)
        assertEquals(1, dao.getById(1L)!!.campaignId)
        assertEquals(3, dao.getById(1L)!!.serverRevision)

        api.onSync = { cid, req ->
            assertEquals(2, cid)
            assertEquals(0, req.expectedRevision)
            PartySyncResponse(
                id = 99,
                uuid = req.uuid,
                name = req.name,
                revision = 1,
                updatedAt = "2026-11-12T01:00:00Z",
                status = "synced",
            )
        }
        val succeededCross = repo.syncCharacter(1L, campaignId = 2)
        assertTrue(succeededCross is CharacterSyncResult.Success)
        val updated = dao.getById(1L)!!
        assertEquals(2, updated.campaignId)
        assertEquals(1, updated.serverRevision)
        assertEquals("synced", updated.syncStatus)
    }
}
