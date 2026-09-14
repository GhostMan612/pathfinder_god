// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

import 'package:flutter/material.dart';

/// A warm, parchment-and-crimson "Pathfinder" look, with a dark variant for
/// low light at the table.
class PathfinderTheme {
  // Core palette.
  static const parchment = Color(0xFFF3E9D2);
  static const parchmentDeep = Color(0xFFE7D8B5);
  static const crimson = Color(0xFF7B1E1E);
  static const crimsonBright = Color(0xFF9E2A2B);
  static const gold = Color(0xFFB8860B);
  static const ink = Color(0xFF2B2118);
  static const nightBg = Color(0xFF1A1512);
  static const nightSurface = Color(0xFF241D18);

  static ThemeData light() {
    final base = ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,
      colorScheme: ColorScheme.fromSeed(
        seedColor: crimson,
        primary: crimson,
        secondary: gold,
        surface: parchment,
        brightness: Brightness.light,
      ),
      scaffoldBackgroundColor: parchment,
    );
    return base.copyWith(
      appBarTheme: const AppBarTheme(
        backgroundColor: crimson,
        foregroundColor: parchment,
        centerTitle: true,
        elevation: 2,
      ),
      cardTheme: CardThemeData(
        color: parchmentDeep,
        elevation: 1,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      ),
      textTheme: base.textTheme.apply(bodyColor: ink, displayColor: ink),
      chipTheme: base.chipTheme.copyWith(backgroundColor: parchmentDeep),
    );
  }

  static ThemeData dark() {
    final base = ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      colorScheme: ColorScheme.fromSeed(
        seedColor: crimsonBright,
        primary: crimsonBright,
        secondary: gold,
        surface: nightSurface,
        brightness: Brightness.dark,
      ),
      scaffoldBackgroundColor: nightBg,
    );
    return base.copyWith(
      appBarTheme: const AppBarTheme(
        backgroundColor: nightSurface,
        foregroundColor: gold,
        centerTitle: true,
      ),
      cardTheme: CardThemeData(
        color: nightSurface,
        elevation: 1,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      ),
    );
  }
}
