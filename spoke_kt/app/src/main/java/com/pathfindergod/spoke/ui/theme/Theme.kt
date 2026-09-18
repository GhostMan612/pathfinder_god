// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable

private val GodColors = darkColorScheme(
    primary = CrimsonPrimary,
    onPrimary = TextPrimary,
    secondary = GoldAccent,
    onSecondary = VoidBackground,
    tertiary = TextSecondary,
    background = VoidBackground,
    onBackground = TextPrimary,
    surface = ParchmentSurface,
    onSurface = TextPrimary,
    surfaceVariant = ParchmentSurface,
    onSurfaceVariant = TextSecondary,
    outline = GoldAccent,
)

@Composable
fun PathfinderGodTheme(
    content: @Composable () -> Unit,
) {
    MaterialTheme(
        colorScheme = GodColors,
        content = content,
    )
}
