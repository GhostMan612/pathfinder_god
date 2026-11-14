// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.local

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Transaction
import kotlinx.coroutines.flow.Flow

@Dao
interface CharacterDao {
    @Query("SELECT * FROM characters ORDER BY id DESC")
    fun observeAll(): Flow<List<CharacterEntity>>

    @Query("SELECT * FROM characters WHERE id = :id")
    suspend fun getById(id: Long): CharacterEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(entity: CharacterEntity): Long

    @Query("DELETE FROM characters WHERE id = :id")
    suspend fun delete(id: Long)

    @Query("SELECT COUNT(*) FROM characters")
    suspend fun count(): Int

    @Query("SELECT * FROM characters WHERE uuid = :uuid")
    suspend fun getByUuid(uuid: String): CharacterEntity?

    @Query("UPDATE characters SET uuid = :uuid WHERE id = :id AND trim(uuid) = ''")
    suspend fun backfillUuidIfBlank(id: Long, uuid: String): Int

    @Query("UPDATE characters SET uuid = :uuid, hub_url = :hubUrl, campaign_id = :campaignId, server_revision = :serverRevision, sync_status = :syncStatus, last_synced_at = :lastSyncedAt WHERE id = :id")
    suspend fun updateSyncState(
        id: Long,
        uuid: String,
        hubUrl: String?,
        campaignId: Int?,
        serverRevision: Int?,
        syncStatus: String,
        lastSyncedAt: String?,
    )

    @Transaction
    suspend fun commitSyncSuccess(
        id: Long,
        snapshot: CharacterEntity,
        uuid: String,
        hubUrl: String,
        campaignId: Int,
        serverRevision: Int,
        lastSyncedAt: String?,
    ): Boolean {
        val current = getById(id) ?: return false
        val effectiveUuid = current.uuid.trim().ifEmpty { uuid }
        if (!current.hasSameSheetContent(snapshot)) {
            updateSyncState(
                id = id,
                uuid = effectiveUuid,
                hubUrl = hubUrl,
                campaignId = campaignId,
                serverRevision = serverRevision,
                syncStatus = "local",
                lastSyncedAt = current.lastSyncedAt,
            )
            return false
        }
        updateSyncState(
            id = id,
            uuid = effectiveUuid,
            hubUrl = hubUrl,
            campaignId = campaignId,
            serverRevision = serverRevision,
            syncStatus = "synced",
            lastSyncedAt = lastSyncedAt,
        )
        return true
    }

    @Transaction
    suspend fun commitSyncFailure(
        id: Long,
        snapshot: CharacterEntity,
        uuid: String,
        syncStatus: String,
    ) {
        val current = getById(id) ?: return
        val effectiveUuid = current.uuid.trim().ifEmpty { uuid }
        val resolvedStatus = if (current.hasSameSheetContent(snapshot)) syncStatus else "local"
        updateSyncState(
            id = id,
            uuid = effectiveUuid,
            hubUrl = current.hubUrl,
            campaignId = current.campaignId,
            serverRevision = current.serverRevision,
            syncStatus = resolvedStatus,
            lastSyncedAt = current.lastSyncedAt,
        )
    }
}
