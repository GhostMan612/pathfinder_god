// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.repository

import com.pathfindergod.spoke.data.local.AppDatabase
import com.pathfindergod.spoke.data.local.CharacterDao
import com.pathfindergod.spoke.data.local.CharacterEntity
import com.pathfindergod.spoke.data.local.SyncOutboxDao
import com.pathfindergod.spoke.data.local.SyncOutboxEntry
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
import kotlinx.coroutines.flow.flowOf
import kotlinx.serialization.decodeFromString
import kotlinx.serialization.encodeToString
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

/**
 * Outcome of the authenticated-handset check (Issue #33 Phase 4).
 *
 * A lightweight `GET /campaign/list` — authenticated whenever the Hub has a
 * key configured — distinguishes the three failure modes the issue calls out:
 * wrong credentials (401/403), a TLS/pin failure, and the Hub simply being
 * unreachable. `Ok` means the handset reached the Hub over valid TLS and the
 * Hub accepted its credentials (or has no key configured).
 */
sealed class HandsetAuthResult {
    data object Ok : HandsetAuthResult()
    data class AuthFailed(val statusCode: Int) : HandsetAuthResult()
    data object TlsFailed : HandsetAuthResult()
    data class Unreachable(val message: String) : HandsetAuthResult()
}

class CharacterRepository(
    private val dao: CharacterDao,
    private val apiProvider: () -> HubApi,
    private val selectedCampaignIdProvider: () -> Int? = { null },
    private val onCampaignSelected: (Int) -> Unit = {},
    private val hubUrlProvider: () -> String = { HubEndpoint.DEFAULT_BASE_URL },
    private val bindingProvider: (() -> HubBinding)? = null,
    private val outboxDao: SyncOutboxDao? = null,
    private val scheduleRetry: () -> Unit = {},
) {
    constructor(dao: CharacterDao, api: HubApi) : this(dao, { api })
    constructor(db: AppDatabase, api: HubApi) : this(
        db.characterDao(),
        { api },
        outboxDao = db.syncOutboxDao(),
    )
    constructor(db: AppDatabase, apiProvider: () -> HubApi) : this(
        db.characterDao(),
        apiProvider,
        outboxDao = db.syncOutboxDao(),
    )
    constructor(
        db: AppDatabase,
        apiProvider: () -> HubApi,
        selectedCampaignIdProvider: () -> Int?,
        onCampaignSelected: (Int) -> Unit,
        hubUrlProvider: () -> String = { HubEndpoint.DEFAULT_BASE_URL },
        bindingProvider: (() -> HubBinding)? = null,
        scheduleRetry: () -> Unit = {},
    ) : this(
        db.characterDao(),
        apiProvider,
        selectedCampaignIdProvider,
        onCampaignSelected,
        hubUrlProvider,
        bindingProvider,
        outboxDao = db.syncOutboxDao(),
        scheduleRetry = scheduleRetry,
    )

    companion object {
        /** Outbox payloads are serialized with this instance (round-trip only). */
        private val OutboxJson = Json { ignoreUnknownKeys = true }

        /** First retry 30s after a failed attempt. */
        const val OUTBOX_FIRST_RETRY_MS = 30_000L

        /**
         * Backoff between outbox replays: 30s, 2m, 10m, then 1h forever.
         * Entries are never dropped for a retryable failure, so the delay
         * caps instead of the attempts.
         */
        fun outboxBackoffMillis(attemptCount: Int): Long = when {
            attemptCount <= 0 -> 30_000L
            attemptCount == 1 -> 120_000L
            attemptCount == 2 -> 600_000L
            else -> 3_600_000L
        }
    }

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

        val request = buildSyncRequest(
            entity = activeEntity,
            uuid = effectiveUuid,
            hubUrl = currentHub,
            campaignId = targetCampaignId,
            expectedRevision = expectedRevision,
            idempotencyKey = idempotencyKey,
        )
        return deliverSyncRequest(
            binding = binding,
            characterId = characterId,
            snapshot = activeEntity,
            uuid = effectiveUuid,
            campaignId = targetCampaignId,
            request = request,
        )
    }

    /**
     * Build the wire request for one character row.
     *
     * Pure: the idempotency key is derived from the Hub identity, campaign,
     * uuid, expected revision and wire stats, so the same row state always
     * produces the same key and the Hub dedupes a replayed attempt.
     */
    private fun buildSyncRequest(
        entity: CharacterEntity,
        uuid: String,
        hubUrl: String,
        campaignId: Int,
        expectedRevision: Int,
        idempotencyKey: String? = null,
    ): PartySyncRequest {
        val wireStats = CharacterMapper.toWire(entity)
        val idemp = idempotencyKey ?: computeIdempotencyKey(
            hubIdentity = hubUrl,
            campaignId = campaignId,
            uuid = uuid,
            expectedRevision = expectedRevision,
            stats = wireStats,
        )
        return PartySyncRequest(
            uuid = uuid,
            name = entity.name,
            characterClass = entity.characterClass,
            level = entity.level,
            ancestry = entity.ancestry,
            background = entity.background,
            stats = wireStats,
            expectedRevision = expectedRevision,
            idempotencyKey = idemp,
        )
    }

    /**
     * POST one sync request and record the outcome.
     *
     * This is the single delivery path for both a live `syncCharacter` call
     * and an outbox replay, so a retry can never diverge from the original
     * attempt. On a retryable failure (network down, TLS failure, Hub 5xx)
     * the exact attempted request is queued in the durable outbox; on
     * success any queued entry for the character is cleared. A 409, a
     * 401/403 and a 404 are never queued: a conflict belongs to the user to
     * resolve, and auth / missing-campaign failures cannot heal by retrying.
     */
    private suspend fun deliverSyncRequest(
        binding: HubBinding,
        characterId: Long,
        snapshot: CharacterEntity,
        uuid: String,
        campaignId: Int,
        request: PartySyncRequest,
    ): CharacterSyncResult {
        val currentHub = binding.hubUrl
        return try {
            val response = binding.api.syncPartyMember(campaignId, request)
            val committed = dao.commitSyncSuccess(
                id = characterId,
                snapshot = snapshot,
                uuid = uuid,
                hubUrl = currentHub,
                campaignId = campaignId,
                serverRevision = response.revision,
                lastSyncedAt = response.updatedAt,
            )
            if (committed) {
                outboxDao?.deleteForCharacter(characterId)
                CharacterSyncResult.Success(response.revision)
            } else {
                // The sheet moved while the request was in flight. Queue the
                // fresh row state so the edit is not lost to a manual re-sync.
                enqueueFresh(characterId, currentHub, campaignId)
                CharacterSyncResult.LocalModifiedDuringSync(response.revision)
            }
        } catch (e: CancellationException) {
            throw e
        } catch (e: retrofit2.HttpException) {
            val code = e.code()
            if (code == 409) {
                val errorBody = e.response()?.errorBody()?.string().orEmpty()
                var currentRevision = (snapshot.serverRevision ?: 1) + 1
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
                dao.commitSyncFailure(characterId, snapshot, uuid, "conflict")
                CharacterSyncResult.Conflict(currentRevision, serverChar)
            } else if (code == 401 || code == 403) {
                dao.commitSyncFailure(characterId, snapshot, uuid, "auth_error")
                CharacterSyncResult.Error("Authentication failed ($code)", code)
            } else if (code == 404) {
                dao.commitSyncFailure(characterId, snapshot, uuid, "campaign_not_found")
                CharacterSyncResult.Error("Campaign $campaignId does not exist on Hub", code)
            } else if (code >= 500) {
                dao.commitSyncFailure(characterId, snapshot, uuid, "error")
                enqueueOutbox(characterId, uuid, currentHub, campaignId, request, "HTTP error $code")
                CharacterSyncResult.Error("HTTP error $code", code)
            } else {
                dao.commitSyncFailure(characterId, snapshot, uuid, "error")
                CharacterSyncResult.Error("HTTP error $code", code)
            }
        } catch (e: SSLException) {
            dao.commitSyncFailure(characterId, snapshot, uuid, "tls_error")
            enqueueOutbox(characterId, uuid, currentHub, campaignId, request, e.message ?: "TLS error")
            CharacterSyncResult.Error(e.message ?: "TLS error")
        } catch (e: Exception) {
            dao.commitSyncFailure(characterId, snapshot, uuid, "network_error")
            enqueueOutbox(characterId, uuid, currentHub, campaignId, request, e.message ?: "Network error")
            CharacterSyncResult.Error(e.message ?: "Network error")
        }
    }

    /**
     * Queue the exact request that was just attempted for a later replay.
     *
     * No-op when the repository was built without an outbox DAO (unit tests
     * and legacy call sites): the failure is still recorded on the row.
     */
    private suspend fun enqueueOutbox(
        characterId: Long,
        uuid: String,
        hubUrl: String,
        campaignId: Int,
        request: PartySyncRequest,
        lastError: String?,
    ) {
        val outbox = outboxDao ?: return
        outbox.enqueue(
            SyncOutboxEntry(
                characterId = characterId,
                uuid = uuid,
                hubUrl = hubUrl,
                campaignId = campaignId,
                payloadJson = OutboxJson.encodeToString(request),
                expectedRevision = request.expectedRevision ?: 0,
                idempotencyKey = request.idempotencyKey ?: "",
                nextAttemptAt = System.currentTimeMillis() + OUTBOX_FIRST_RETRY_MS,
                lastError = lastError,
            ),
        )
        scheduleRetry()
    }

    /** Queue the current row state after a mid-sync local edit. */
    private suspend fun enqueueFresh(characterId: Long, hubUrl: String, campaignId: Int) {
        val outbox = outboxDao ?: return
        val entity = dao.getById(characterId) ?: return
        val uuid = entity.uuid.trim().ifEmpty {
            val candidate = java.util.UUID.randomUUID().toString()
            dao.backfillUuidIfBlank(characterId, candidate)
            candidate
        }
        // Re-read after a backfill so the wire stats carry the same uuid as
        // the request — the same discipline syncCharacter applies.
        val fresh = (dao.getById(characterId) ?: entity).let {
            if (it.uuid != uuid) it.copy(uuid = uuid) else it
        }
        val expectedRevision =
            if (!fresh.hubUrl.isNullOrBlank() && fresh.hubUrl == hubUrl && fresh.campaignId == campaignId) {
                fresh.serverRevision ?: 0
            } else {
                0
            }
        val request = buildSyncRequest(fresh, uuid, hubUrl, campaignId, expectedRevision)
        outbox.enqueue(
            SyncOutboxEntry(
                characterId = characterId,
                uuid = uuid,
                hubUrl = hubUrl,
                campaignId = campaignId,
                payloadJson = OutboxJson.encodeToString(request),
                expectedRevision = expectedRevision,
                idempotencyKey = request.idempotencyKey ?: "",
                nextAttemptAt = System.currentTimeMillis() + OUTBOX_FIRST_RETRY_MS,
                lastError = "local_edit_during_sync",
            ),
        )
        scheduleRetry()
    }

    /**
     * Replay every due outbox entry. Returns how many were processed.
     *
     * Called by [com.pathfindergod.spoke.service.SyncRetryWorker] and by the periodic sweep. An entry whose
     * Hub is no longer the current Settings Hub is left pending: the worker
     * runs without a UI, so it must never deliver to a Hub the user has
     * moved away from — the entry replays when (and if) that Hub is current
     * again, or the user discards it.
     */
    suspend fun replayDueOutboxEntries(now: Long = System.currentTimeMillis()): Int {
        val outbox = outboxDao ?: return 0
        val due = outbox.dueEntries(now)
        for (entry in due) {
            replayOutboxEntry(entry, now)
        }
        return due.size
    }

    private suspend fun replayOutboxEntry(entry: SyncOutboxEntry, now: Long) {
        val outbox = outboxDao ?: return
        val entity = dao.getById(entry.characterId)
        if (entity == null) {
            outbox.deleteById(entry.id)
            return
        }
        if (entry.hubUrl != currentHubIdentity()) return
        val stored = try {
            OutboxJson.decodeFromString<PartySyncRequest>(entry.payloadJson)
        } catch (_: Exception) {
            null
        }
        if (stored == null) {
            outbox.deleteById(entry.id)
            return
        }
        // The sheet moved on since the attempt was queued. Drop the stale
        // payload and run a fresh sync: it re-reads the row, rebuilds the
        // request with a fresh idempotency key, and re-queues if it fails.
        if (stored.stats != CharacterMapper.toWire(entity)) {
            outbox.deleteById(entry.id)
            syncCharacter(entry.characterId, campaignId = entry.campaignId)
            return
        }
        val binding = try {
            resolveHubBinding()
        } catch (_: IllegalArgumentException) {
            return
        } ?: return
        // The binding is the current Settings Hub. A queued entry for a
        // different Hub stays pending: the worker runs without a UI, so it
        // must never deliver to a Hub the user has moved away from.
        if (binding.hubUrl != entry.hubUrl) return
        val outcome = deliverSyncRequest(
            binding = binding,
            characterId = entry.characterId,
            snapshot = entity,
            uuid = entry.uuid,
            campaignId = entry.campaignId,
            request = stored,
        )
        // The entry's fate depends on what delivery did with the outbox:
        // a retryable failure re-queued the same payload (advance its
        // backoff so the worker does not hot-loop a dead Hub); a conflict
        // or a non-retryable failure left the original entry untouched
        // (drop it — the row's sync_status already names the failure, and
        // replaying it would 409/401 forever); a mid-sync local edit
        // replaced it with a fresh payload (leave the fresh entry alone).
        if (outcome is CharacterSyncResult.Conflict) {
            outbox.deleteById(entry.id)
        } else if (outcome is CharacterSyncResult.Error) {
            val current = outbox.entryForCharacter(entry.characterId)
            if (current != null && current.id == entry.id) {
                outbox.deleteById(entry.id)
            } else if (current != null && current.payloadJson == entry.payloadJson) {
                val attempts = entry.attemptCount + 1
                outbox.markAttempt(
                    id = current.id,
                    attemptCount = attempts,
                    nextAttemptAt = now + outboxBackoffMillis(attempts),
                    lastError = outcome.message,
                )
            }
        }
    }

    /**
     * Resolve a 409 by keeping the local sheet.
     *
     * Only the server's revision number is adopted — never its content —
     * then the normal sync path pushes the local sheet at that revision with
     * a fresh idempotency key. If the Hub moved on again meanwhile, the
     * conflict simply surfaces again instead of overwriting anything.
     */
    suspend fun resolveConflictKeepMine(
        characterId: Long,
        currentRevision: Int,
        campaignId: Int? = null,
    ): CharacterSyncResult {
        val entity = dao.getById(characterId)
            ?: return CharacterSyncResult.Error("Character not found")
        dao.updateSyncState(
            id = characterId,
            uuid = entity.uuid,
            hubUrl = entity.hubUrl,
            campaignId = entity.campaignId,
            serverRevision = currentRevision,
            syncStatus = entity.syncStatus,
            lastSyncedAt = entity.lastSyncedAt,
        )
        return syncCharacter(characterId, campaignId = campaignId ?: entity.campaignId)
    }

    /**
     * Resolve a 409 by adopting the Hub's character.
     *
     * The Hub's `server_character` carries the stored wire map under
     * `stats`; it is parsed with the same mapper the forge flow uses, then
     * re-anchored to the local row (id, uuid, Hub, campaign) so no local
     * identity is lost. The local sheet is replaced — the caller shows this
     * choice explicitly, and nothing here overwrites silently.
     */
    suspend fun resolveConflictUseServer(
        characterId: Long,
        serverCharacter: Map<String, JsonElement>?,
    ): CharacterSyncResult {
        val entity = dao.getById(characterId)
            ?: return CharacterSyncResult.Error("Character not found")
        val wire = (serverCharacter?.get("stats") as? JsonObject)
            ?: (serverCharacter as? JsonObject)
            ?: return CharacterSyncResult.Error("Server character could not be read")
        val adopted = CharacterMapper.fromWire(wire)
            ?: return CharacterSyncResult.Error("Server character could not be read")
        val revision = (serverCharacter["revision"] as? JsonPrimitive)?.intOrNull
            ?: entity.serverRevision
            ?: 1
        val updatedAt = (serverCharacter["updated_at"] as? JsonPrimitive)
            ?.takeIf { it.isString }?.content
        val serverUuid = (serverCharacter["uuid"] as? JsonPrimitive)
            ?.takeIf { it.isString }?.content?.ifBlank { null }
        dao.upsert(
            adopted.copy(
                id = entity.id,
                uuid = serverUuid ?: entity.uuid,
                hubUrl = entity.hubUrl,
                campaignId = entity.campaignId,
                serverRevision = revision,
                syncStatus = "synced",
                lastSyncedAt = updatedAt ?: entity.lastSyncedAt,
            ),
        )
        outboxDao?.deleteForCharacter(characterId)
        return CharacterSyncResult.Success(revision)
    }

    /**
     * Verify this handset can authenticate to its Hub (Issue #33 Phase 4).
     *
     * One lightweight authenticated call; the result names the failure mode
     * instead of collapsing everything into "network error".
     */
    suspend fun verifyHandsetAuth(): HandsetAuthResult {
        val resolved = try {
            resolveHubBinding()
        } catch (e: IllegalArgumentException) {
            return HandsetAuthResult.Unreachable(e.message ?: "Hub endpoint is not configured")
        }
        val binding = resolved
            ?: return HandsetAuthResult.Unreachable("Hub endpoint changed while verifying; retry")
        return try {
            binding.api.listCampaigns()
            HandsetAuthResult.Ok
        } catch (e: CancellationException) {
            throw e
        } catch (e: retrofit2.HttpException) {
            val code = e.code()
            if (code == 401 || code == 403) {
                HandsetAuthResult.AuthFailed(code)
            } else {
                HandsetAuthResult.Unreachable("HTTP error $code")
            }
        } catch (e: SSLException) {
            HandsetAuthResult.TlsFailed
        } catch (e: Exception) {
            HandsetAuthResult.Unreachable(e.message ?: "Network error")
        }
    }

    fun observePendingOutboxCount(): Flow<Int> =
        outboxDao?.observePendingCount() ?: flowOf(0)

    suspend fun pendingOutboxCount(): Int =
        outboxDao?.countPending() ?: 0

    /** Discard a queued sync without touching the local sheet. */
    suspend fun clearQueuedSync(characterId: Long) {
        outboxDao?.deleteForCharacter(characterId)
    }
}
