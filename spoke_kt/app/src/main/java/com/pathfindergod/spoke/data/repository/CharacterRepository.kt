// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.repository

import com.pathfindergod.spoke.data.local.AppDatabase
import com.pathfindergod.spoke.data.local.CharacterDao
import com.pathfindergod.spoke.data.local.CharacterEntity
import com.pathfindergod.spoke.data.network.BuildCharacterRequest
import com.pathfindergod.spoke.data.network.BuildCharacterResponse
import com.pathfindergod.spoke.data.network.HubApi
import com.pathfindergod.spoke.data.network.PartySyncRequest
import java.security.MessageDigest
import javax.net.ssl.SSLException
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.Flow
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.intOrNull

sealed class CharacterSyncResult {
    data class Success(val revision: Int) : CharacterSyncResult()
    data class Conflict(val currentRevision: Int, val serverCharacter: Map<String, JsonElement>?) : CharacterSyncResult()
    data class Error(val message: String, val statusCode: Int? = null) : CharacterSyncResult()
}

class CharacterRepository(
    private val dao: CharacterDao,
    private val apiProvider: () -> HubApi,
) {
    constructor(dao: CharacterDao, api: HubApi) : this(dao, { api })
    constructor(db: AppDatabase, api: HubApi) : this(db.characterDao(), { api })
    constructor(db: AppDatabase, apiProvider: () -> HubApi) : this(db.characterDao(), apiProvider)

    fun observeCharacters(): Flow<List<CharacterEntity>> =
        dao.observeAll()

    suspend fun getCharacter(id: Long): CharacterEntity? =
        dao.getById(id)

    suspend fun saveCharacter(entity: CharacterEntity): Long =
        dao.upsert(entity)

    suspend fun forgeCharacter(prompt: String): BuildCharacterResponse =
        apiProvider().generateCharacter(BuildCharacterRequest(prompt))

    suspend fun deleteCharacter(id: Long) {
        dao.delete(id)
    }

    suspend fun characterCount(): Int = dao.count()

    private fun computeIdempotencyKey(
        campaignId: Int,
        uuid: String,
        expectedRevision: Int,
        stats: Map<String, JsonElement>,
    ): String {
        val payload = "$campaignId|$uuid|$expectedRevision|${JsonObject(stats)}"
        val digest = MessageDigest.getInstance("SHA-256")
            .digest(payload.toByteArray(Charsets.UTF_8))
        val hex = digest.joinToString("") { "%02x".format(it) }
        return "sync-${hex.take(48)}"
    }

    suspend fun syncCharacter(
        characterId: Long,
        campaignId: Int? = null,
        idempotencyKey: String? = null,
    ): CharacterSyncResult {
        val entity = dao.getById(characterId)
            ?: return CharacterSyncResult.Error("Character not found")

        val effectiveUuid = entity.uuid.trim().ifEmpty {
            java.util.UUID.randomUUID().toString()
        }
        val activeEntity = if (effectiveUuid != entity.uuid) {
            val updated = entity.copy(uuid = effectiveUuid)
            dao.upsert(updated)
            updated
        } else {
            entity
        }

        val targetCampaignId = (campaignId ?: activeEntity.campaignId).coerceAtLeast(1)
        val expectedRevision = if (targetCampaignId == activeEntity.campaignId) {
            activeEntity.serverRevision ?: 0
        } else {
            0
        }

        val wireStats = CharacterMapper.toWire(activeEntity)
        val idemp = idempotencyKey ?: computeIdempotencyKey(
            campaignId = targetCampaignId,
            uuid = effectiveUuid,
            expectedRevision = expectedRevision,
            stats = wireStats,
        )
        val request = PartySyncRequest(
            uuid = effectiveUuid,
            name = activeEntity.name,
            characterClass = activeEntity.characterClass,
            level = activeEntity.level,
            ancestry = activeEntity.ancestry,
            background = activeEntity.background,
            stats = wireStats,
            expectedRevision = expectedRevision,
            idempotencyKey = idemp,
        )

        return try {
            val response = apiProvider().syncPartyMember(targetCampaignId, request)
            dao.updateSyncState(
                id = characterId,
                uuid = effectiveUuid,
                campaignId = targetCampaignId,
                serverRevision = response.revision,
                syncStatus = "synced",
                lastSyncedAt = response.updatedAt,
            )
            CharacterSyncResult.Success(response.revision)
        } catch (e: CancellationException) {
            throw e
        } catch (e: retrofit2.HttpException) {
            val code = e.code()
            if (code == 409) {
                val errorBody = e.response()?.errorBody()?.string().orEmpty()
                var currentRevision = (activeEntity.serverRevision ?: 1) + 1
                var serverChar: Map<String, JsonElement>? = null
                try {
                    val jsonElement = Json.parseToJsonElement(errorBody)
                    if (jsonElement is JsonObject) {
                        val detail = jsonElement["detail"]
                        if (detail is JsonObject) {
                            detail["current_revision"]?.let {
                                if (it is JsonPrimitive) currentRevision = it.intOrNull ?: currentRevision
                            }
                            val serverCharElement = detail["server_character"]
                            if (serverCharElement is JsonObject) {
                                serverChar = serverCharElement
                            }
                        }
                    }
                } catch (_: Exception) {
                }
                dao.updateSyncState(
                    id = characterId,
                    uuid = effectiveUuid,
                    campaignId = activeEntity.campaignId,
                    serverRevision = activeEntity.serverRevision,
                    syncStatus = "conflict",
                    lastSyncedAt = activeEntity.lastSyncedAt,
                )
                CharacterSyncResult.Conflict(currentRevision, serverChar)
            } else if (code == 401 || code == 403) {
                dao.updateSyncState(
                    id = characterId,
                    uuid = effectiveUuid,
                    campaignId = activeEntity.campaignId,
                    serverRevision = activeEntity.serverRevision,
                    syncStatus = "auth_error",
                    lastSyncedAt = activeEntity.lastSyncedAt,
                )
                CharacterSyncResult.Error("Authentication failed ($code)", code)
            } else {
                dao.updateSyncState(
                    id = characterId,
                    uuid = effectiveUuid,
                    campaignId = activeEntity.campaignId,
                    serverRevision = activeEntity.serverRevision,
                    syncStatus = "error",
                    lastSyncedAt = activeEntity.lastSyncedAt,
                )
                CharacterSyncResult.Error("HTTP error $code", code)
            }
        } catch (e: SSLException) {
            dao.updateSyncState(
                id = characterId,
                uuid = effectiveUuid,
                campaignId = activeEntity.campaignId,
                serverRevision = activeEntity.serverRevision,
                syncStatus = "tls_error",
                lastSyncedAt = activeEntity.lastSyncedAt,
            )
            CharacterSyncResult.Error(e.message ?: "TLS error")
        } catch (e: Exception) {
            dao.updateSyncState(
                id = characterId,
                uuid = effectiveUuid,
                campaignId = activeEntity.campaignId,
                serverRevision = activeEntity.serverRevision,
                syncStatus = "network_error",
                lastSyncedAt = activeEntity.lastSyncedAt,
            )
            CharacterSyncResult.Error(e.message ?: "Network error")
        }
    }
}
