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
    entities = [
        CharacterEntity::class,
        EncounterEntity::class,
        MapEntity::class,
        CampaignEntity::class,
    ],
    version = 2,
    exportSchema = false,
)
abstract class AppDatabase : RoomDatabase() {
    abstract fun characterDao(): CharacterDao

    abstract fun encounterDao(): EncounterDao

    abstract fun mapDao(): MapDao

    abstract fun campaignDao(): CampaignDao

    companion object {
        const val FILE_NAME = "pathfinder_spoke.db"

        fun create(
            context: Context,
            factory: SupportSQLiteOpenHelper.Factory = NgaSQLiteOpenHelperFactory(),
        ): AppDatabase =
            Room.databaseBuilder(context, AppDatabase::class.java, FILE_NAME)
                .openHelperFactory(factory)
                .fallbackToDestructiveMigration(dropAllTables = true)
                .build()
    }
}
