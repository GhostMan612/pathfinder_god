// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.navigation

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Campaign
import androidx.compose.material.icons.filled.Casino
import androidx.compose.material.icons.filled.Forum
import androidx.compose.material.icons.filled.Groups
import androidx.compose.material.icons.filled.Map
import androidx.compose.material.icons.filled.MenuBook
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Shield
import androidx.compose.ui.graphics.vector.ImageVector

enum class NavigationItem(val label: String, val icon: ImageVector) {
    DICE("Dice", Icons.Filled.Casino),
    GOD("God", Icons.Filled.Forum),
    HERO("Hero", Icons.Filled.Person),
    RULES("Rules", Icons.Filled.MenuBook),
    COMBAT("Combat", Icons.Filled.Shield),
    ENCOUNTER("Encounter", Icons.Filled.Groups),
    MAP("Map", Icons.Filled.Map),
    CAMPAIGN("Campaign", Icons.Filled.Campaign),
    SETUP("Setup", Icons.Filled.Settings),
}
