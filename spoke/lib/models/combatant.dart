// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

import 'dart:convert';

/// A single condition affecting a combatant.
class CombatCondition {
  final String name;
  final int value;
  final int? durationRounds;

  const CombatCondition({
    required this.name,
    this.value = 1,
    this.durationRounds,
  });

  Map<String, dynamic> toJson() => {
        'name': name,
        'value': value,
        if (durationRounds != null) 'duration_rounds': durationRounds,
      };

  factory CombatCondition.fromJson(Map<String, dynamic> json) =>
      CombatCondition(
        name: json['name'] as String,
        value: json['value'] as int? ?? 1,
        durationRounds: json['duration_rounds'] as int?,
      );

  CombatCondition copyWith({
    String? name,
    int? value,
    int? durationRounds,
  }) =>
      CombatCondition(
        name: name ?? this.name,
        value: value ?? this.value,
        durationRounds: durationRounds ?? this.durationRounds,
      );

  @override
  String toString() => 'CombatCondition(name: $name, value: $value, durationRounds: $durationRounds)';

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is CombatCondition &&
          runtimeType == other.runtimeType &&
          name == other.name &&
          value == other.value &&
          durationRounds == other.durationRounds;

  @override
  int get hashCode => Object.hash(name, value, durationRounds);
}

/// A combat participant (PC or NPC/monster).
class Combatant {
  final String id;
  final String name;
  final bool isPc;
  final int initiative;
  int currentHp;
  final int maxHp;
  int tempHp;
  final int ac;
  List<CombatCondition> conditions;

  Combatant({
    required this.id,
    required this.name,
    required this.isPc,
    required this.initiative,
    required this.currentHp,
    required this.maxHp,
    this.tempHp = 0,
    required this.ac,
    List<CombatCondition>? conditions,
  }) : conditions = conditions ?? <CombatCondition>[];

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        'is_pc': isPc,
        'initiative': initiative,
        'current_hp': currentHp,
        'max_hp': maxHp,
        'temp_hp': tempHp,
        'ac': ac,
        'conditions': conditions.map((c) => c.toJson()).toList(),
      };

  factory Combatant.fromJson(Map<String, dynamic> json) => Combatant(
        id: json['id'] as String,
        name: json['name'] as String,
        isPc: json['is_pc'] as bool? ?? false,
        initiative: json['initiative'] as int? ?? 0,
        currentHp: json['current_hp'] as int? ?? 0,
        maxHp: json['max_hp'] as int? ?? 0,
        tempHp: json['temp_hp'] as int? ?? 0,
        ac: json['ac'] as int? ?? 0,
        conditions: (json['conditions'] as List<dynamic>? ?? [])
            .map((c) => CombatCondition.fromJson(c as Map<String, dynamic>))
            .toList(),
      );

  Combatant copyWith({
    String? id,
    String? name,
    bool? isPc,
    int? initiative,
    int? currentHp,
    int? maxHp,
    int? tempHp,
    int? ac,
    List<CombatCondition>? conditions,
  }) =>
      Combatant(
        id: id ?? this.id,
        name: name ?? this.name,
        isPc: isPc ?? this.isPc,
        initiative: initiative ?? this.initiative,
        currentHp: currentHp ?? this.currentHp,
        maxHp: maxHp ?? this.maxHp,
        tempHp: tempHp ?? this.tempHp,
        ac: ac ?? this.ac,
        conditions: conditions ?? this.conditions,
      );

  int get hpPercent => maxHp > 0 ? (currentHp * 100 / maxHp).round() : 0;

  bool get isDead => currentHp <= 0;

  @override
  String toString() =>
      'Combatant(id: $id, name: $name, initiative: $initiative, hp: $currentHp/$maxHp, temp: $tempHp, ac: $ac)';

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is Combatant &&
          runtimeType == other.runtimeType &&
          id == other.id;

  @override
  int get hashCode => id.hashCode;
}