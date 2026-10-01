// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable

@Composable
fun PathfinderGodTheme(
    content: @Composable () -> Unit,
) {
    MaterialTheme(
        colorScheme = GodColorScheme,
        typography = GodTypography,
        shapes = GodShapes,
        content = content,
    )
}
