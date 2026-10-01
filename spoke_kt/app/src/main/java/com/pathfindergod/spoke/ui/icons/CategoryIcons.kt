// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.icons

import androidx.annotation.DrawableRes
import com.pathfindergod.spoke.R

object CategoryIcons {

    @DrawableRes
    fun lootRarity(rarity: String): Int {
        val text = rarity.lowercase()
        return when {
            text.contains("very rare") -> R.drawable.gi_loot_crystal_shine
            text.contains("legendary") -> R.drawable.gi_loot_glowing_artifact
            text.contains("mythic") -> R.drawable.gi_loot_glowing_artifact
            text.contains("artifact") -> R.drawable.gi_loot_chest
            text.contains("relic") -> R.drawable.gi_loot_chest
            text.contains("unique") -> R.drawable.gi_loot_chest
            text.contains("rare") -> R.drawable.gi_loot_fire_gem
            text.contains("uncommon") -> R.drawable.gi_loot_crystal_cluster
            else -> R.drawable.gi_loot_coins
        }
    }

    @DrawableRes
    fun encounterDifficulty(difficulty: String): Int = when (difficulty.lowercase()) {
        "trivial" -> R.drawable.gi_enc_trivial
        "low" -> R.drawable.gi_enc_low
        "severe" -> R.drawable.gi_enc_severe
        "extreme" -> R.drawable.gi_enc_extreme
        else -> R.drawable.gi_enc_moderate
    }

    @DrawableRes
    fun condition(
        name: String,
        frightened: String,
        prone: String,
        sickened: String,
    ): Int? = when {
        name.equals(frightened, ignoreCase = true) -> R.drawable.gi_cond_frightened
        name.equals(prone, ignoreCase = true) -> R.drawable.gi_cond_prone
        name.equals(sickened, ignoreCase = true) -> R.drawable.gi_cond_sickened
        else -> null
    }
}