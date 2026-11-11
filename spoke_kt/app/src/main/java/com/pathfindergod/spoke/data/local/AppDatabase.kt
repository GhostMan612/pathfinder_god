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

    companion object {
        const val FILE_NAME = "pathfinder_spoke.db"
        const val VERSION = 4

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

        val MIGRATIONS: Array<Migration> = arrayOf(MIGRATION_1_2, MIGRATION_2_3, MIGRATION_3_4)

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
