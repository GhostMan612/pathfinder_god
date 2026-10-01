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
    /**
     * Build a safe FTS5 MATCH expression from free-form user text.
     *
     * The user's raw keystrokes used to be passed straight into MATCH, where
     * FTS5 reads `' " * ( ) : -` and commas as query syntax. Verified against
     * the bundled rules database, each of these threw OperationalError:
     * "monk's feats", "cost 1,000 gp", "d20 minus 5", a bare "*", or any
     * unbalanced quote or paren. Because RuleSearchViewModel had no catch, that
     * exception escaped viewModelScope and killed the app - the Rules search
     * fires on every keystroke.
     *
     * Quoting each token as an FTS5 string literal (doubling any embedded
     * double quote) makes it impossible for user text to be parsed as syntax.
     */
    private fun ftsPhrase(raw: String): String =
        raw.trim()
            .split(Regex("\\s+"))
            .filter { it.isNotEmpty() }
            .joinToString(" OR ") { token -> "\"" + token.replace("\"", "\"\"") + "\"" }
            .ifEmpty { "\"\"" }

    private suspend fun run(match: String, limit: Int): List<RuleFtsEntity> =
        withContext(Dispatchers.IO) {
            db.ruleFtsDao().search(
                SimpleSQLiteQuery(
                    "SELECT rowid, name, raw_content, system, category, source_book " +
                        "FROM rules WHERE rules MATCH ? " +
                        "ORDER BY bm25(rules) LIMIT ?",
                    arrayOf<Any?>(match, limit),
                ),
            )
        }

    suspend fun search(query: String, limit: Int = 25): List<RuleFtsEntity> =
        run(ftsPhrase(query), limit)

    suspend fun searchInSystem(
        query: String,
        system: String,
        limit: Int = 25,
    ): List<RuleFtsEntity> =
        run("{system} : ${ftsPhrase(system)} AND (${ftsPhrase(query)})", limit)

    suspend fun count(query: String): Int =
        withContext(Dispatchers.IO) {
            db.ruleFtsDao().count(
                SimpleSQLiteQuery(
                    "SELECT COUNT(*) FROM rules WHERE rules MATCH ?",
                    arrayOf(ftsPhrase(query)),
                ),
            )
        }
}