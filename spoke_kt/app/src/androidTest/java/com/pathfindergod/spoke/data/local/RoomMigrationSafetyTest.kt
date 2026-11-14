// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.local

import android.content.Context
import android.database.sqlite.SQLiteDatabase
import androidx.test.core.app.ApplicationProvider
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class RoomMigrationSafetyTest {

    private val context: Context = ApplicationProvider.getApplicationContext()

    @Before
    fun clean() {
        context.deleteDatabase(APP_DB)
        context.deleteDatabase(RULES_DB)
    }

    @After
    fun tearDown() {
        context.deleteDatabase(APP_DB)
        context.deleteDatabase(RULES_DB)
    }

    @Test
    fun versionOneInstallUpgradesToCurrentWithoutLosingData() {
        seedVersionOne()

        val db = AppDatabase.create(context, name = APP_DB)
        try {
            val sql = db.openHelper.writableDatabase
            assertEquals(AppDatabase.VERSION, sql.version)
            sql.query("SELECT name, level FROM characters").use { c ->
                assertTrue(c.moveToFirst())
                assertEquals("Synthetic Hero A", c.getString(0))
                assertEquals(3, c.getInt(1))
            }
            sql.query("SELECT prompt, scene_json FROM maps").use { c ->
                assertTrue(c.moveToFirst())
                assertEquals("Synthetic crypt", c.getString(0))
                assertTrue(c.isNull(1))
            }
            sql.query("SELECT COUNT(*) FROM campaigns").use { c ->
                assertTrue(c.moveToFirst())
                assertEquals(0, c.getInt(0))
            }
            sql.query("SELECT COUNT(*) FROM roll_history").use { c ->
                assertTrue(c.moveToFirst())
                assertEquals(0, c.getInt(0))
            }
        } finally {
            db.close()
        }
    }

    @Test
    fun unknownAppVersionFailsLoudlyInsteadOfWipingTables() {
        seedVersionOne()
        SQLiteDatabase.openDatabase(
            context.getDatabasePath(APP_DB).path,
            null,
            SQLiteDatabase.OPEN_READWRITE,
        ).use { it.version = AppDatabase.VERSION + 5 }

        val db = AppDatabase.create(context, name = APP_DB)
        try {
            assertThrows(IllegalStateException::class.java) { db.openHelper.writableDatabase }
        } finally {
            db.close()
        }
        assertEquals(1, countRows(APP_DB, "characters"))
    }

    @Test
    fun versionFourInstallWithCharactersMigratesToVersionFiveAndSurvivesReopen() {
        seedVersionFour()
        val uuidPattern = Regex("^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")

        val migratedUuids: Pair<String, String>
        val firstOpen = AppDatabase.create(context, name = APP_DB)
        try {
            val sql = firstOpen.openHelper.writableDatabase
            assertEquals(AppDatabase.VERSION, sql.version)
            runBlocking {
                val valeros = firstOpen.characterDao().getById(1L)!!
                val seoni = firstOpen.characterDao().getById(2L)!!
                assertEquals("Valeros", valeros.name)
                assertEquals("Fighter", valeros.characterClass)
                assertEquals(4, valeros.level)
                assertEquals("Pre-v5 notes preserved", valeros.notes)
                assertTrue(valeros.uuid.matches(uuidPattern))
                assertNull(valeros.campaignId)
                assertNull(valeros.serverRevision)
                assertEquals("local", valeros.syncStatus)
                assertNull(valeros.lastSyncedAt)

                assertEquals("Seoni", seoni.name)
                assertTrue(seoni.uuid.matches(uuidPattern))
                assertNotEquals(valeros.uuid, seoni.uuid)

                val committed = firstOpen.characterDao().commitSyncSuccess(
                    id = valeros.id,
                    snapshot = valeros,
                    uuid = valeros.uuid,
                    campaignId = 2,
                    serverRevision = 3,
                    lastSyncedAt = "2026-11-14T00:00:00Z",
                )
                assertTrue(committed)
                migratedUuids = valeros.uuid to seoni.uuid
            }
        } finally {
            firstOpen.close()
        }

        val reopened = AppDatabase.create(context, name = APP_DB)
        try {
            runBlocking {
                val valeros = reopened.characterDao().getById(1L)!!
                val seoni = reopened.characterDao().getById(2L)!!
                assertEquals("Valeros", valeros.name)
                assertEquals("Pre-v5 notes preserved", valeros.notes)
                assertEquals(migratedUuids.first, valeros.uuid)
                assertEquals(2, valeros.campaignId)
                assertEquals(3, valeros.serverRevision)
                assertEquals("synced", valeros.syncStatus)
                assertEquals("2026-11-14T00:00:00Z", valeros.lastSyncedAt)

                assertEquals("Seoni", seoni.name)
                assertEquals(migratedUuids.second, seoni.uuid)
                assertNull(seoni.campaignId)
                assertEquals("local", seoni.syncStatus)
            }
        } finally {
            reopened.close()
        }
    }

    @Test
    fun rulesDatabaseVersionMismatchFailsLoudlyInsteadOfWipingRules() {
        val first = RulesDatabase.open(context, name = RULES_DB)
        try {
            first.openHelper.writableDatabase.execSQL(
                "INSERT INTO rules (rowid, name, raw_content, system, category, source_book) " +
                    "VALUES (1, 'Synthetic Rule', 'Synthetic text.', '2E', 'rule', 'Synthetic Book')",
            )
        } finally {
            first.close()
        }
        SQLiteDatabase.openDatabase(
            context.getDatabasePath(RULES_DB).path,
            null,
            SQLiteDatabase.OPEN_READWRITE,
        ).use { it.version = 2 }

        val second = RulesDatabase.open(context, name = RULES_DB)
        try {
            assertThrows(IllegalStateException::class.java) { second.openHelper.writableDatabase }
        } finally {
            second.close()
        }
        assertEquals(1, countRows(RULES_DB, "rules"))
    }

    private fun countRows(name: String, table: String): Int =
        SQLiteDatabase.openDatabase(
            context.getDatabasePath(name).path,
            null,
            SQLiteDatabase.OPEN_READONLY,
        ).use { db ->
            db.rawQuery("SELECT COUNT(*) FROM $table", null).use { c ->
                c.moveToFirst()
                c.getInt(0)
            }
        }

    private fun seedVersionOne() {
        val file = context.getDatabasePath(APP_DB)
        file.parentFile?.mkdirs()
        SQLiteDatabase.openOrCreateDatabase(file, null).use { db ->
            db.execSQL(
                "CREATE TABLE IF NOT EXISTS `characters` (" +
                    "`id` INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, `name` TEXT NOT NULL, " +
                    "`ancestry` TEXT, `heritage` TEXT, `background` TEXT, " +
                    "`character_class` TEXT, `subclass` TEXT, `level` INTEGER NOT NULL, " +
                    "`deity` TEXT, `alignment` TEXT, `size` TEXT, `gender` TEXT, `age` INTEGER, " +
                    "`eyes` TEXT, `hair` TEXT, `height` TEXT, `weight` TEXT, `languages` TEXT, " +
                    "`senses` TEXT, `speed` TEXT, `portrait_path` TEXT, `abilities` TEXT, " +
                    "`proficiencies` TEXT, `feats` TEXT, `spellcasting` TEXT, `equipment` TEXT, " +
                    "`derived` TEXT, `conditions` TEXT, `notes` TEXT)",
            )
            db.execSQL(
                "CREATE TABLE IF NOT EXISTS `encounters` (" +
                    "`id` TEXT NOT NULL, `theme` TEXT NOT NULL, `threat` TEXT NOT NULL, " +
                    "`monsters_json` TEXT NOT NULL, `target_xp` INTEGER NOT NULL, " +
                    "`created_at` TEXT NOT NULL, PRIMARY KEY(`id`))",
            )
            db.execSQL(
                "CREATE TABLE IF NOT EXISTS `maps` (" +
                    "`id` TEXT NOT NULL, `prompt` TEXT NOT NULL, `gm_base64_png` TEXT NOT NULL, " +
                    "`player_base64_png` TEXT NOT NULL, `width` INTEGER NOT NULL, " +
                    "`height` INTEGER NOT NULL, `created_at` TEXT NOT NULL, PRIMARY KEY(`id`))",
            )
            db.execSQL(
                "CREATE TABLE IF NOT EXISTS room_master_table " +
                    "(id INTEGER PRIMARY KEY,identity_hash TEXT)",
            )
            db.execSQL(
                "INSERT OR REPLACE INTO room_master_table (id,identity_hash) " +
                    "VALUES(42, 'synthetic-v1-identity')",
            )
            db.execSQL(
                "INSERT INTO characters (name, level) VALUES ('Synthetic Hero A', 3)",
            )
            db.execSQL(
                "INSERT INTO maps (id, prompt, gm_base64_png, player_base64_png, width, height, " +
                    "created_at) VALUES ('map-1', 'Synthetic crypt', '', '', 4, 3, '2026-01-01')",
            )
            db.version = 1
        }
    }

    private fun seedVersionFour() {
        val file = context.getDatabasePath(APP_DB)
        file.parentFile?.mkdirs()
        SQLiteDatabase.openOrCreateDatabase(file, null).use { db ->
            db.execSQL(
                "CREATE TABLE IF NOT EXISTS `characters` (" +
                    "`id` INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, `name` TEXT NOT NULL, " +
                    "`ancestry` TEXT, `heritage` TEXT, `background` TEXT, " +
                    "`character_class` TEXT, `subclass` TEXT, `level` INTEGER NOT NULL, " +
                    "`deity` TEXT, `alignment` TEXT, `size` TEXT, `gender` TEXT, `age` INTEGER, " +
                    "`eyes` TEXT, `hair` TEXT, `height` TEXT, `weight` TEXT, `languages` TEXT, " +
                    "`senses` TEXT, `speed` TEXT, `portrait_path` TEXT, `abilities` TEXT, " +
                    "`proficiencies` TEXT, `feats` TEXT, `spellcasting` TEXT, `equipment` TEXT, " +
                    "`derived` TEXT, `conditions` TEXT, `notes` TEXT)",
            )
            db.execSQL(
                "CREATE TABLE IF NOT EXISTS `encounters` (" +
                    "`id` TEXT NOT NULL, `theme` TEXT NOT NULL, `threat` TEXT NOT NULL, " +
                    "`monsters_json` TEXT NOT NULL, `target_xp` INTEGER NOT NULL, " +
                    "`created_at` TEXT NOT NULL, PRIMARY KEY(`id`))",
            )
            db.execSQL(
                "CREATE TABLE IF NOT EXISTS `maps` (" +
                    "`id` TEXT NOT NULL, `prompt` TEXT NOT NULL, `gm_base64_png` TEXT NOT NULL, " +
                    "`player_base64_png` TEXT NOT NULL, `width` INTEGER NOT NULL, " +
                    "`height` INTEGER NOT NULL, `scene_json` TEXT, `created_at` TEXT NOT NULL, PRIMARY KEY(`id`))",
            )
            db.execSQL(
                "CREATE TABLE IF NOT EXISTS `campaigns` (" +
                    "`id` TEXT NOT NULL, `name` TEXT NOT NULL, `description` TEXT NOT NULL, " +
                    "`session_notes` TEXT NOT NULL, `updated_at` TEXT NOT NULL, PRIMARY KEY(`id`))",
            )
            db.execSQL(
                "CREATE TABLE IF NOT EXISTS `roll_history` (" +
                    "`id` INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, `notation` TEXT NOT NULL, " +
                    "`rolls` TEXT NOT NULL, `kept` TEXT NOT NULL, `dropped` TEXT NOT NULL, " +
                    "`modifier` INTEGER NOT NULL, `total` INTEGER NOT NULL, `impact` TEXT NOT NULL, " +
                    "`degree` TEXT NOT NULL, `target_number` INTEGER, `rolled_at` INTEGER NOT NULL)",
            )
            db.execSQL(
                "CREATE TABLE IF NOT EXISTS room_master_table " +
                    "(id INTEGER PRIMARY KEY,identity_hash TEXT)",
            )
            db.execSQL(
                "INSERT OR REPLACE INTO room_master_table (id,identity_hash) " +
                    "VALUES(42, 'synthetic-v4-identity')",
            )
            db.execSQL(
                "INSERT INTO characters (id, name, ancestry, character_class, level, notes) " +
                    "VALUES (1, 'Valeros', 'Human', 'Fighter', 4, 'Pre-v5 notes preserved')",
            )
            db.execSQL(
                "INSERT INTO characters (id, name, ancestry, character_class, level) " +
                    "VALUES (2, 'Seoni', 'Human', 'Sorcerer', 3)",
            )
            db.version = 4
        }
    }

    private companion object {
        const val APP_DB = "migration-safety-app.db"
        const val RULES_DB = "migration-safety-rules.db"
    }
}
