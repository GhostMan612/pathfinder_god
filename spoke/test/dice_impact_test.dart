// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

import 'dart:math';

import 'package:flutter_test/flutter_test.dart';
import 'package:pathfinder_god/dice/dice_impact.dart';
import 'package:pathfinder_god/dice/dice_physics.dart';
import 'package:pathfinder_god/services/audio_service.dart';

void main() {
  group('DiceImpact pure mapping', () {
    test('nat20 maps to crit sfx, full shake, flash, marker', () {
      expect(DiceImpact.isNat20(20, 20), isTrue);
      expect(DiceImpact.sfxFor(20, 20), Sfx.crit);
      expect(DiceImpact.shakeFor(20, 20), 1.0);
      expect(DiceImpact.flashFor(20, 20), isTrue);
      expect(DiceImpact.markerFor(20, 20), 'NAT 20');
    });

    test('nat1 maps to fail sfx, heavy shake, flash, fumble marker', () {
      expect(DiceImpact.isNat1(1, 20), isTrue);
      expect(DiceImpact.sfxFor(1, 20), Sfx.fail);
      expect(DiceImpact.shakeFor(1, 20), 0.7);
      expect(DiceImpact.flashFor(1, 20), isTrue);
      expect(DiceImpact.markerFor(1, 20), 'FUMBLE');
    });

    test('normal d20 has no flash and light shake', () {
      expect(DiceImpact.flashFor(10, 20), isFalse);
      expect(DiceImpact.shakeFor(10, 20), 0.15);
      expect(DiceImpact.sfxFor(10, 20), Sfx.dice);
      expect(DiceImpact.markerFor(10, 20), '10');
    });

    test('non-d20 never crits', () {
      expect(DiceImpact.isNat20(20, 12), isFalse);
      expect(DiceImpact.isNat1(1, 6), isFalse);
      expect(DiceImpact.flashFor(20, 12), isFalse);
    });
  });

  group('DiceSkin presets', () {
    test('three skins with distinct edges', () {
      expect(DiceSkin.all.length, 3);
      expect(DiceSkin.byKind(DiceSkinKind.blood).label, 'Blood');
      expect(DiceSkin.byKind(DiceSkinKind.arcane).label, 'Arcane');
      expect(DiceSkin.byKind(DiceSkinKind.obsidian).label, 'Obsidian');
    });
  });

  group('Dice settle flatness', () {
    test('final axis angles land on multiples of 2pi', () {
      const twoPi = 2 * pi;
      expect(
          AnimatedDiceRoller.finalTumbleX % twoPi, closeTo(0, 1e-9));
      expect(
          AnimatedDiceRoller.finalTumbleY % twoPi, closeTo(0, 1e-9));
      expect(
          AnimatedDiceRoller.finalSpinZ % twoPi, closeTo(0, 1e-9));
    });
  });
}
