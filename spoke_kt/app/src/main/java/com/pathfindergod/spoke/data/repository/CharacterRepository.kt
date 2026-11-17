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

/**
 * One Hub endpoint paired with the client that talks to it.
 *
 * A sync attempt must never authorize against one Hub and then deliver to
 * another, so both halves are derived from a single Settings read and treated
 * as immutable for the whole attempt. Prefer [of]; [hubUrl] must be a
 * canonical origin (see `HubEndpoint.canonicalOrigin`).
 */
data class HubBinding(
    val hubUrl: String,
    val api: HubApi,
) {
    init {
        require(hubUrl.isNotBlank()) { "Hub URL is required" }
    }

    companion object {
        /**
         * Derive both halves from one raw Hub URL.
         *
         * Normalization happens once, so the identity used for campaign
         * authorization and idempotency and the client that carries the
         * request cannot disagree even if Settings changes immediately after
         * this call.
         */
        fun of(rawHubUrl: String, apiFor: (String) -> HubApi): HubBinding {
            val normalized = HubEndpoint.normalize(rawHubUrl)
            return HubBinding(HubEndpoint.canonicalOrigin(normalized), apiFor(normalized))
        }
    }
}

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
    private val bindingProvider: (() -> HubBinding)? = null,
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
        bindingProvider: (() -> HubBinding)? = null,
    ) : this(
        db.characterDao(),
        apiProvider,
        selectedCampaignIdProvider,
        onCampaignSelected,
        hubUrlProvider,
        bindingProvider,
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

    /**
     * Freeze the Hub destination for one sync attempt.
     *
     * With [bindingProvider] the caller supplies a URL/client pair built from a
     * single Settings read, so the two cannot disagree. The legacy fallback
     * cannot see inside [apiProvider], so it re-reads the identity around the
     * client construction and refuses to sync if it moved (or is blank).
     */
    private fun resolveHubBinding(): HubBinding? {
        bindingProvider?.let { return it() }
        val before = currentHubIdentity()
        val api = apiProvider()
        val after = currentHubIdentity()
        if (before != after || after.isBlank()) return null
        return HubBinding(after, api)
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

    /**
     * Pushes one character to the Hub campaign it belongs to.
     *
     * The attempt is bound to exactly one [HubBinding] before any state is
     * read: the campaign authorization, the idempotency key, the user-facing
     * cross-Hub prompt, and the delivered request all refer to that endpoint,
     * even if Settings changes mid-flight.
     *
     * @param confirmCrossHub the user approved transferring a character that
     *   belongs to another Hub.
     * @param confirmedHubUrl the destination the user was shown when they
     *   approved. When it no longer matches this attempt's binding, the
     *   approval is void and a fresh [CharacterSyncResult.CrossHubConfirmationRequired]
     *   is returned. Null means the approval is scoped to whatever endpoint
     *   this attempt bound (programmatic callers only; the UI always passes
     *   the prompted destination).
     */
    suspend fun syncCharacter(
        characterId: Long,
        campaignId: Int? = null,
        idempotencyKey: String? = null,
        confirmCrossHub: Boolean = false,
        confirmedHubUrl: String? = null,
    ): CharacterSyncResult {
        if (campaignId != null && campaignId < 1) {
            return CharacterSyncResult.Error("Invalid campaign ID")
        }
        // Bind before reading any row: everything below must agree on one Hub.
        val resolved = try {
            resolveHubBinding()
        } catch (e: IllegalArgumentException) {
            return CharacterSyncResult.Error(e.message ?: "Hub endpoint is not configured")
        }
        val binding = resolved
            ?: return CharacterSyncResult.Error("Hub endpoint changed while sync was starting; retry")
        val currentHub = binding.hubUrl

        val entity = dao.getById(characterId)
            ?: return CharacterSyncResult.Error("Character not found")

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
        // An approval names a destination. If Settings moved to another Hub
        // after the prompt was shown, that approval no longer covers this
        // attempt: ask again instead of transferring somewhere unapproved.
        val approvedHub = confirmedHubUrl?.let { raw ->
            try {
                HubEndpoint.canonicalOrigin(raw)
            } catch (_: IllegalArgumentException) {
                null
            }
        }
        val approvalCoversThisAttempt =
            confirmCrossHub && (confirmedHubUrl == null || approvedHub == currentHub)
        if (isCrossHubTransfer && !approvalCoversThisAttempt) {
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
            val response = binding.api.syncPartyMember(targetCampaignId, request)
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
