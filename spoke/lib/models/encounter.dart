// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

import 'dart:convert';

/// A monster in a generated encounter.
class EncounterMonster {
  final String name;
  final int count;
  final int level;
  final int xpEach;
  final int totalXp;
  final String sourceBook;
  final String content;

  const EncounterMonster({
    required this.name,
    required this.count,
    required this.level,
    required this.xpEach,
    required this.totalXp,
    required this.sourceBook,
    required this.content,
  });

  Map<String, dynamic> toJson() => {
        'name': name,
        'count': count,
        'level': level,
        'xp_each': xpEach,
        'total_xp': totalXp,
        'source_book': sourceBook,
        'content': content,
      };

  factory EncounterMonster.fromJson(Map<String, dynamic> json) =>
      EncounterMonster(
        name: json['name'] as String,
        count: json['count'] as int? ?? 1,
        level: json['level'] as int? ?? 1,
        xpEach: json['xp_each'] as int? ?? 0,
        totalXp: json['total_xp'] as int? ?? 0,
        sourceBook: json['source_book'] as String? ?? '',
        content: json['content'] as String? ?? '',
      );

  EncounterMonster copyWith({
    String? name,
    int? count,
    int? level,
    int? xpEach,
    int? totalXp,
    String? sourceBook,
    String? content,
  }) =>
      EncounterMonster(
        name: name ?? this.name,
        count: count ?? this.count,
        level: level ?? this.level,
        xpEach: xpEach ?? this.xpEach,
        totalXp: totalXp ?? this.totalXp,
        sourceBook: sourceBook ?? this.sourceBook,
        content: content ?? this.content,
      );
}

/// The full generated encounter result.
class GeneratedEncounter {
  final int targetXp;
  final int totalXp;
  final int partyLevel;
  final int partySize;
  final String threat;
  final String theme;
  final List<EncounterMonster> monsters;

  const GeneratedEncounter({
    required this.targetXp,
    required this.totalXp,
    required this.partyLevel,
    required this.partySize,
    required this.threat,
    required this.theme,
    required this.monsters,
  });

  Map<String, dynamic> toJson() => {
        'target_xp': targetXp,
        'total_xp': totalXp,
        'party_level': partyLevel,
        'party_size': partySize,
        'threat': threat,
        'theme': theme,
        'monsters': monsters.map((m) => m.toJson()).toList(),
      };

  factory GeneratedEncounter.fromJson(Map<String, dynamic> json) =>
      GeneratedEncounter(
        targetXp: json['target_xp'] as int? ?? 0,
        totalXp: json['total_xp'] as int? ?? 0,
        partyLevel: json['party_level'] as int? ?? 1,
        partySize: json['party_size'] as int? ?? 4,
        threat: json['threat'] as String? ?? 'moderate',
        theme: json['theme'] as String? ?? '',
        monsters: (json['monsters'] as List<dynamic>? ?? [])
            .map((e) => EncounterMonster.fromJson(e as Map<String, dynamic>))
            .toList(),
      );

  int get monsterCount => monsters.fold(0, (sum, m) => sum + m.count);

  @override
  String toString() =>
      'GeneratedEncounter(partyLevel: $partyLevel, threat: $threat, theme: $theme, '
      'targetXp: $targetXp, totalXp: $totalXp, monsters: $monsterCount)';
}