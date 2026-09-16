// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

import 'package:share_plus/share_plus.dart';

import '../models/character.dart';

/// Generates Markdown character sheets from Character models.
class ExportService {
  static String generateMarkdownSheet(Character c) {
    final buf = StringBuffer();

    buf.writeln('# ${c.name}');
    buf.writeln('**Level ${c.level} ${c.ancestry} ${c.characterClass}${c.subclass.isNotEmpty ? ' (${c.subclass})' : ''}**');
    if (c.heritage.isNotEmpty) buf.writeln('**Heritage:** ${c.heritage}');
    if (c.background.isNotEmpty) buf.writeln('**Background:** ${c.background}');
    if (c.deity.isNotEmpty) buf.writeln('**Deity:** ${c.deity}');
    if (c.alignment.isNotEmpty) buf.writeln('**Alignment:** ${c.alignment}');
    buf.writeln('');

    buf.writeln('## Abilities');
    buf.writeln('| Ability | Score | Mod |');
    buf.writeln('|---------|-------|-----|');
    _writeAbilityRow(buf, 'STR', c.abilities.str, c.abilities.strMod);
    _writeAbilityRow(buf, 'DEX', c.abilities.dex, c.abilities.dexMod);
    _writeAbilityRow(buf, 'CON', c.abilities.con, c.abilities.conMod);
    _writeAbilityRow(buf, 'INT', c.abilities.int_, c.abilities.intMod);
    _writeAbilityRow(buf, 'WIS', c.abilities.wis, c.abilities.wisMod);
    _writeAbilityRow(buf, 'CHA', c.abilities.cha, c.abilities.chaMod);
    buf.writeln('');

    buf.writeln('## Combat Stats');
    buf.writeln('| Stat | Value |');
    buf.writeln('|------|-------|');
    buf.writeln('| HP | ${c.derived.hp} / ${c.derived.maxHp} |');
    buf.writeln('| AC | ${c.derived.ac} |');
    buf.writeln('| Fortitude | ${c.derived.fortitude >= 0 ? "+" : ""}${c.derived.fortitude} |');
    buf.writeln('| Reflex | ${c.derived.reflex >= 0 ? "+" : ""}${c.derived.reflex} |');
    buf.writeln('| Will | ${c.derived.will >= 0 ? "+" : ""}${c.derived.will} |');
    buf.writeln('| Perception | ${c.derived.perception >= 0 ? "+" : ""}${c.derived.perception} |');
    buf.writeln('| Speed | ${c.derived.speed} ft |');
    buf.writeln('| Initiative | ${c.derived.initiative >= 0 ? "+" : ""}${c.derived.initiative} |');
    buf.writeln('| Class DC | ${c.derived.classDC} |');
    buf.writeln('| Spell DC | ${c.derived.spellDC} |');
    buf.writeln('| Spell Attack | ${c.derived.spellAttack >= 0 ? "+" : ""}${c.derived.spellAttack} |');
    buf.writeln('');

    buf.writeln('## Proficiencies');
    _writeProficiencySection(buf, 'Skills', {
      'Acrobatics': 'acrobatics',
      'Arcana': 'arcana',
      'Athletics': 'athletics',
      'Crafting': 'crafting',
      'Deception': 'deception',
      'Diplomacy': 'diplomacy',
      'Intimidation': 'intimidation',
      'Lore': 'lore',
      'Medicine': 'medicine',
      'Nature': 'nature',
      'Occultism': 'occultism',
      'Performance': 'performance',
      'Religion': 'religion',
      'Society': 'society',
      'Stealth': 'stealth',
      'Survival': 'survival',
      'Thievery': 'thievery',
    }, c.proficiencies.skills.toMap());
    _writeProficiencySection(buf, 'Saves', {
      'Fortitude': 'fortitude',
      'Reflex': 'reflex',
      'Will': 'will',
      'Perception': 'perception',
    }, c.proficiencies.defenses.toMap());
    _writeProficiencySection(buf, 'Attacks', {
      'Unarmed': 'unarmed',
      'Simple Weapons': 'simpleWeapons',
      'Martial Weapons': 'martialWeapons',
      'Advanced Weapons': 'advancedWeapons',
    }, c.proficiencies.defenses.toMap());
    _writeProficiencySection(buf, 'Armor', {
      'Unarmored': 'unarmored',
      'Light Armor': 'lightArmor',
      'Medium Armor': 'mediumArmor',
      'Heavy Armor': 'heavyArmor',
    }, c.proficiencies.defenses.toMap());
    _writeProficiencySection(buf, 'Class', {
      'Class DC': 'classDC',
      'Spell DC': 'spellDC',
      'Spell Attack': 'spellAttack',
    }, c.proficiencies.classProfs.toMap());
    buf.writeln('');

    if (c.feats.isNotEmpty) {
      buf.writeln('## Feats');
      for (final f in c.feats) {
        buf.writeln('- **${f.name}** (${f.type}, Level ${f.level})');
        if (f.description.isNotEmpty) {
          buf.writeln('  > ${f.description}');
        }
        if (f.prerequisites != null && f.prerequisites!.isNotEmpty) {
          buf.writeln('  *Prerequisites: ${f.prerequisites}*');
        }
      }
      buf.writeln('');
    }

    if (c.spellcasting.repertoire.isNotEmpty) {
      buf.writeln('## Spells');
      buf.writeln('**Tradition:** ${c.spellcasting.tradition} | **Key Ability:** ${c.spellcasting.keyAbility}');
      buf.writeln('**Focus Pool:** ${c.spellcasting.focusPool} / ${c.spellcasting.focusMax}');
      buf.writeln('');
      for (var i = 0; i < c.spellcasting.slotsPerLevel.length; i++) {
        final slots = c.spellcasting.slotsPerLevel[i];
        if (slots > 0 || c.spellcasting.repertoire.any((s) => s.level == i)) {
          final label = i == 0 ? 'Cantrips' : 'Level $i';
          buf.writeln('### $label');
          final spells = c.spellcasting.repertoire.where((s) => s.level == i).toList();
          if (spells.isEmpty) {
            buf.writeln('*No spells known*');
          } else {
            for (final s in spells) {
              buf.writeln('- **${s.name}** (${s.tradition}, ${s.school}${s.isFocus ? ', Focus' : ''}${s.isRitual ? ', Ritual' : ''}${s.isCantrip ? ', Cantrip' : ''})');
              if (s.castingTime.isNotEmpty) buf.writeln('  *Casting Time: ${s.castingTime}*');
              if (s.range.isNotEmpty) buf.writeln('  *Range: ${s.range}*');
              if (s.components.isNotEmpty) buf.writeln('  *Components: ${s.components}*');
              if (s.duration.isNotEmpty) buf.writeln('  *Duration: ${s.duration}*');
              if (s.description.isNotEmpty) buf.writeln('  ${s.description}');
              buf.writeln('');
            }
          }
        }
        buf.writeln('');
      }
      buf.writeln('');
    }

    buf.writeln('## Equipment');
    if (c.equipment.weapons.isNotEmpty) {
      buf.writeln('### Weapons');
      for (final w in c.equipment.weapons) {
        buf.writeln('- **${w.name}** (${w.group}): ${w.damage} ${w.damageType} [${w.traits}]');
      }
      buf.writeln('');
    }
    if (c.equipment.armor.name != 'Unarmored') {
      buf.writeln('### Armor');
      final a = c.equipment.armor;
      buf.writeln('- **${a.name}** (${a.category}): AC +${a.acBonus}, Dex Cap ${a.dexCap}, Check Penalty ${a.checkPenalty}, Speed Penalty ${a.speedPenalty}');
      buf.writeln('');
    }
    if (c.equipment.shield != null) {
      buf.writeln('### Shield');
      final s = c.equipment.shield!;
      buf.writeln('- **${s.name}**: AC +${s.acBonus}, Hardness ${s.hardness}, HP ${s.hp} (BT ${s.bt})');
      buf.writeln('');
    }
    if (c.equipment.gear.isNotEmpty) {
      buf.writeln('### Gear');
      c.equipment.gear.forEach((item, qty) => buf.writeln('- $item x$qty'));
      buf.writeln('');
    }
    buf.writeln('**Currency:** ${c.equipment.pp} pp ${c.equipment.gp} gp ${c.equipment.sp} sp ${c.equipment.cp} cp');
    buf.writeln('');

    if (c.conditions.dying > 0 ||
        c.conditions.wounded > 0 ||
        c.conditions.doomed > 0 ||
        c.conditions.fatigued > 0 ||
        c.conditions.frightened > 0 ||
        c.conditions.sickened > 0 ||
        c.conditions.stunned > 0 ||
        c.conditions.slowed > 0 ||
        c.conditions.clumsy > 0 ||
        c.conditions.enfeebled > 0 ||
        c.conditions.drained > 0) {
      buf.writeln('## Conditions');
      if (c.conditions.dying > 0) buf.writeln('- **Dying:** ${c.conditions.dying}');
      if (c.conditions.wounded > 0) buf.writeln('- **Wounded:** ${c.conditions.wounded}');
      if (c.conditions.doomed > 0) buf.writeln('- **Doomed:** ${c.conditions.doomed}');
      if (c.conditions.fatigued > 0) buf.writeln('- **Fatigued:** ${c.conditions.fatigued}');
      if (c.conditions.frightened > 0) buf.writeln('- **Frightened:** ${c.conditions.frightened}');
      if (c.conditions.sickened > 0) buf.writeln('- **Sickened:** ${c.conditions.sickened}');
      if (c.conditions.stunned > 0) buf.writeln('- **Stunned:** ${c.conditions.stunned}');
      if (c.conditions.slowed > 0) buf.writeln('- **Slowed:** ${c.conditions.slowed}');
      if (c.conditions.clumsy > 0) buf.writeln('- **Clumsy:** ${c.conditions.clumsy}');
      if (c.conditions.enfeebled > 0) buf.writeln('- **Enfeebled:** ${c.conditions.enfeebled}');
      if (c.conditions.drained > 0) buf.writeln('- **Drained:** ${c.conditions.drained}');
      buf.writeln('');
    }

    if (c.notes.isNotEmpty) {
      buf.writeln('## Notes');
      buf.writeln(c.notes);
      buf.writeln('');
    }

    buf.writeln('---');
    buf.writeln('*Generated by Pathfinder God*');
    return buf.toString();
  }

  static void _writeAbilityRow(StringBuffer buf, String label, int score, int mod) {
    final modStr = mod >= 0 ? '+$mod' : '$mod';
    buf.write('| $label | $score | $modStr |\n');
  }

  static void _writeProficiencySection(StringBuffer buf, String title, Map<String, String> fields, Map<String, int> source) {
    buf.write('### $title\n');
    buf.write('| Proficiency | Rank |\n');
    buf.write('|-------------|------|\n');
    for (final entry in fields.entries) {
      final rank = source[entry.value];
      final rankStr = rank != null ? ['U', 'T', 'E', 'M', 'L'][rank] : 'U';
      buf.write('| ${entry.key} | $rankStr |\n');
    }
    buf.write('\n');
  }

  static Future<void> shareCharacter(Character c) async {
    final markdown = generateMarkdownSheet(c);
    await SharePlus.instance.share(
      ShareParams(
        text: markdown,
        subject: '${c.name} - Pathfinder 2e Character',
      ),
    );
  }
}