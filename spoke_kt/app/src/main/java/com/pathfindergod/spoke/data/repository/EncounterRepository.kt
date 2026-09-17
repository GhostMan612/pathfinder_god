// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.repository

import com.pathfindergod.spoke.data.local.AppDatabase
import com.pathfindergod.spoke.data.local.EncounterEntity
import com.pathfindergod.spoke.data.network.HubApi
import java.time.Instant
import kotlinx.coroutines.flow.Flow

class EncounterRepository(
    private val db: AppDatabase,
    private val api: HubApi,
) {
    fun observeEncounters(): Flow<List<EncounterEntity>> =
        db.encounterDao().observeAll()

    suspend fun getEncounters(): List<EncounterEntity> =
        db.encounterDao().getAll()

    suspend fun saveEncounter(
        id: String,
        theme: String,
        threat: String,
        monstersJson: String,
        targetXp: Int,
    ) {
        db.encounterDao().upsert(
            EncounterEntity(
                id = id,
                theme = theme,
                threat = threat,
                monstersJson = monstersJson,
                targetXp = targetXp,
                createdAt = Instant.now().toString(),
            ),
        )
    }

    suspend fun deleteEncounter(id: String) {
        db.encounterDao().delete(id)
    }
}
