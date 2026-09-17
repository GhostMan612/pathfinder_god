// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.local

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "characters")
data class CharacterEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val name: String,
    val ancestry: String? = null,
    val heritage: String? = null,
    val background: String? = null,
    @ColumnInfo(name = "character_class") val characterClass: String? = null,
    val subclass: String? = null,
    val level: Int = 1,
    val deity: String? = null,
    val alignment: String? = null,
    val size: String? = null,
    val gender: String? = null,
    val age: Int? = null,
    val eyes: String? = null,
    val hair: String? = null,
    val height: String? = null,
    val weight: String? = null,
    val languages: String? = null,
    val senses: String? = null,
    val speed: String? = null,
    @ColumnInfo(name = "portrait_path") val portraitPath: String? = null,
    val abilities: String? = null,
    val proficiencies: String? = null,
    val feats: String? = null,
    val spellcasting: String? = null,
    val equipment: String? = null,
    val derived: String? = null,
    val conditions: String? = null,
    val notes: String? = null,
)
