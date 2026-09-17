// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.local

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "encounters")
data class EncounterEntity(
    @PrimaryKey val id: String,
    val theme: String,
    val threat: String,
    @ColumnInfo(name = "monsters_json") val monstersJson: String,
    @ColumnInfo(name = "target_xp") val targetXp: Int,
    @ColumnInfo(name = "created_at") val createdAt: String,
)
