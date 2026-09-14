// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

import 'package:flutter_test/flutter_test.dart';
import 'package:pathfinder_god/models/character.dart';

void main() {
  group('G4-3 Derived stats match PF2e Remaster', () {
    test('L1 Human Fighter - Chain Mail', () {
      final c = Character(
        name: 'Valen',
        ancestry: 'Human',
        characterClass: 'Fighter',
        level: 1,
        abilities: const AbilityScores(str: 18, dex: 12, con: 14, int_: 10, wis: 12, cha: 10),
        proficiencies: Proficiencies(
          defenses: const DefenseProficiencies(
            fortitude: Proficiency.trained,
            reflex: Proficiency.trained,
            will: Proficiency.trained,
            perception: Proficiency.trained,
            unarmored: Proficiency.trained,
            mediumArmor: Proficiency.trained,
          ),
          classProfs: const ClassProficiencies(classDC: Proficiency.trained),
        ),
        equipment: Equipment(
          armor: const Armor(name: 'Chain Mail', category: 'medium', acBonus: 4, dexCap: 1, speedPenalty: 1),
        ),
      ).recalculateDerived();

      expect(c.derived.maxHp, 20);
      expect(c.derived.ac, 18);
      expect(c.derived.fortitude, 5);
      expect(c.derived.reflex, 4);
      expect(c.derived.will, 4);
      expect(c.derived.perception, 4);
      expect(c.derived.classDC, 17);
      expect(c.derived.speed, 24);
      expect(c.derived.bulkLimit, 9);
      expect(c.derived.initiative, 4);
    });

    test('L3 Elf Wizard - Explorer Clothes', () {
      final c = Character(
        name: 'Elyndra',
        ancestry: 'Elf',
        characterClass: 'Wizard',
        level: 3,
        abilities: const AbilityScores(str: 10, dex: 14, con: 12, int_: 18, wis: 10, cha: 12),
        proficiencies: Proficiencies(
          defenses: const DefenseProficiencies(
            fortitude: Proficiency.trained,
            reflex: Proficiency.trained,
            will: Proficiency.expert,
            perception: Proficiency.trained,
            unarmored: Proficiency.trained,
          ),
          classProfs: const ClassProficiencies(classDC: Proficiency.trained, spellDC: Proficiency.trained, spellAttack: Proficiency.trained),
        ),
        spellcasting: Spellcasting(tradition: 'arcane', keyAbility: 'int', slotsPerLevel: const [5, 3, 3, 3]),
        equipment: Equipment(armor: const Armor(name: 'Explorer Clothes', category: 'unarmored', acBonus: 0, dexCap: 5)),
      ).recalculateDerived();

      expect(c.derived.maxHp, 27);
      expect(c.derived.ac, 17);
      expect(c.derived.fortitude, 6);
      expect(c.derived.reflex, 7);
      expect(c.derived.will, 7);
      expect(c.derived.perception, 5);
      expect(c.derived.classDC, 19);
      expect(c.derived.spellDC, 19);
      expect(c.derived.spellAttack, 9);
      expect(c.derived.speed, 30);
    });

    test('L5 Dwarf Cleric - Breastplate', () {
      final c = Character(
        name: 'Borin',
        ancestry: 'Dwarf',
        characterClass: 'Cleric',
        level: 5,
        abilities: const AbilityScores(str: 14, dex: 10, con: 16, int_: 10, wis: 18, cha: 12),
        proficiencies: Proficiencies(
          defenses: const DefenseProficiencies(
            fortitude: Proficiency.expert,
            reflex: Proficiency.trained,
            will: Proficiency.expert,
            perception: Proficiency.expert,
            mediumArmor: Proficiency.trained,
          ),
          classProfs: const ClassProficiencies(classDC: Proficiency.trained, spellDC: Proficiency.expert, spellAttack: Proficiency.expert),
        ),
        spellcasting: Spellcasting(tradition: 'divine', keyAbility: 'wis'),
        equipment: Equipment(armor: const Armor(name: 'Breastplate', category: 'medium', acBonus: 4, dexCap: 1)),
      ).recalculateDerived();

      expect(c.derived.maxHp, 65);
      expect(c.derived.ac, 21);
      expect(c.derived.fortitude, 12);
      expect(c.derived.reflex, 7);
      expect(c.derived.will, 13);
      expect(c.derived.perception, 13);
      expect(c.derived.classDC, 21);
      expect(c.derived.spellDC, 23);
      expect(c.derived.spellAttack, 13);
      expect(c.derived.speed, 20);
    });

    test('L10 Goblin Rogue - Leather', () {
      final c = Character(
        name: 'Snik',
        ancestry: 'Goblin',
        characterClass: 'Rogue',
        level: 10,
        abilities: const AbilityScores(str: 10, dex: 19, con: 12, int_: 14, wis: 10, cha: 16),
        proficiencies: Proficiencies(
          defenses: const DefenseProficiencies(
            fortitude: Proficiency.trained,
            reflex: Proficiency.master,
            will: Proficiency.trained,
            perception: Proficiency.master,
            lightArmor: Proficiency.trained,
          ),
          classProfs: const ClassProficiencies(classDC: Proficiency.master),
        ),
        equipment: Equipment(armor: const Armor(name: 'Leather Armor', category: 'light', acBonus: 1, dexCap: 4)),
      ).recalculateDerived();

      expect(c.derived.maxHp, 96);
      expect(c.derived.ac, 27);
      expect(c.derived.fortitude, 13);
      expect(c.derived.reflex, 20);
      expect(c.derived.will, 12);
      expect(c.derived.perception, 16);
      expect(c.derived.classDC, 26);
      expect(c.derived.speed, 25);
      expect(c.derived.bulkLimit, 5);
    });

    test('L20 Orc Barbarian - Full Plate with Shield', () {
      final c = Character(
        name: 'Gorthak',
        ancestry: 'Orc',
        characterClass: 'Barbarian',
        level: 20,
        abilities: const AbilityScores(str: 22, dex: 14, con: 20, int_: 8, wis: 12, cha: 10),
        proficiencies: Proficiencies(
          defenses: const DefenseProficiencies(
            fortitude: Proficiency.legendary,
            reflex: Proficiency.trained,
            will: Proficiency.master,
            perception: Proficiency.master,
            mediumArmor: Proficiency.trained,
            heavyArmor: Proficiency.trained,
            unarmored: Proficiency.trained,
          ),
          classProfs: const ClassProficiencies(classDC: Proficiency.legendary),
        ),
        equipment: Equipment(
          armor: const Armor(name: 'Full Plate', category: 'heavy', acBonus: 6, dexCap: 0),
          shield: const Shield(name: 'Steel Shield', acBonus: 2),
        ),
      ).recalculateDerived();

      expect(c.derived.maxHp, 350);
      expect(c.derived.ac, 40);
      expect(c.derived.fortitude, 33);
      expect(c.derived.reflex, 24);
      expect(c.derived.will, 27);
      expect(c.derived.perception, 27);
      expect(c.derived.classDC, 44);
      expect(c.derived.speed, 25);
      expect(c.derived.bulkLimit, 11);
    });
  });
}
