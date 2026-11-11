// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.local

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class AppDatabaseMigrationChainTest {

    @Test
    fun migrationsFormOneContiguousChainFromVersionOneToCurrent() {
        val steps = AppDatabase.MIGRATIONS.sortedBy { it.startVersion }
        assertEquals(1, steps.first().startVersion)
        assertEquals(AppDatabase.VERSION, steps.last().endVersion)
        steps.zipWithNext().forEach { (prev, next) ->
            assertEquals(prev.endVersion, next.startVersion)
        }
        steps.forEach { assertEquals(it.startVersion + 1, it.endVersion) }
    }

    @Test
    fun everyHistoricalVersionHasAnUpgradePath() {
        val starts = AppDatabase.MIGRATIONS.map { it.startVersion }.toSet()
        (1 until AppDatabase.VERSION).forEach { version ->
            assertTrue("no migration starts at v$version", version in starts)
        }
    }
}
