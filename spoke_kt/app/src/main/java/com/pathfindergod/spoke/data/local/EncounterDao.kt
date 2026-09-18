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
interface EncounterDao {
    @Query("SELECT * FROM encounters ORDER BY created_at DESC")
    fun observeAll(): Flow<List<EncounterEntity>>

    @Query("SELECT * FROM encounters ORDER BY created_at DESC")
    suspend fun getAll(): List<EncounterEntity>

    @Query("SELECT * FROM encounters WHERE id = :id")
    suspend fun getById(id: String): EncounterEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(entity: EncounterEntity)

    @Query("DELETE FROM encounters WHERE id = :id")
    suspend fun delete(id: String)
}
