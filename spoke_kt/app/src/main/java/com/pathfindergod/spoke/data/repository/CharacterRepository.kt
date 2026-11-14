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
import com.pathfindergod.spoke.data.network.HubCampaignSummary
import com.pathfindergod.spoke.data.network.HubEndpoint
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
    data class LocalModifiedDuringSync(val serverRevision: Int) : CharacterSyncResult()
    data class CrossHubConfirmationRequired(
        val previousHubUrl: String,
        val targetHubUrl: String,
        val targetCampaignId: Int,
    ) : CharacterSyncResult()
    data class Conflict(val currentRevision: Int, val serverCharacter: Map<String, JsonElement>?) : CharacterSyncResult()
    data class Error(val message: String, val statusCode: Int? = null) : CharacterSyncResult()
}

class CharacterRepository(
    private val dao: CharacterDao,
    private val apiProvider: () -> HubApi,
    private val selectedCampaignIdProvider: () -> Int? = { null },
    private val onCampaignSelected: (Int) -> Unit = {},
    private val hubUrlProvider: () -> String = { HubEndpoint.DEFAULT_BASE_URL },
) {
    constructor(dao: CharacterDao, api: HubApi) : this(dao, { api })
    constructor(db: AppDatabase, api: HubApi) : this(db.characterDao(), { api })
    constructor(db: AppDatabase, apiProvider: () -> HubApi) : this(db.characterDao(), apiProvider)
    constructor(
        db: AppDatabase,
        apiProvider: () -> HubApi,
        selectedCampaignIdProvider: () -> Int?,
        onCampaignSelected: (Int) -> Unit,
        hubUrlProvider: () -> String = { HubEndpoint.DEFAULT_BASE_URL },
    ) : this(
        db.characterDao(),
        apiProvider,
        selectedCampaignIdProvider,
        onCampaignSelected,
        hubUrlProvider,
    )

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

    fun selectedCampaignId(): Int? =
        selectedCampaignIdProvider()?.takeIf { it >= 1 }

    fun setSelectedCampaignId(campaignId: Int) {
        if (campaignId >= 1) {
            onCampaignSelected(campaignId)
        }
    }

    fun currentHubIdentity(): String {
        val raw = hubUrlProvider().trim()
        if (raw.isEmpty()) return ""
        return try {
            HubEndpoint.canonicalOrigin(raw)
        } catch (_: IllegalArgumentException) {
            raw.lowercase()
        }
    }

    suspend fun listHubCampaigns(): List<HubCampaignSummary> =
        apiProvider().listCampaigns()

    private fun computeIdempotencyKey(
        hubIdentity: String,
        campaignId: Int,
        uuid: String,
        expectedRevision: Int,
        stats: Map<String, JsonElement>,
    ): String {
        val payload = "$hubIdentity|$campaignId|$uuid|$expectedRevision|${JsonObject(stats)}"
        val digest = MessageDigest.getInstance("SHA-256")
            .digest(payload.toByteArray(Charsets.UTF_8))
        val hex = digest.joinToString("") { "%02x".format(it) }
        return "sync-${hex.take(48)}"
    }

    suspend fun syncCharacter(
        characterId: Long,
        campaignId: Int? = null,
        idempotencyKey: String? = null,
        confirmCrossHub: Boolean = false,
    ): CharacterSyncResult {
        if (campaignId != null && campaignId < 1) {
            return CharacterSyncResult.Error("Invalid campaign ID")
        }
        val entity = dao.getById(characterId)
            ?: return CharacterSyncResult.Error("Character not found")

        val currentHub = currentHubIdentity()
        val effectiveUuid = if (entity.uuid.isBlank()) {
            val candidate = java.util.UUID.randomUUID().toString()
            dao.backfillUuidIfBlank(characterId, candidate)
            dao.getById(characterId)?.uuid?.trim().orEmpty().ifEmpty { candidate }
        } else {
            entity.uuid.trim()
        }
        val activeEntity = (dao.getById(characterId) ?: entity).let {
            if (it.uuid != effectiveUuid) it.copy(uuid = effectiveUuid) else it
        }

        val boundToCurrentHub = !activeEntity.hubUrl.isNullOrBlank() && activeEntity.hubUrl == currentHub
        val boundCampaignId = if (boundToCurrentHub) activeEntity.campaignId else null
        val targetCampaignId = (campaignId ?: boundCampaignId ?: selectedCampaignIdProvider())
            ?.takeIf { it >= 1 }
            ?: run {
                dao.commitSyncFailure(characterId, activeEntity, effectiveUuid, "campaign_required")
                return CharacterSyncResult.Error("Select a Hub campaign before syncing")
            }

        val previousHub = activeEntity.hubUrl?.trim()?.ifEmpty { null }
        val isCrossHubTransfer =
            (previousHub != null && previousHub != currentHub) ||
                (previousHub == null && activeEntity.serverRevision != null)
        if (!confirmCrossHub && isCrossHubTransfer) {
            return CharacterSyncResult.CrossHubConfirmationRequired(
                previousHubUrl = previousHub.orEmpty(),
                targetHubUrl = currentHub,
                targetCampaignId = targetCampaignId,
            )
        }

        val expectedRevision = if (boundToCurrentHub && targetCampaignId == activeEntity.campaignId) {
            activeEntity.serverRevision ?: 0
        } else {
            0
        }

        val wireStats = CharacterMapper.toWire(activeEntity)
        val idemp = idempotencyKey ?: computeIdempotencyKey(
            hubIdentity = currentHub,
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
            val committed = dao.commitSyncSuccess(
                id = characterId,
                snapshot = activeEntity,
                uuid = effectiveUuid,
                hubUrl = currentHub,
                campaignId = targetCampaignId,
                serverRevision = response.revision,
                lastSyncedAt = response.updatedAt,
            )
            if (committed) {
                CharacterSyncResult.Success(response.revision)
            } else {
                CharacterSyncResult.LocalModifiedDuringSync(response.revision)
            }
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
                dao.commitSyncFailure(characterId, activeEntity, effectiveUuid, "conflict")
                CharacterSyncResult.Conflict(currentRevision, serverChar)
            } else if (code == 401 || code == 403) {
                dao.commitSyncFailure(characterId, activeEntity, effectiveUuid, "auth_error")
                CharacterSyncResult.Error("Authentication failed ($code)", code)
            } else if (code == 404) {
                dao.commitSyncFailure(characterId, activeEntity, effectiveUuid, "campaign_not_found")
                CharacterSyncResult.Error("Campaign $targetCampaignId does not exist on Hub", code)
            } else {
                dao.commitSyncFailure(characterId, activeEntity, effectiveUuid, "error")
                CharacterSyncResult.Error("HTTP error $code", code)
            }
        } catch (e: SSLException) {
            dao.commitSyncFailure(characterId, activeEntity, effectiveUuid, "tls_error")
            CharacterSyncResult.Error(e.message ?: "TLS error")
        } catch (e: Exception) {
            dao.commitSyncFailure(characterId, activeEntity, effectiveUuid, "network_error")
            CharacterSyncResult.Error(e.message ?: "Network error")
        }
    }
}
