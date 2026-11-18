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
interface SyncOutboxDao {
    /**
     * Queue (or replace) the pending sync for one character.
     *
     * One pending entry per character: a newer attempt supersedes the older
     * one instead of stacking behind it, so the outbox can never hold a stale
     * payload for a character the user has since edited.
     */
    @Transaction
    suspend fun enqueue(entry: SyncOutboxEntry) {
        deleteForCharacter(entry.characterId)
        insert(entry)
    }

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(entry: SyncOutboxEntry): Long

    @Query("SELECT * FROM sync_outbox WHERE next_attempt_at <= :now ORDER BY next_attempt_at ASC")
    suspend fun dueEntries(now: Long): List<SyncOutboxEntry>

    @Query("SELECT * FROM sync_outbox WHERE character_id = :characterId LIMIT 1")
    suspend fun entryForCharacter(characterId: Long): SyncOutboxEntry?

    @Query("DELETE FROM sync_outbox WHERE character_id = :characterId")
    suspend fun deleteForCharacter(characterId: Long)

    @Query("DELETE FROM sync_outbox WHERE id = :id")
    suspend fun deleteById(id: Long)

    @Query("UPDATE sync_outbox SET attempt_count = :attemptCount, next_attempt_at = :nextAttemptAt, last_error = :lastError WHERE id = :id")
    suspend fun markAttempt(id: Long, attemptCount: Int, nextAttemptAt: Long, lastError: String?)

    @Query("UPDATE sync_outbox SET payload_json = :payloadJson, expected_revision = :expectedRevision, idempotency_key = :idempotencyKey, attempt_count = 0, next_attempt_at = :nextAttemptAt, last_error = NULL WHERE id = :id")
    suspend fun refreshPayload(
        id: Long,
        payloadJson: String,
        expectedRevision: Int,
        idempotencyKey: String,
        nextAttemptAt: Long,
    )

    @Query("SELECT COUNT(*) FROM sync_outbox")
    suspend fun countPending(): Int

    @Query("SELECT COUNT(*) FROM sync_outbox")
    fun observePendingCount(): Flow<Int>
}
