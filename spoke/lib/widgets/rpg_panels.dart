// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

/// 9-slice panel widgets for consistent RPG-style UI.
class RpgPanels {
  static Widget gothicStone({
    required Widget child,
    EdgeInsetsGeometry? padding,
    EdgeInsetsGeometry? margin,
    Color? color,
  }) {
    return Container(
      margin: margin,
      padding: padding ?? const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: color ?? PathfinderTheme.parchment,
        border: Border.all(color: PathfinderTheme.gold, width: 1.5),
        borderRadius: BorderRadius.circular(12),
        boxShadow: [
          BoxShadow(
            color: PathfinderTheme.gold.withValues(alpha: 0.15),
            blurRadius: 8,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: child,
    );
  }

  static Widget darkParchment({
    required Widget child,
    EdgeInsetsGeometry? padding,
    EdgeInsetsGeometry? margin,
  }) {
    return Container(
      margin: margin,
      padding: padding ?? const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: PathfinderTheme.parchmentDeep,
        border: Border.all(color: PathfinderTheme.gold, width: 1),
        borderRadius: BorderRadius.circular(8),
      ),
      child: child,
    );
  }

  static Widget simpleGold({
    required Widget child,
    EdgeInsetsGeometry? padding,
    EdgeInsetsGeometry? margin,
  }) {
    return Container(
      margin: margin,
      padding: padding ?? const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: PathfinderTheme.parchment,
        border: Border.all(color: PathfinderTheme.gold, width: 1),
        borderRadius: BorderRadius.circular(8),
      ),
      child: child,
    );
  }
}