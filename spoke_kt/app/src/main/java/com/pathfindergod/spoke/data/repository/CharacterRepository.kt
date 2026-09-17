// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.repository

import com.pathfindergod.spoke.data.local.AppDatabase
import com.pathfindergod.spoke.data.local.CharacterEntity
import com.pathfindergod.spoke.data.network.HubApi
import kotlinx.coroutines.flow.Flow

class CharacterRepository(
    private val db: AppDatabase,
    private val api: HubApi,
) {
    fun observeCharacters(): Flow<List<CharacterEntity>> =
        db.characterDao().observeAll()

    suspend fun getCharacter(id: Long): CharacterEntity? =
        db.characterDao().getById(id)

    suspend fun saveCharacter(entity: CharacterEntity): Long =
        db.characterDao().upsert(entity)

    suspend fun deleteCharacter(id: Long) {
        db.characterDao().delete(id)
    }

    suspend fun characterCount(): Int = db.characterDao().count()
}
