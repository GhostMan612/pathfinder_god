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
interface MapDao {
    @Query("SELECT * FROM maps ORDER BY created_at DESC")
    fun observeAll(): Flow<List<MapEntity>>

    @Query("SELECT * FROM maps ORDER BY created_at DESC")
    suspend fun getAll(): List<MapEntity>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(entity: MapEntity)

    @Query("DELETE FROM maps WHERE id = :id")
    suspend fun delete(id: String)
}
