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
interface CampaignDao {
    @Query("SELECT * FROM campaigns ORDER BY updated_at DESC LIMIT 1")
    fun observeActive(): Flow<CampaignEntity?>

    @Query("SELECT * FROM campaigns ORDER BY updated_at DESC LIMIT 1")
    suspend fun getActive(): CampaignEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(entity: CampaignEntity)

    @Query("DELETE FROM campaigns WHERE id = :id")
    suspend fun delete(id: String)
}
