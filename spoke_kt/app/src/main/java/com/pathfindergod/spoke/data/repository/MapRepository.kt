// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.repository

import com.pathfindergod.spoke.data.local.AppDatabase
import com.pathfindergod.spoke.data.local.MapEntity
import com.pathfindergod.spoke.data.network.HubApi
import java.time.Instant
import kotlinx.coroutines.flow.Flow

class MapRepository(
    private val db: AppDatabase,
    private val api: HubApi,
) {
    fun observeMaps(): Flow<List<MapEntity>> =
        db.mapDao().observeAll()

    suspend fun getMaps(): List<MapEntity> =
        db.mapDao().getAll()

    suspend fun saveMap(
        id: String,
        prompt: String,
        gmBase64Png: String,
        playerBase64Png: String,
        width: Int,
        height: Int,
    ) {
        db.mapDao().upsert(
            MapEntity(
                id = id,
                prompt = prompt,
                gmBase64Png = gmBase64Png,
                playerBase64Png = playerBase64Png,
                width = width,
                height = height,
                createdAt = Instant.now().toString(),
            ),
        )
    }

    suspend fun deleteMap(id: String) {
        db.mapDao().delete(id)
    }
}
