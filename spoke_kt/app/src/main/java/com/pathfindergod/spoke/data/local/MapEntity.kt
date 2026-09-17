// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.local

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "maps")
data class MapEntity(
    @PrimaryKey val id: String,
    val prompt: String,
    @ColumnInfo(name = "gm_base64_png") val gmBase64Png: String,
    @ColumnInfo(name = "player_base64_png") val playerBase64Png: String,
    val width: Int,
    val height: Int,
    @ColumnInfo(name = "created_at") val createdAt: String,
)
