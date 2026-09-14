// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

import 'dart:math';

/// A dice engine for standard RPG notation, e.g. `2d6+3`, `d20`, `4d6kh3`,
/// `1d8-1`, `2d20kl1` (disadvantage).
///
/// Runs entirely on the phone — no hub needed — so dice always work, even with
/// the laptop off. This is the small bit of game logic the client owns.

/// One parsed dice term, like `4d6kh3` or a flat `+3`.
class DiceTerm {
  final int sign; // +1 or -1
  final int count; // number of dice (0 for a flat modifier)
  final int sides; // die size (0 for a flat modifier)
  final int keepHighest; // keep N highest, or -1 for "all"
  final int keepLowest; // keep N lowest, or -1 for "all"
  final int flat; // flat modifier value (used when count == 0)

  const DiceTerm({
    required this.sign,
    required this.count,
    required this.sides,
    this.keepHighest = -1,
    this.keepLowest = -1,
    this.flat = 0,
  });

  bool get isFlat => count == 0 || sides == 0;
}

/// The result of rolling one term.
class TermResult {
  final DiceTerm term;
  final List<int> rolls; // every die rolled (before keep filtering)
  final List<int> kept; // the dice actually counted
  final int subtotal; // signed contribution to the grand total

  const TermResult(this.term, this.rolls, this.kept, this.subtotal);
}

/// The full result of evaluating a notation string.
class DiceResult {
  final String notation;
  final List<TermResult> terms;
  final int total;

  const DiceResult(this.notation, this.terms, this.total);

  /// A human-readable breakdown like `2d6[4,5] + 3 = 12`.
  String get breakdown {
    final parts = <String>[];
    for (final t in terms) {
      if (t.term.isFlat) {
        parts.add('${t.subtotal >= 0 ? '+' : '-'} ${t.subtotal.abs()}');
      } else {
        final rolled = t.rolls.join(',');
        final keptNote = t.kept.length != t.rolls.length ? '→[${t.kept.join(',')}]' : '';
        final sign = t.term.sign > 0 ? '' : '- ';
        parts.add('$sign${t.term.count}d${t.term.sides}[$rolled]$keptNote');
      }
    }
    return '${parts.join(' ')} = $total';
  }
}

class DiceFormatException implements Exception {
  final String message;
  DiceFormatException(this.message);
  @override
  String toString() => 'DiceFormatException: $message';
}

class DiceRoller {
  final Random _rng;
  DiceRoller([Random? rng]) : _rng = rng ?? Random.secure();

  /// Parse and roll a notation string. Throws [DiceFormatException] on garbage.
  DiceResult roll(String notation) {
    final terms = parse(notation);
    final results = <TermResult>[];
    var total = 0;
    for (final term in terms) {
      final r = _rollTerm(term);
      results.add(r);
      total += r.subtotal;
    }
    return DiceResult(notation.trim(), results, total);
  }

  TermResult _rollTerm(DiceTerm term) {
    if (term.isFlat) {
      final v = term.sign * term.flat;
      return TermResult(term, const [], const [], v);
    }
    final rolls = List<int>.generate(term.count, (_) => _rng.nextInt(term.sides) + 1);
    var kept = List<int>.from(rolls);
    if (term.keepHighest >= 0) {
      kept.sort((a, b) => b.compareTo(a));
      kept = kept.take(term.keepHighest).toList();
    } else if (term.keepLowest >= 0) {
      kept.sort();
      kept = kept.take(term.keepLowest).toList();
    }
    final sum = kept.fold<int>(0, (a, b) => a + b);
    return TermResult(term, rolls, kept, term.sign * sum);
  }

  /// Convenience: roll a d20 with advantage (keep highest of two).
  DiceResult advantage([int modifier = 0]) =>
      roll('2d20kh1${modifier >= 0 ? '+$modifier' : '$modifier'}');

  /// Convenience: roll a d20 with disadvantage (keep lowest of two).
  DiceResult disadvantage([int modifier = 0]) =>
      roll('2d20kl1${modifier >= 0 ? '+$modifier' : '$modifier'}');

  /// Parse notation into a list of [DiceTerm]s.
  static List<DiceTerm> parse(String notation) {
    final cleaned = notation.replaceAll(' ', '').toLowerCase();
    if (cleaned.isEmpty) throw DiceFormatException('empty notation');

    // Split into signed terms while keeping the operators.
    final termRegex = RegExp(r'([+-]?)([^+-]+)');
    final terms = <DiceTerm>[];
    for (final m in termRegex.allMatches(cleaned)) {
      final sign = m.group(1) == '-' ? -1 : 1;
      final body = m.group(2)!;
      if (body.isEmpty) continue;
      terms.add(_parseBody(sign, body));
    }
    if (terms.isEmpty) throw DiceFormatException('no terms in "$notation"');
    return terms;
  }

  static DiceTerm _parseBody(int sign, String body) {
    // Flat modifier?
    final flat = int.tryParse(body);
    if (flat != null) {
      return DiceTerm(sign: sign, count: 0, sides: 0, flat: flat);
    }

    // Dice term: [count]d<sides>[kh<n>|kl<n>]
    final m = RegExp(r'^(\d*)d(\d+)(?:(kh|kl)(\d+))?$').firstMatch(body);
    if (m == null) {
      throw DiceFormatException('cannot parse term "$body"');
    }
    final count = m.group(1)!.isEmpty ? 1 : int.parse(m.group(1)!);
    final sides = int.parse(m.group(2)!);
    if (count <= 0 || count > 1000) throw DiceFormatException('bad dice count in "$body"');
    if (sides <= 0 || sides > 1000) throw DiceFormatException('bad die size in "$body"');

    var keepHighest = -1;
    var keepLowest = -1;
    final keepKind = m.group(3);
    if (keepKind == 'kh') {
      keepHighest = int.parse(m.group(4)!);
    } else if (keepKind == 'kl') {
      keepLowest = int.parse(m.group(4)!);
    }
    return DiceTerm(
      sign: sign,
      count: count,
      sides: sides,
      keepHighest: keepHighest,
      keepLowest: keepLowest,
    );
  }
}

/// Common Pathfinder dice for quick-roll buttons.
const List<String> quickDice = ['d4', 'd6', 'd8', 'd10', 'd12', 'd20', 'd100'];

/// PF2e degrees of success for a d20 check.
enum DegreeOfSuccess {
  criticalFailure,
  failure,
  success,
  criticalSuccess;

  String get label => switch (this) {
        DegreeOfSuccess.criticalSuccess => 'Critical Success',
        DegreeOfSuccess.success => 'Success',
        DegreeOfSuccess.failure => 'Failure',
        DegreeOfSuccess.criticalFailure => 'Critical Failure',
      };
}

/// The outcome of one PF2e check (d20 + modifier vs DC).
class CheckResult {
  final int natural; // the kept natural d20 roll (1–20)
  final int modifier;
  final int dc;
  final int total; // natural + modifier
  final DegreeOfSuccess degree;
  final bool heroPoint; // a hero-point reroll was used

  const CheckResult({
    required this.natural,
    required this.modifier,
    required this.dc,
    required this.total,
    required this.degree,
    this.heroPoint = false,
  });

  String get breakdown =>
      'd20[$natural]${modifier >= 0 ? '+' : '-'}${modifier.abs()} '
      '= $total vs DC $dc → ${degree.label}';
}

DegreeOfSuccess _baseDegree(int total, int dc) {
  if (total >= dc + 10) return DegreeOfSuccess.criticalSuccess;
  if (total >= dc) return DegreeOfSuccess.success;
  if (total <= dc - 10) return DegreeOfSuccess.criticalFailure;
  return DegreeOfSuccess.failure;
}

extension Pf2eChecks on DiceRoller {
  /// Roll a d20 check with full PF2e degree semantics:
  /// - critical success at total ≥ DC+10, critical failure at total ≤ DC−10
  /// - a natural 20 improves the degree by one step; a natural 1 worsens it
  /// - [fortune]/[misfortune]: roll two d20 and keep the better/worse
  /// - [heroPoint]: spend a hero point — reroll and keep the second roll
  CheckResult check(
    int modifier,
    int dc, {
    bool fortune = false,
    bool misfortune = false,
    bool heroPoint = false,
  }) {
    var natural = _rng.nextInt(20) + 1;
    if (fortune != misfortune) {
      final second = _rng.nextInt(20) + 1;
      natural = fortune ? max(natural, second) : min(natural, second);
    }
    if (heroPoint) {
      natural = _rng.nextInt(20) + 1;
    }
    final total = natural + modifier;
    var index = _baseDegree(total, dc).index;
    if (natural == 20) index = min(DegreeOfSuccess.values.length - 1, index + 1);
    if (natural == 1) index = max(0, index - 1);
    return CheckResult(
      natural: natural,
      modifier: modifier,
      dc: dc,
      total: total,
      degree: DegreeOfSuccess.values[index],
      heroPoint: heroPoint,
    );
  }
}
