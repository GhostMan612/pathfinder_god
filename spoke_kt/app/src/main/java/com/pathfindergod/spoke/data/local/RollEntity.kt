// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.local

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "roll_history")
data class RollEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0L,
    val notation: String,
    val rolls: String,
    val kept: String,
    val dropped: String,
    val modifier: Int,
    val total: Int,
    val impact: String,
    val degree: String,
    @ColumnInfo(name = "target_number") val targetNumber: Int?,
    @ColumnInfo(name = "rolled_at") val rolledAt: Long,
)
