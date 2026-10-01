// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.theme

import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.ColorScheme
import androidx.compose.ui.graphics.Color

val VoidBackground = Color(0xFF12100E)
val ParchmentSurface = Color(0xFF1E1B18)
val CrimsonPrimary = Color(0xFF7B1E1E)
val GoldAccent = Color(0xFFC8A846)
val TextPrimary = Color(0xFFE6E1DA)
val TextSecondary = Color(0xFFA89F91)
val CritRed = Color(0xFFFF2D2D)
val StatusGreen = Color(0xFF4CAF50)

val PrimaryContainer = Color(0xFF6E1B1B)
val OnPrimaryContainer = Color(0xFFFFDAD6)
val InversePrimary = Color(0xFFE8A0A0)
val SecondaryContainer = Color(0xFF4A3F1C)
val OnSecondaryContainer = Color(0xFFF2E3A8)
val TertiaryAccent = Color(0xFFB0A79B)
val OnTertiary = Color(0xFF2A241E)
val TertiaryContainer = Color(0xFF3A322B)
val OnTertiaryContainer = Color(0xFFE4DCD2)
val SurfaceVariant = Color(0xFF262220)
val SurfaceTint = CrimsonPrimary
val InverseSurface = Color(0xFFE6E1DA)
val InverseOnSurface = Color(0xFF1E1B18)
val ErrorRole = Color(0xFFFFB4AB)
val OnError = Color(0xFF690005)
val ErrorContainer = Color(0xFF93000A)
val OnErrorContainer = Color(0xFFFFDAD6)
val OutlineVariant = Color(0xFF4A4234)
val Scrim = Color(0xFF000000)
val SurfaceBright = Color(0xFF38332F)
val SurfaceDim = Color(0xFF12100E)
val SurfaceContainerLowest = Color(0xFF0D0B0A)
val SurfaceContainerLow = Color(0xFF1B1816)
val SurfaceContainer = Color(0xFF211D1B)
val SurfaceContainerHigh = Color(0xFF2B2623)
val SurfaceContainerHighest = Color(0xFF362F2B)

val GodColorScheme: ColorScheme = darkColorScheme(
    primary = CrimsonPrimary,
    onPrimary = TextPrimary,
    primaryContainer = PrimaryContainer,
    onPrimaryContainer = OnPrimaryContainer,
    inversePrimary = InversePrimary,
    secondary = GoldAccent,
    onSecondary = VoidBackground,
    secondaryContainer = SecondaryContainer,
    onSecondaryContainer = OnSecondaryContainer,
    tertiary = TertiaryAccent,
    onTertiary = OnTertiary,
    tertiaryContainer = TertiaryContainer,
    onTertiaryContainer = OnTertiaryContainer,
    background = VoidBackground,
    onBackground = TextPrimary,
    surface = ParchmentSurface,
    onSurface = TextPrimary,
    surfaceVariant = SurfaceVariant,
    onSurfaceVariant = TextSecondary,
    surfaceTint = SurfaceTint,
    inverseSurface = InverseSurface,
    inverseOnSurface = InverseOnSurface,
    error = ErrorRole,
    onError = OnError,
    errorContainer = ErrorContainer,
    onErrorContainer = OnErrorContainer,
    outline = GoldAccent,
    outlineVariant = OutlineVariant,
    scrim = Scrim,
    surfaceBright = SurfaceBright,
    surfaceDim = SurfaceDim,
    surfaceContainerLowest = SurfaceContainerLowest,
    surfaceContainerLow = SurfaceContainerLow,
    surfaceContainer = SurfaceContainer,
    surfaceContainerHigh = SurfaceContainerHigh,
    surfaceContainerHighest = SurfaceContainerHighest,
)
