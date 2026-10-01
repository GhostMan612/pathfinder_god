// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.local

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query

@Dao
interface RollDao {
    @Query("SELECT * FROM roll_history ORDER BY id DESC LIMIT :limit")
    suspend fun recent(limit: Int): List<RollEntity>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(entity: RollEntity): Long

    @Query("DELETE FROM roll_history WHERE id NOT IN (SELECT id FROM roll_history ORDER BY id DESC LIMIT :keep)")
    suspend fun trimTo(keep: Int)

    @Query("DELETE FROM roll_history")
    suspend fun clear()
}
