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
    }
}
