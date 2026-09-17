// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.local

import androidx.room.Dao
import androidx.room.RawQuery
import androidx.sqlite.db.SupportSQLiteQuery

@Dao
interface RuleFtsDao {
    @RawQuery(observedEntities = [RuleFtsEntity::class])
    fun search(query: SupportSQLiteQuery): List<RuleFtsEntity>

    @RawQuery(observedEntities = [RuleFtsEntity::class])
    fun count(query: SupportSQLiteQuery): Int
}
