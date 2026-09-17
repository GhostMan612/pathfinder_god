// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.repository

import androidx.sqlite.db.SimpleSQLiteQuery
import com.pathfindergod.spoke.data.local.RuleFtsEntity
import com.pathfindergod.spoke.data.local.RulesDatabase
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

class RuleRepository(
    private val db: RulesDatabase,
) {
    suspend fun search(query: String, limit: Int = 25): List<RuleFtsEntity> =
        withContext(Dispatchers.IO) {
            db.ruleFtsDao().search(
                SimpleSQLiteQuery(
                    "SELECT rowid, name, raw_content, system, category, source_book " +
                        "FROM rules WHERE rules MATCH ? " +
                        "ORDER BY bm25(rules) LIMIT ?",
                    arrayOf<Any?>(query, limit),
                ),
            )
        }

    suspend fun searchInSystem(
        query: String,
        system: String,
        limit: Int = 25,
    ): List<RuleFtsEntity> =
        withContext(Dispatchers.IO) {
            db.ruleFtsDao().search(
                SimpleSQLiteQuery(
                    "SELECT rowid, name, raw_content, system, category, source_book " +
                        "FROM rules WHERE rules MATCH ? " +
                        "ORDER BY bm25(rules) LIMIT ?",
                    arrayOf<Any?>("{system} : $system AND ($query)", limit),
                ),
            )
        }

    suspend fun count(query: String): Int =
        withContext(Dispatchers.IO) {
            db.ruleFtsDao().count(
                SimpleSQLiteQuery(
                    "SELECT COUNT(*) FROM rules WHERE rules MATCH ?",
                    arrayOf(query),
                ),
            )
        }
}
