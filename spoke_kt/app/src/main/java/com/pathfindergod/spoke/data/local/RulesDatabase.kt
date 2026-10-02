// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.local

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import androidx.sqlite.db.SupportSQLiteOpenHelper

@Database(
    entities = [RuleFtsEntity::class],
    version = 1,
    exportSchema = false,
)
abstract class RulesDatabase : RoomDatabase() {
    abstract fun ruleFtsDao(): RuleFtsDao

    companion object {
        const val FILE_NAME = "pathfinder_rag.db"

        fun open(
            context: Context,
            factory: SupportSQLiteOpenHelper.Factory = NgaSQLiteOpenHelperFactory(),
        ): RulesDatabase =
            Room.databaseBuilder(context, RulesDatabase::class.java, FILE_NAME)
                .openHelperFactory(factory)
                .fallbackToDestructiveMigration(dropAllTables = true)
                .build()

        @Volatile
        private var instance: RulesDatabase? = null

        /**
         * Process-wide singleton. `open` was a plain factory, and the call site
         * invoked it inside `remember { }` in a composable, so every visit to the
         * Rules tab - which navigation disposes - reopened the 58 MB rules DB
         * with a new connection pool and InvalidationTracker poller, none ever
         * closed.
         */
        fun get(context: Context): RulesDatabase =
            instance ?: synchronized(this) {
                instance ?: open(context.applicationContext).also { instance = it }
            }
    }
}
