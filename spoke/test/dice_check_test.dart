// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

import 'dart:math';

import 'package:flutter_test/flutter_test.dart';
import 'package:pathfinder_god/dice/dice.dart';

/// Random that yields predetermined values (natural d20 rolls minus one).
class _FixedRandom implements Random {
  final List<int> values;
  int _i = 0;
  _FixedRandom(this.values);

  @override
  int nextInt(int max) => (values[_i++ % values.length] - 1) % max;

  @override
  bool nextBool() => true;

  @override
  double nextDouble() => 0.5;
}

void main() {
  group('PF2e degrees of success', () {
    test('total >= DC+10 is a critical success', () {
      final r = DiceRoller(_FixedRandom([10])).check(10, 20);
      expect(r.total, 20);
      expect(r.degree, DegreeOfSuccess.success);
    });

    test('exactly DC is a success, exactly DC-10 is a critical failure', () {
      expect(DiceRoller(_FixedRandom([10])).check(0, 10).degree,
          DegreeOfSuccess.success);
      expect(DiceRoller(_FixedRandom([10])).check(0, 20).degree,
          DegreeOfSuccess.criticalFailure);
    });

    test('natural 20 upgrades one degree (success -> crit success)', () {
      final r = DiceRoller(_FixedRandom([20])).check(0, 15);
      expect(r.natural, 20);
      expect(r.degree, DegreeOfSuccess.criticalSuccess);
    });

    test('natural 20 upgrades failure -> success', () {
      final r = DiceRoller(_FixedRandom([20])).check(-8, 15);
      expect(r.total, 12);
      expect(r.degree, DegreeOfSuccess.success);
    });

    test('natural 1 downgrades failure -> critical failure', () {
      final r = DiceRoller(_FixedRandom([1])).check(5, 10);
      expect(r.total, 6);
      expect(r.degree, DegreeOfSuccess.criticalFailure);
    });

    test('natural 1 downgrades success -> failure', () {
      final r = DiceRoller(_FixedRandom([1])).check(14, 10);
      expect(r.total, 15);
      expect(r.degree, DegreeOfSuccess.failure);
    });

    test('fortune keeps the higher of two d20s', () {
      final r = DiceRoller(_FixedRandom([3, 17])).check(0, 10, fortune: true);
      expect(r.natural, 17);
      expect(r.degree, DegreeOfSuccess.success);
    });

    test('misfortune keeps the lower of two d20s', () {
      final r = DiceRoller(_FixedRandom([3, 17])).check(2, 10, misfortune: true);
      expect(r.natural, 3);
      expect(r.degree, DegreeOfSuccess.failure);
    });

    test('hero point reroll keeps the SECOND roll', () {
      final r = DiceRoller(_FixedRandom([20, 4])).check(0, 10, heroPoint: true);
      expect(r.natural, 4);
      expect(r.heroPoint, isTrue);
      expect(r.degree, DegreeOfSuccess.failure);
    });

    test('breakdown string renders the full story', () {
      final r = DiceRoller(_FixedRandom([14])).check(7, 20);
      expect(r.breakdown, 'd20[14]+7 = 21 vs DC 20 → Success');
    });
  });
}