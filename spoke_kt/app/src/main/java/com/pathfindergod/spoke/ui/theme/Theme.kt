// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable

private val LightColors = lightColorScheme(
    primary = Crimson,
    secondary = Gold,
    surface = Parchment,
    background = Parchment,
    onPrimary = Parchment,
    onSecondary = Ink,
    onSurface = Ink,
    onBackground = Ink,
)

private val DarkColors = darkColorScheme(
    primary = CrimsonBright,
    secondary = Gold,
    surface = NightSurface,
    background = NightBg,
    onPrimary = Gold,
    onSecondary = Gold,
    onSurface = Gold,
    onBackground = Gold,
)

@Composable
fun PathfinderGodTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    MaterialTheme(
        colorScheme = if (darkTheme) DarkColors else LightColors,
        content = content,
    )
}
