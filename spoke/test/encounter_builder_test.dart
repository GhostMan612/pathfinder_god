// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

import 'package:flutter_test/flutter_test.dart';
import 'package:pathfinder_god/models/encounter.dart';

void main() {
  group('Encounter models', () {
    test('EncounterMonster JSON serialization', () {
      const m = EncounterMonster(
        name: 'Goblin Warrior',
        count: 3,
        level: 1,
        xpEach: 30,
        totalXp: 90,
        sourceBook: 'Bestiary',
        content: 'Goblin Warrior content',
      );

      final json = m.toJson();
      expect(json['name'], 'Goblin Warrior');
      expect(json['count'], 3);
      expect(json['level'], 1);
      expect(json['xp_each'], 30);
      expect(json['total_xp'], 90);
      expect(json['source_book'], 'Bestiary');

      final m2 = EncounterMonster.fromJson(json);
      expect(m2.name, m.name);
      expect(m2.count, m.count);
      expect(m2.level, m.level);
      expect(m2.xpEach, m.xpEach);
      expect(m2.totalXp, m.totalXp);
      expect(m2.sourceBook, m.sourceBook);
    });

    test('GeneratedEncounter JSON serialization', () {
      const monsters = [
        EncounterMonster(
          name: 'Goblin Warrior',
          count: 3,
          level: 1,
          xpEach: 30,
          totalXp: 90,
          sourceBook: 'Bestiary',
          content: 'Goblin Warrior content',
        ),
        EncounterMonster(
          name: 'Goblin Commando',
          count: 1,
          level: 2,
          xpEach: 40,
          totalXp: 40,
          sourceBook: 'Bestiary',
          content: 'Goblin Commando content',
        ),
      ];

      const e = GeneratedEncounter(
        targetXp: 130,
        totalXp: 130,
        partyLevel: 1,
        partySize: 4,
        threat: 'moderate',
        theme: 'Goblin ambush',
        monsters: monsters,
      );

      final json = e.toJson();
      expect(json['target_xp'], 130);
      expect(json['total_xp'], 130);
      expect(json['party_level'], 1);
      expect(json['party_size'], 4);
      expect(json['threat'], 'moderate');
      expect(json['theme'], 'Goblin ambush');
      expect((json['monsters'] as List).length, 2);

      final e2 = GeneratedEncounter.fromJson(json);
      expect(e2.targetXp, e.targetXp);
      expect(e2.totalXp, e.totalXp);
      expect(e2.partyLevel, e.partyLevel);
      expect(e2.partySize, e.partySize);
      expect(e2.threat, e.threat);
      expect(e2.theme, e.theme);
      expect(e2.monsters.length, e.monsters.length);
      expect(e2.monsterCount, 4); // 3 + 1
    });

    test('EncounterMonster copyWith', () {
      const m = EncounterMonster(
        name: 'Test',
        count: 1,
        level: 1,
        xpEach: 40,
        totalXp: 40,
        sourceBook: 'Test',
        content: 'Test content',
      );

      final m2 = m.copyWith(count: 3, totalXp: 120);
      expect(m2.count, 3);
      expect(m2.totalXp, 120);
      expect(m2.name, 'Test'); // unchanged
    });

    test('GeneratedEncounter monsterCount', () {
      const e = GeneratedEncounter(
        targetXp: 100,
        totalXp: 100,
        partyLevel: 1,
        partySize: 4,
        threat: 'moderate',
        theme: 'test',
        monsters: [
          EncounterMonster(name: 'A', count: 2, level: 1, xpEach: 20, totalXp: 40, sourceBook: '', content: 'A content'),
          EncounterMonster(name: 'B', count: 3, level: 2, xpEach: 20, totalXp: 60, sourceBook: '', content: 'B content'),
        ],
      );
      expect(e.monsterCount, 5);
    });
  });
}