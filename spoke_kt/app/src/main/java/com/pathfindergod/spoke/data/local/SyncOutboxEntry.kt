// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.local

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.PrimaryKey

/**
 * One queued character-sheet sync that the Hub has not confirmed yet.
 *
 * Issue #33 Phase 3: a sync attempt that fails for a retryable reason
 * (network down, TLS handshake failure, Hub 5xx) is written here instead of
 * being lost. The payload is the exact [PartySyncRequest] wire JSON that was
 * attempted — including its idempotency key — so a replay is byte-identical
 * to the original attempt and the Hub dedupes it instead of applying it
 * twice. At most one pending entry exists per character; a newer local edit
 * replaces the queued payload instead of stacking behind it.
 *
 * `next_attempt_at` is epoch milliseconds. The retry worker only replays
 * entries whose time has come, and pushes the time out on every retryable
 * failure (30s, 2m, 10m, then 1h — see `SyncOutbox` backoff). Entries are
 * never dropped for a retryable failure: they persist until the Hub confirms
 * them, the user discards them, or a later local edit refreshes them.
 */
@Entity(tableName = "sync_outbox")
data class SyncOutboxEntry(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    @ColumnInfo(name = "character_id") val characterId: Long,
    val uuid: String,
    @ColumnInfo(name = "hub_url") val hubUrl: String,
    @ColumnInfo(name = "campaign_id") val campaignId: Int,
    @ColumnInfo(name = "payload_json") val payloadJson: String,
    @ColumnInfo(name = "expected_revision") val expectedRevision: Int,
    @ColumnInfo(name = "idempotency_key") val idempotencyKey: String,
    @ColumnInfo(name = "attempt_count") val attemptCount: Int = 0,
    @ColumnInfo(name = "next_attempt_at") val nextAttemptAt: Long = 0,
    @ColumnInfo(name = "last_error") val lastError: String? = null,
    @ColumnInfo(name = "created_at") val createdAt: Long = System.currentTimeMillis(),
)
