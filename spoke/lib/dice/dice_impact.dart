// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

import 'package:flutter/material.dart';

import '../services/audio_service.dart';

enum DiceSkinKind { obsidian, blood, arcane }

class DiceSkin {
  final DiceSkinKind kind;
  final List<Color> gradient;
  final Color edge;
  final Color glow;
  final Color face;
  const DiceSkin({
    required this.kind,
    required this.gradient,
    required this.edge,
    required this.glow,
    required this.face,
  });

  String get label {
    switch (kind) {
      case DiceSkinKind.obsidian:
        return 'Obsidian';
      case DiceSkinKind.blood:
        return 'Blood';
      case DiceSkinKind.arcane:
        return 'Arcane';
    }
  }

  static const obsidian = DiceSkin(
    kind: DiceSkinKind.obsidian,
    gradient: [Color(0xFF2B2B33), Color(0xFF0E0E13)],
    edge: Color(0xFF00E5FF),
    glow: Color(0xFF00E5FF),
    face: Colors.white,
  );

  static const blood = DiceSkin(
    kind: DiceSkinKind.blood,
    gradient: [Color(0xFF4A0E0E), Color(0xFF1A0505)],
    edge: Color(0xFFFF2D2D),
    glow: Color(0xFFFF2D2D),
    face: Color(0xFFFFE9C9),
  );

  static const arcane = DiceSkin(
    kind: DiceSkinKind.arcane,
    gradient: [Color(0xFF2A1A4A), Color(0xFF0D0618)],
    edge: Color(0xFFB388FF),
    glow: Color(0xFFB388FF),
    face: Color(0xFFEDE7FF),
  );

  static const List<DiceSkin> all = [obsidian, blood, arcane];

  static DiceSkin byKind(DiceSkinKind k) {
    switch (k) {
      case DiceSkinKind.obsidian:
        return obsidian;
      case DiceSkinKind.blood:
        return blood;
      case DiceSkinKind.arcane:
        return arcane;
    }
  }
}

class DiceImpact {
  static bool isNat20(int value, int sides) => sides == 20 && value == 20;
  static bool isNat1(int value, int sides) => sides == 20 && value == 1;

  static Sfx sfxFor(int value, int sides) {
    if (isNat20(value, sides)) return Sfx.crit;
    if (isNat1(value, sides)) return Sfx.fail;
    return Sfx.dice;
  }

  static double shakeFor(int value, int sides) {
    if (isNat20(value, sides)) return 1.0;
    if (isNat1(value, sides)) return 0.7;
    if (sides == 20 && (value >= 18 || value <= 3)) return 0.35;
    return 0.15;
  }

  static bool flashFor(int value, int sides) =>
      isNat20(value, sides) || isNat1(value, sides);

  static String markerFor(int value, int sides) {
    if (isNat20(value, sides)) return 'NAT 20';
    if (isNat1(value, sides)) return 'FUMBLE';
    return '$value';
  }
}
