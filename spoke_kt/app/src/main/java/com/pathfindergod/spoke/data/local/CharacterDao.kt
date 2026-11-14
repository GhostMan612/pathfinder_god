// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.local

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
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

    @Query("UPDATE characters SET uuid = :uuid, campaign_id = :campaignId, server_revision = :serverRevision, sync_status = :syncStatus, last_synced_at = :lastSyncedAt WHERE id = :id")
    suspend fun updateSyncState(
        id: Long,
        uuid: String,
        campaignId: Int,
        serverRevision: Int?,
        syncStatus: String,
        lastSyncedAt: String?,
    )
}
