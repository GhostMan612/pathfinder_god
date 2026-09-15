// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

import 'package:flutter/material.dart';

/// 9-slice scaled RPG panel for ornate fantasy borders.
///
/// Uses a single square asset (e.g., 128x128) with defined corner zones.
/// Corners never stretch; edges tile; center fills.
/// Usage:
///   RpgPanel(
///     asset: 'assets/ui/stone_border.png',
///     centerSlice: Rect.fromLTRB(16, 16, 112, 112),
///     child: YourContent(),
///   )
class RpgPanel extends StatelessWidget {
  final String asset;
  final Rect centerSlice;
  final Widget child;
  final EdgeInsetsGeometry? padding;
  final Color? colorFilter;
  final BoxFit fit;
  final double? width;
  final double? height;

  const RpgPanel({
    super.key,
    required this.asset,
    required this.centerSlice,
    required this.child,
    this.padding,
    this.colorFilter,
    this.fit = BoxFit.fill,
    this.width,
    this.height,
  });

  @override
  Widget build(BuildContext context) {
    return ConstrainedBox(
      constraints: BoxConstraints(
        minWidth: width ?? 0,
        minHeight: height ?? 0,
      ),
      child: Container(
        width: width,
        height: height,
        padding: padding,
        decoration: BoxDecoration(
          image: DecorationImage(
            image: AssetImage(asset),
            centerSlice: centerSlice,
            fit: fit,
            colorFilter: colorFilter != null
                ? ColorFilter.mode(colorFilter!, BlendMode.modulate)
                : null,
          ),
        ),
        child: child,
      ),
    );
  }
}

/// Pre-defined panel styles for consistent theming.
class RpgPanels {
  static const stoneBorder = RpgPanelStyle(
    asset: 'assets/ui/stone_border.png',
    centerSlice: Rect.fromLTRB(16, 16, 112, 112),
  );

  static const parchment = RpgPanelStyle(
    asset: 'assets/ui/parchment_border.png',
    centerSlice: Rect.fromLTRB(20, 20, 108, 108),
  );

  static const goldFiligree = RpgPanelStyle(
    asset: 'assets/ui/gold_filigree.png',
    centerSlice: Rect.fromLTRB(18, 18, 110, 110),
  );

  static const gothicStone = RpgPanelStyle(
    asset: 'assets/ui/gothic_stone.png',
    centerSlice: Rect.fromLTRB(22, 22, 106, 106),
  );
}

class RpgPanelStyle {
  final String asset;
  final Rect centerSlice;

  const RpgPanelStyle({
    required this.asset,
    required this.centerSlice,
  });

  Widget build({required Widget child, EdgeInsetsGeometry? padding, Color? tint}) {
    return RpgPanel(
      asset: asset,
      centerSlice: centerSlice,
      padding: padding,
      colorFilter: tint,
      child: child,
    );
  }
}