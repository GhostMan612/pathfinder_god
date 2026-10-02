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
    version = 3,
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

        val MIGRATION_2_3 = object : Migration(2, 3) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL(CREATE_ROLL_HISTORY)
            }
        }

        fun create(
            context: Context,
            factory: SupportSQLiteOpenHelper.Factory = NgaSQLiteOpenHelperFactory(),
        ): AppDatabase =
            Room.databaseBuilder(context, AppDatabase::class.java, FILE_NAME)
                .addMigrations(MIGRATION_2_3)
                .openHelperFactory(factory)
                .fallbackToDestructiveMigration(dropAllTables = true)
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
