// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.local

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase
import androidx.sqlite.db.SupportSQLiteOpenHelper

@Database(
    entities = [
        CharacterEntity::class,
        EncounterEntity::class,
        MapEntity::class,
        CampaignEntity::class,
        RollEntity::class,
        SyncOutboxEntry::class,
    ],
    version = AppDatabase.VERSION,
    exportSchema = false,
)
abstract class AppDatabase : RoomDatabase() {
    abstract fun characterDao(): CharacterDao

    abstract fun encounterDao(): EncounterDao

    abstract fun mapDao(): MapDao

    abstract fun campaignDao(): CampaignDao

    abstract fun rollDao(): RollDao

    abstract fun syncOutboxDao(): SyncOutboxDao

    companion object {
        const val FILE_NAME = "pathfinder_spoke.db"
        const val VERSION = 7

        private const val CREATE_CAMPAIGNS =
            "CREATE TABLE IF NOT EXISTS `campaigns` (" +
                "`id` TEXT NOT NULL, " +
                "`name` TEXT NOT NULL, " +
                "`description` TEXT NOT NULL, " +
                "`session_notes` TEXT NOT NULL, " +
                "`updated_at` TEXT NOT NULL, " +
                "PRIMARY KEY(`id`))"

        private const val CREATE_ROLL_HISTORY =
            "CREATE TABLE IF NOT EXISTS `roll_history` (" +
                "`id` INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, " +
                "`notation` TEXT NOT NULL, " +
                "`rolls` TEXT NOT NULL, " +
                "`kept` TEXT NOT NULL, " +
                "`dropped` TEXT NOT NULL, " +
                "`modifier` INTEGER NOT NULL, " +
                "`total` INTEGER NOT NULL, " +
                "`impact` TEXT NOT NULL, " +
                "`degree` TEXT NOT NULL, " +
                "`target_number` INTEGER, " +
                "`rolled_at` INTEGER NOT NULL)"

        val MIGRATION_1_2 = object : Migration(1, 2) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL(CREATE_CAMPAIGNS)
            }
        }

        val MIGRATION_2_3 = object : Migration(2, 3) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL(CREATE_ROLL_HISTORY)
            }
        }

        val MIGRATION_3_4 = object : Migration(3, 4) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL("ALTER TABLE `maps` ADD COLUMN `scene_json` TEXT")
            }
        }

        val MIGRATION_4_5 = object : Migration(4, 5) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL("ALTER TABLE `characters` ADD COLUMN `uuid` TEXT NOT NULL DEFAULT ''")
                db.execSQL("ALTER TABLE `characters` ADD COLUMN `campaign_id` INTEGER")
                db.execSQL("ALTER TABLE `characters` ADD COLUMN `server_revision` INTEGER")
                db.execSQL("ALTER TABLE `characters` ADD COLUMN `sync_status` TEXT NOT NULL DEFAULT 'local'")
                db.execSQL("ALTER TABLE `characters` ADD COLUMN `last_synced_at` TEXT")
                db.execSQL(
                    "UPDATE `characters` SET `uuid` = lower(" +
                        "hex(randomblob(4)) || '-' || " +
                        "hex(randomblob(2)) || '-4' || " +
                        "substr(hex(randomblob(2)), 2) || '-' || " +
                        "substr('89ab', 1 + (abs(random()) % 4), 1) || " +
                        "substr(hex(randomblob(2)), 2) || '-' || " +
                        "hex(randomblob(6))) " +
                        "WHERE `uuid` = ''",
                )
            }
        }

        val MIGRATION_5_6 = object : Migration(5, 6) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL("ALTER TABLE `characters` ADD COLUMN `hub_url` TEXT")
            }
        }

        // Issue #33 Phase 3: the durable sync outbox. A fresh table — no
        // existing rows to migrate — so the migration is a single CREATE.
        // No DEFAULT clauses: Room compares column defaults at open time,
        // and the entity declares none, so the table must carry none.
        val MIGRATION_6_7 = object : Migration(6, 7) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL(
                    "CREATE TABLE IF NOT EXISTS `sync_outbox` (" +
                        "`id` INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, " +
                        "`character_id` INTEGER NOT NULL, " +
                        "`uuid` TEXT NOT NULL, " +
                        "`hub_url` TEXT NOT NULL, " +
                        "`campaign_id` INTEGER NOT NULL, " +
                        "`payload_json` TEXT NOT NULL, " +
                        "`expected_revision` INTEGER NOT NULL, " +
                        "`idempotency_key` TEXT NOT NULL, " +
                        "`attempt_count` INTEGER NOT NULL, " +
                        "`next_attempt_at` INTEGER NOT NULL, " +
                        "`last_error` TEXT, " +
                        "`created_at` INTEGER NOT NULL)",
                )
                db.execSQL(
                    "CREATE INDEX IF NOT EXISTS `index_sync_outbox_next_attempt_at` " +
                        "ON `sync_outbox` (`next_attempt_at`)",
                )
            }
        }

        val MIGRATIONS: Array<Migration> = arrayOf(MIGRATION_1_2, MIGRATION_2_3, MIGRATION_3_4, MIGRATION_4_5, MIGRATION_5_6, MIGRATION_6_7)

        fun create(
            context: Context,
            factory: SupportSQLiteOpenHelper.Factory = NgaSQLiteOpenHelperFactory(),
            name: String = FILE_NAME,
        ): AppDatabase =
            Room.databaseBuilder(context, AppDatabase::class.java, name)
                .addMigrations(*MIGRATIONS)
                .openHelperFactory(factory)
                .build()

        @Volatile
        private var instance: AppDatabase? = null

        /**
         * Process-wide singleton. `create` was a plain factory returning a new
         * RoomDatabase on every call, and all seven call sites invoke it inside
         * `remember { }` in a composable. Because navigation uses
         * popUpTo(saveState)/restoreState, which *disposes* the destination,
         * every tab visit minted another live database - its own SQLite
         * connection pool and InvalidationTracker poller - and nothing ever
         * closed any of them.
         */
        fun get(context: Context): AppDatabase =
            instance ?: synchronized(this) {
                instance ?: create(context.applicationContext).also { instance = it }
            }
    }
}
