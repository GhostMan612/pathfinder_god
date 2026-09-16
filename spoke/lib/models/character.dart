// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

import 'dart:convert';

/// PF2e proficiency ranks.
enum Proficiency { untrained, trained, expert, master, legendary }

/// Ability scores with raw values and calculated modifiers.
class AbilityScores {
  final int str;
  final int dex;
  final int con;
  final int int_;
  final int wis;
  final int cha;

  const AbilityScores({
    this.str = 10,
    this.dex = 10,
    this.con = 10,
    this.int_ = 10,
    this.wis = 10,
    this.cha = 10,
  });

  int mod(int score) => ((score - 10) / 2).floor();

  int get strMod => mod(str);
  int get dexMod => mod(dex);
  int get conMod => mod(con);
  int get intMod => mod(int_);
  int get wisMod => mod(wis);
  int get chaMod => mod(cha);

  Map<String, int> toMap() => {
        'str': str,
        'dex': dex,
        'con': con,
        'int': int_,
        'wis': wis,
        'cha': cha,
      };

  factory AbilityScores.fromMap(Map<String, dynamic> m) => AbilityScores(
        str: m['str'] as int? ?? 10,
        dex: m['dex'] as int? ?? 10,
        con: m['con'] as int? ?? 10,
        int_: m['int'] as int? ?? 10,
        wis: m['wis'] as int? ?? 10,
        cha: m['cha'] as int? ?? 10,
      );

  String toJson() => jsonEncode(toMap());
  factory AbilityScores.fromJson(String s) => AbilityScores.fromMap(jsonDecode(s) as Map<String, dynamic>);
}

/// Skill proficiencies.
class SkillProficiencies {
  final Proficiency acrobatics;
  final Proficiency arcana;
  final Proficiency athletics;
  final Proficiency crafting;
  final Proficiency deception;
  final Proficiency diplomacy;
  final Proficiency intimidation;
  final Proficiency lore;
  final Proficiency medicine;
  final Proficiency nature;
  final Proficiency occultism;
  final Proficiency performance;
  final Proficiency religion;
  final Proficiency society;
  final Proficiency stealth;
  final Proficiency survival;
  final Proficiency thievery;

  const SkillProficiencies({
    this.acrobatics = Proficiency.untrained,
    this.arcana = Proficiency.untrained,
    this.athletics = Proficiency.untrained,
    this.crafting = Proficiency.untrained,
    this.deception = Proficiency.untrained,
    this.diplomacy = Proficiency.untrained,
    this.intimidation = Proficiency.untrained,
    this.lore = Proficiency.untrained,
    this.medicine = Proficiency.untrained,
    this.nature = Proficiency.untrained,
    this.occultism = Proficiency.untrained,
    this.performance = Proficiency.untrained,
    this.religion = Proficiency.untrained,
    this.society = Proficiency.untrained,
    this.stealth = Proficiency.untrained,
    this.survival = Proficiency.untrained,
    this.thievery = Proficiency.untrained,
  });

  Map<String, int> toMap() => {
        'acrobatics': acrobatics.index,
        'arcana': arcana.index,
        'athletics': athletics.index,
        'crafting': crafting.index,
        'deception': deception.index,
        'diplomacy': diplomacy.index,
        'intimidation': intimidation.index,
        'lore': lore.index,
        'medicine': medicine.index,
        'nature': nature.index,
        'occultism': occultism.index,
        'performance': performance.index,
        'religion': religion.index,
        'society': society.index,
        'stealth': stealth.index,
        'survival': survival.index,
        'thievery': thievery.index,
      };

  factory SkillProficiencies.fromMap(Map<String, dynamic> m) => SkillProficiencies(
        acrobatics: Proficiency.values[m['acrobatics'] as int? ?? 0],
        arcana: Proficiency.values[m['arcana'] as int? ?? 0],
        athletics: Proficiency.values[m['athletics'] as int? ?? 0],
        crafting: Proficiency.values[m['crafting'] as int? ?? 0],
        deception: Proficiency.values[m['deception'] as int? ?? 0],
        diplomacy: Proficiency.values[m['diplomacy'] as int? ?? 0],
        intimidation: Proficiency.values[m['intimidation'] as int? ?? 0],
        lore: Proficiency.values[m['lore'] as int? ?? 0],
        medicine: Proficiency.values[m['medicine'] as int? ?? 0],
        nature: Proficiency.values[m['nature'] as int? ?? 0],
        occultism: Proficiency.values[m['occultism'] as int? ?? 0],
        performance: Proficiency.values[m['performance'] as int? ?? 0],
        religion: Proficiency.values[m['religion'] as int? ?? 0],
        society: Proficiency.values[m['society'] as int? ?? 0],
        stealth: Proficiency.values[m['stealth'] as int? ?? 0],
        survival: Proficiency.values[m['survival'] as int? ?? 0],
        thievery: Proficiency.values[m['thievery'] as int? ?? 0],
      );

  String toJson() => jsonEncode(toMap());
  factory SkillProficiencies.fromJson(String s) => SkillProficiencies.fromMap(jsonDecode(s) as Map<String, dynamic>);
}

/// Defense proficiencies (saves, perception, armor, weapons).
class DefenseProficiencies {
  final Proficiency fortitude;
  final Proficiency reflex;
  final Proficiency will;
  final Proficiency perception;
  final Proficiency unarmored;
  final Proficiency lightArmor;
  final Proficiency mediumArmor;
  final Proficiency heavyArmor;
  final Proficiency simpleWeapons;
  final Proficiency martialWeapons;
  final Proficiency advancedWeapons;
  final Proficiency unarmed;

  const DefenseProficiencies({
    this.fortitude = Proficiency.untrained,
    this.reflex = Proficiency.untrained,
    this.will = Proficiency.untrained,
    this.perception = Proficiency.untrained,
    this.unarmored = Proficiency.untrained,
    this.lightArmor = Proficiency.untrained,
    this.mediumArmor = Proficiency.untrained,
    this.heavyArmor = Proficiency.untrained,
    this.simpleWeapons = Proficiency.untrained,
    this.martialWeapons = Proficiency.untrained,
    this.advancedWeapons = Proficiency.untrained,
    this.unarmed = Proficiency.untrained,
  });

  Map<String, int> toMap() => {
        'fortitude': fortitude.index,
        'reflex': reflex.index,
        'will': will.index,
        'perception': perception.index,
        'unarmored': unarmored.index,
        'lightArmor': lightArmor.index,
        'mediumArmor': mediumArmor.index,
        'heavyArmor': heavyArmor.index,
        'simpleWeapons': simpleWeapons.index,
        'martialWeapons': martialWeapons.index,
        'advancedWeapons': advancedWeapons.index,
        'unarmed': unarmed.index,
      };

  factory DefenseProficiencies.fromMap(Map<String, dynamic> m) => DefenseProficiencies(
        fortitude: Proficiency.values[m['fortitude'] as int? ?? 0],
        reflex: Proficiency.values[m['reflex'] as int? ?? 0],
        will: Proficiency.values[m['will'] as int? ?? 0],
        perception: Proficiency.values[m['perception'] as int? ?? 0],
        unarmored: Proficiency.values[m['unarmored'] as int? ?? 0],
        lightArmor: Proficiency.values[m['lightArmor'] as int? ?? 0],
        mediumArmor: Proficiency.values[m['mediumArmor'] as int? ?? 0],
        heavyArmor: Proficiency.values[m['heavyArmor'] as int? ?? 0],
        simpleWeapons: Proficiency.values[m['simpleWeapons'] as int? ?? 0],
        martialWeapons: Proficiency.values[m['martialWeapons'] as int? ?? 0],
        advancedWeapons: Proficiency.values[m['advancedWeapons'] as int? ?? 0],
        unarmed: Proficiency.values[m['unarmed'] as int? ?? 0],
      );

  String toJson() => jsonEncode(toMap());
  factory DefenseProficiencies.fromJson(String s) => DefenseProficiencies.fromMap(jsonDecode(s) as Map<String, dynamic>);
}

/// Class proficiencies (class DC, spell DC, spell attack).
class ClassProficiencies {
  final Proficiency classDC;
  final Proficiency spellDC;
  final Proficiency spellAttack;

  const ClassProficiencies({
    this.classDC = Proficiency.untrained,
    this.spellDC = Proficiency.untrained,
    this.spellAttack = Proficiency.untrained,
  });

  Map<String, int> toMap() => {
        'classDC': classDC.index,
        'spellDC': spellDC.index,
        'spellAttack': spellAttack.index,
      };

  factory ClassProficiencies.fromMap(Map<String, dynamic> m) => ClassProficiencies(
        classDC: Proficiency.values[m['classDC'] as int? ?? 0],
        spellDC: Proficiency.values[m['spellDC'] as int? ?? 0],
        spellAttack: Proficiency.values[m['spellAttack'] as int? ?? 0],
      );

  String toJson() => jsonEncode(toMap());
  factory ClassProficiencies.fromJson(String s) => ClassProficiencies.fromMap(jsonDecode(s) as Map<String, dynamic>);
}

/// All proficiencies combined.
class Proficiencies {
  final SkillProficiencies skills;
  final DefenseProficiencies defenses;
  final ClassProficiencies classProfs;

  const Proficiencies({
    SkillProficiencies? skills,
    DefenseProficiencies? defenses,
    ClassProficiencies? classProfs,
  })  : skills = skills ?? const SkillProficiencies(),
        defenses = defenses ?? const DefenseProficiencies(),
        classProfs = classProfs ?? const ClassProficiencies();

  Map<String, dynamic> toMap() => {
        'skills': skills.toMap(),
        'defenses': defenses.toMap(),
        'classProfs': classProfs.toMap(),
      };

  factory Proficiencies.fromMap(Map<String, dynamic> m) => Proficiencies(
        skills: SkillProficiencies.fromMap(m['skills'] as Map<String, dynamic>? ?? {}),
        defenses: DefenseProficiencies.fromMap(m['defenses'] as Map<String, dynamic>? ?? {}),
        classProfs: ClassProficiencies.fromMap(m['classProfs'] as Map<String, dynamic>? ?? {}),
      );

  String toJson() => jsonEncode(toMap());
  factory Proficiencies.fromJson(String s) => Proficiencies.fromMap(jsonDecode(s) as Map<String, dynamic>);
}

/// A single feat entry.
class Feat {
  final String name;
  final String type; // ancestry, class, skill, general, background, free
  final int level; // level gained
  final String description;
  final String? prerequisites;

  const Feat({
    required this.name,
    required this.type,
    required this.level,
    required this.description,
    this.prerequisites,
  });

  Map<String, dynamic> toMap() => {
        'name': name,
        'type': type,
        'level': level,
        'description': description,
        'prerequisites': prerequisites,
      };

  factory Feat.fromMap(Map<String, dynamic> m) => Feat(
        name: m['name'] as String? ?? '',
        type: m['type'] as String? ?? '',
        level: m['level'] as int? ?? 1,
        description: m['description'] as String? ?? '',
        prerequisites: m['prerequisites'] as String?,
      );

  String toJson() => jsonEncode(toMap());
  factory Feat.fromJson(String s) => Feat.fromMap(jsonDecode(s) as Map<String, dynamic>);
}

/// Spell entry.
class Spell {
  final String name;
  final int level; // 1-10, 0 for cantrip
  final String tradition; // arcane, divine, occult, primal
  final String school; // abjuration, conjuration, etc.
  final String castingTime;
  final String range;
  final String components; // V, S, M, F, DF
  final String duration;
  final String description;
  final bool isFocus;
  final bool isRitual;
  final bool isCantrip;

  const Spell({
    required this.name,
    required this.level,
    required this.tradition,
    this.school = '',
    this.castingTime = '',
    this.range = '',
    this.components = '',
    this.duration = '',
    this.description = '',
    this.isFocus = false,
    this.isRitual = false,
    this.isCantrip = false,
  });

  bool get isFocusSpell => isFocus;
  bool get isCantripSpell => isCantrip || level == 0;

  Map<String, dynamic> toMap() => {
        'name': name,
        'level': level,
        'tradition': tradition,
        'school': school,
        'castingTime': castingTime,
        'range': range,
        'components': components,
        'duration': duration,
        'description': description,
        'isFocus': isFocus,
        'isRitual': isRitual,
        'isCantrip': isCantrip,
      };

  factory Spell.fromMap(Map<String, dynamic> m) => Spell(
        name: m['name'] as String? ?? '',
        level: m['level'] as int? ?? 1,
        tradition: m['tradition'] as String? ?? '',
        school: m['school'] as String? ?? '',
        castingTime: m['castingTime'] as String? ?? '',
        range: m['range'] as String? ?? '',
        components: m['components'] as String? ?? '',
        duration: m['duration'] as String? ?? '',
        description: m['description'] as String? ?? '',
        isFocus: m['isFocus'] as bool? ?? false,
        isRitual: m['isRitual'] as bool? ?? false,
        isCantrip: m['isCantrip'] as bool? ?? false,
      );

  String toJson() => jsonEncode(toMap());
  factory Spell.fromJson(String s) => Spell.fromMap(jsonDecode(s) as Map<String, dynamic>);
}

class Spellcasting {
  final String tradition; // arcane, divine, occult, primal
  final String keyAbility; // int, wis, cha
  final List<int> slotsPerLevel; // index = spell level, value = slots (cantrips at index 0)
  final int focusPool;
  final int focusMax;
  final List<Spell> repertoire; // known/prepared spells
  final bool isPrepared; // true = prepared (wizard), false = spontaneous (sorcerer)

  Spellcasting({
    this.tradition = '',
    this.keyAbility = 'cha',
    this.slotsPerLevel = const [5, 3, 3, 3, 3, 3, 2, 2, 2, 2, 1], // 0-10
    this.focusPool = 0,
    this.focusMax = 1,
    this.repertoire = const [],
    this.isPrepared = false,
  });

  Map<String, dynamic> toMap() => {
        'tradition': tradition,
        'keyAbility': keyAbility,
        'slotsPerLevel': slotsPerLevel,
        'focusPool': focusPool,
        'focusMax': focusMax,
        'repertoire': repertoire.map((s) => s.toMap()).toList(),
        'isPrepared': isPrepared,
      };

  factory Spellcasting.fromMap(Map<String, dynamic> m) => Spellcasting(
        tradition: m['tradition'] as String? ?? '',
        keyAbility: m['keyAbility'] as String? ?? 'cha',
        slotsPerLevel: (m['slotsPerLevel'] as List<dynamic>? ?? [])
            .map((e) => e as int)
            .toList(),
        focusPool: m['focusPool'] as int? ?? 0,
        focusMax: m['focusMax'] as int? ?? 1,
        repertoire: (m['repertoire'] as List<dynamic>? ?? [])
            .map((e) => Spell.fromMap(e as Map<String, dynamic>))
            .toList(),
        isPrepared: m['isPrepared'] as bool? ?? false,
      );

  String toJson() => jsonEncode(toMap());
  factory Spellcasting.fromJson(String s) => Spellcasting.fromMap(jsonDecode(s) as Map<String, dynamic>);

  /// Returns the spellcasting ability modifier for this character.
  int spellcastingMod(AbilityScores abilities) {
    switch (keyAbility.toLowerCase()) {
      case 'str':
        return abilities.strMod;
      case 'dex':
        return abilities.dexMod;
      case 'con':
        return abilities.conMod;
      case 'int':
        return abilities.intMod;
      case 'wis':
        return abilities.wisMod;
      case 'cha':
        return abilities.chaMod;
      default:
        return abilities.chaMod;
    }
  }
}

/// Weapon entry.
class Weapon {
  final String name;
  final String group; // sword, axe, bow, etc.
  final String damage; // e.g. "1d8"
  final String damageType; // P, S, B
  final String traits; // comma-separated
  final int hands; // 1 or 2
  final int potencyRune; // +1 to +3
  final int strikingRune; // 1=striking, 2=greater, 3=major
  final String propertyRunes; // comma-separated

  const Weapon({
    required this.name,
    this.group = '',
    this.damage = '1d6',
    this.damageType = 'P',
    this.traits = '',
    this.hands = 1,
    this.potencyRune = 0,
    this.strikingRune = 0,
    this.propertyRunes = '',
  });

  Map<String, dynamic> toMap() => {
        'name': name,
        'group': group,
        'damage': damage,
        'damageType': damageType,
        'traits': traits,
        'hands': hands,
        'potencyRune': potencyRune,
        'strikingRune': strikingRune,
        'propertyRunes': propertyRunes,
      };

  factory Weapon.fromMap(Map<String, dynamic> m) => Weapon(
        name: m['name'] as String? ?? '',
        group: m['group'] as String? ?? '',
        damage: m['damage'] as String? ?? '1d6',
        damageType: m['damageType'] as String? ?? 'P',
        traits: m['traits'] as String? ?? '',
        hands: m['hands'] as int? ?? 1,
        potencyRune: m['potencyRune'] as int? ?? 0,
        strikingRune: m['strikingRune'] as int? ?? 0,
        propertyRunes: m['propertyRunes'] as String? ?? '',
      );

  String toJson() => jsonEncode(toMap());
  factory Weapon.fromJson(String s) => Weapon.fromMap(jsonDecode(s) as Map<String, dynamic>);
}

/// Armor entry.
class Armor {
  final String name;
  final String category; // light, medium, heavy, unarmored
  final int acBonus;
  final int dexCap;
  final int checkPenalty;
  final int speedPenalty;
  final int potencyRune;
  final int resilienceRune; // 1=resilient, 2=greater, 3=major
  final String propertyRunes;

  const Armor({
    required this.name,
    this.category = 'unarmored',
    this.acBonus = 0,
    this.dexCap = 5,
    this.checkPenalty = 0,
    this.speedPenalty = 0,
    this.potencyRune = 0,
    this.resilienceRune = 0,
    this.propertyRunes = '',
  });

  Map<String, dynamic> toMap() => {
        'name': name,
        'category': category,
        'acBonus': acBonus,
        'dexCap': dexCap,
        'checkPenalty': checkPenalty,
        'speedPenalty': speedPenalty,
        'potencyRune': potencyRune,
        'resilienceRune': resilienceRune,
        'propertyRunes': propertyRunes,
      };

  factory Armor.fromMap(Map<String, dynamic> m) => Armor(
        name: m['name'] as String? ?? '',
        category: m['category'] as String? ?? 'unarmored',
        acBonus: m['acBonus'] as int? ?? 0,
        dexCap: m['dexCap'] as int? ?? 5,
        checkPenalty: m['checkPenalty'] as int? ?? 0,
        speedPenalty: m['speedPenalty'] as int? ?? 0,
        potencyRune: m['potencyRune'] as int? ?? 0,
        resilienceRune: m['resilienceRune'] as int? ?? 0,
        propertyRunes: m['propertyRunes'] as String? ?? '',
      );

  String toJson() => jsonEncode(toMap());
  factory Armor.fromJson(String s) => Armor.fromMap(jsonDecode(s) as Map<String, dynamic>);
}

/// Shield entry.
class Shield {
  final String name;
  final int acBonus;
  final int hardness;
  final int hp;
  final int bt;
  final int potencyRune;

  const Shield({
    required this.name,
    this.acBonus = 0,
    this.hardness = 0,
    this.hp = 0,
    this.bt = 0,
    this.potencyRune = 0,
  });

  Map<String, dynamic> toMap() => {
        'name': name,
        'acBonus': acBonus,
        'hardness': hardness,
        'hp': hp,
        'bt': bt,
        'potencyRune': potencyRune,
      };

  factory Shield.fromMap(Map<String, dynamic> m) => Shield(
        name: m['name'] as String? ?? '',
        acBonus: m['acBonus'] as int? ?? 0,
        hardness: m['hardness'] as int? ?? 0,
        hp: m['hp'] as int? ?? 0,
        bt: m['bt'] as int? ?? 0,
        potencyRune: m['potencyRune'] as int? ?? 0,
      );

  String toJson() => jsonEncode(toMap());
  factory Shield.fromJson(String s) => Shield.fromMap(jsonDecode(s) as Map<String, dynamic>);
}

/// Equipment/inventory.
class Equipment {
  final List<Weapon> weapons;
  final Armor armor;
  final Shield? shield;
  final Map<String, int> gear; // item -> quantity
  final int cp;
  final int sp;
  final int gp;
  final int pp;

  const Equipment({
    this.weapons = const [],
    Armor? armor,
    this.shield,
    this.gear = const {},
    this.cp = 0,
    this.sp = 0,
    this.gp = 0,
    this.pp = 0,
  }) : armor = armor ?? const Armor(name: 'Unarmored');

  Map<String, dynamic> toMap() => {
        'weapons': weapons.map((w) => w.toMap()).toList(),
        'armor': armor.toMap(),
        'shield': shield?.toMap(),
        'gear': gear,
        'cp': cp,
        'sp': sp,
        'gp': gp,
        'pp': pp,
      };

  factory Equipment.fromMap(Map<String, dynamic> m) => Equipment(
        weapons: (m['weapons'] as List<dynamic>? ?? [])
            .map((e) => Weapon.fromMap(e as Map<String, dynamic>))
            .toList(),
        armor: Armor.fromMap(m['armor'] as Map<String, dynamic>? ?? {}),
        shield: m['shield'] != null
            ? Shield.fromMap(m['shield'] as Map<String, dynamic>)
            : null,
        gear: Map<String, int>.from(m['gear'] as Map<dynamic, dynamic>? ?? {}),
        cp: m['cp'] as int? ?? 0,
        sp: m['sp'] as int? ?? 0,
        gp: m['gp'] as int? ?? 0,
        pp: m['pp'] as int? ?? 0,
      );

  String toJson() => jsonEncode(toMap());
  factory Equipment.fromJson(String s) => Equipment.fromMap(jsonDecode(s) as Map<String, dynamic>);
}

/// All derived/computed stats.
class DerivedStats {
  final int hp;
  final int maxHp;
  final int ac;
  final int fortitude;
  final int reflex;
  final int will;
  final int perception;
  final int classDC;
  final int spellDC;
  final int spellAttack;
  final int speed;
  final int bulkLimit;
  final int initiative;

  const DerivedStats({
    this.hp = 0,
    this.maxHp = 0,
    this.ac = 10,
    this.fortitude = 0,
    this.reflex = 0,
    this.will = 0,
    this.perception = 0,
    this.classDC = 10,
    this.spellDC = 10,
    this.spellAttack = 0,
    this.speed = 25,
    this.bulkLimit = 5,
    this.initiative = 0,
  });

  Map<String, dynamic> toMap() => {
        'hp': hp,
        'maxHp': maxHp,
        'ac': ac,
        'fortitude': fortitude,
        'reflex': reflex,
        'will': will,
        'perception': perception,
        'classDC': classDC,
        'spellDC': spellDC,
        'spellAttack': spellAttack,
        'speed': speed,
        'bulkLimit': bulkLimit,
        'initiative': initiative,
      };

  factory DerivedStats.fromMap(Map<String, dynamic> m) => DerivedStats(
        hp: m['hp'] as int? ?? 0,
        maxHp: m['maxHp'] as int? ?? 0,
        ac: m['ac'] as int? ?? 10,
        fortitude: m['fortitude'] as int? ?? 0,
        reflex: m['reflex'] as int? ?? 0,
        will: m['will'] as int? ?? 0,
        perception: m['perception'] as int? ?? 0,
        classDC: m['classDC'] as int? ?? 10,
        spellDC: m['spellDC'] as int? ?? 10,
        spellAttack: m['spellAttack'] as int? ?? 0,
        speed: m['speed'] as int? ?? 25,
        bulkLimit: m['bulkLimit'] as int? ?? 5,
        initiative: m['initiative'] as int? ?? 0,
      );

  String toJson() => jsonEncode(toMap());
  factory DerivedStats.fromJson(String s) => DerivedStats.fromMap(jsonDecode(s) as Map<String, dynamic>);
}

/// Condition trackers.
class ConditionTrackers {
  final int heroPoints;
  final int maxHeroPoints;
  final int dying;
  final int wounded;
  final int doomed;
  final int fatigued;
  final int frightened;
  final int sickened;
  final int stunned;
  final int slowed;
  final int clumsy;
  final int enfeebled;
  final int drained;

  const ConditionTrackers({
    this.heroPoints = 1,
    this.maxHeroPoints = 1,
    this.dying = 0,
    this.wounded = 0,
    this.doomed = 0,
    this.fatigued = 0,
    this.frightened = 0,
    this.sickened = 0,
    this.stunned = 0,
    this.slowed = 0,
    this.clumsy = 0,
    this.enfeebled = 0,
    this.drained = 0,
  });

  Map<String, int> toMap() => {
        'heroPoints': heroPoints,
        'maxHeroPoints': maxHeroPoints,
        'dying': dying,
        'wounded': wounded,
        'doomed': doomed,
        'fatigued': fatigued,
        'frightened': frightened,
        'sickened': sickened,
        'stunned': stunned,
        'slowed': slowed,
        'clumsy': clumsy,
        'enfeebled': enfeebled,
        'drained': drained,
      };

  factory ConditionTrackers.fromMap(Map<String, dynamic> m) => ConditionTrackers(
        heroPoints: m['heroPoints'] as int? ?? 1,
        maxHeroPoints: m['maxHeroPoints'] as int? ?? 1,
        dying: m['dying'] as int? ?? 0,
        wounded: m['wounded'] as int? ?? 0,
        doomed: m['doomed'] as int? ?? 0,
        fatigued: m['fatigued'] as int? ?? 0,
        frightened: m['frightened'] as int? ?? 0,
        sickened: m['sickened'] as int? ?? 0,
        stunned: m['stunned'] as int? ?? 0,
        slowed: m['slowed'] as int? ?? 0,
        clumsy: m['clumsy'] as int? ?? 0,
        enfeebled: m['enfeebled'] as int? ?? 0,
        drained: m['drained'] as int? ?? 0,
      );

  String toJson() => jsonEncode(toMap());
  factory ConditionTrackers.fromJson(String s) => ConditionTrackers.fromMap(jsonDecode(s) as Map<String, dynamic>);
}

/// Full PF2e character model.
class Character {
  final int? id;
  final String name;
  final String ancestry;
  final String heritage;
  final String background;
  final String characterClass;
  final String subclass; // archetype / specialization
  final int level;
  final String deity;
  final String alignment;
  final String size; // Tiny, Small, Medium, Large
  final String gender;
  final int age;
  final String eyes;
  final String hair;
  final String height;
  final String weight;
  final String languages;
  final String senses;
  final String speed; // base speed
  final String? portraitPath; // local file path to character portrait

  final AbilityScores abilities;
  final Proficiencies proficiencies;
  final List<Feat> feats;
  final Spellcasting spellcasting;
  final Equipment equipment;
  final DerivedStats derived;
  final ConditionTrackers conditions;
  final String notes; // bio, backstory, appearance

  Character({
    this.id,
    required this.name,
    this.ancestry = 'Human',
    this.heritage = '',
    this.background = '',
    this.characterClass = 'Fighter',
    this.subclass = '',
    this.level = 1,
    this.deity = '',
    this.alignment = 'N',
    this.size = 'Medium',
    this.gender = '',
    this.age = 0,
    this.eyes = '',
    this.hair = '',
    this.height = '',
    this.weight = '',
    this.languages = 'Common',
    this.senses = '',
    this.speed = '25',
    this.portraitPath,
    AbilityScores? abilities,
    Proficiencies? proficiencies,
    List<Feat>? feats,
    Spellcasting? spellcasting,
    Equipment? equipment,
    DerivedStats? derived,
    ConditionTrackers? conditions,
    this.notes = '',
  })  : abilities = abilities ?? const AbilityScores(),
        proficiencies = proficiencies ?? const Proficiencies(),
        feats = feats ?? const [],
        spellcasting = spellcasting ?? Spellcasting(),
        equipment = equipment ?? const Equipment(),
        derived = derived ?? const DerivedStats(),
        conditions = conditions ?? const ConditionTrackers();

  Character copyWith({
    int? id,
    String? name,
    String? ancestry,
    String? heritage,
    String? background,
    String? characterClass,
    String? subclass,
    int? level,
    String? deity,
    String? alignment,
    String? size,
    String? gender,
    int? age,
    String? eyes,
    String? hair,
    String? height,
    String? weight,
    String? languages,
    String? senses,
    String? speed,
    String? portraitPath,
    AbilityScores? abilities,
    Proficiencies? proficiencies,
    List<Feat>? feats,
    Spellcasting? spellcasting,
    Equipment? equipment,
    DerivedStats? derived,
    ConditionTrackers? conditions,
    String? notes,
  }) {
    return Character(
      id: id ?? this.id,
      name: name ?? this.name,
      ancestry: ancestry ?? this.ancestry,
      heritage: heritage ?? this.heritage,
      background: background ?? this.background,
      characterClass: characterClass ?? this.characterClass,
      subclass: subclass ?? this.subclass,
      level: level ?? this.level,
      deity: deity ?? this.deity,
      alignment: alignment ?? this.alignment,
      size: size ?? this.size,
      gender: gender ?? this.gender,
      age: age ?? this.age,
      eyes: eyes ?? this.eyes,
      hair: hair ?? this.hair,
      height: height ?? this.height,
      weight: weight ?? this.weight,
      languages: languages ?? this.languages,
      senses: senses ?? this.senses,
      speed: speed ?? this.speed,
      portraitPath: portraitPath ?? this.portraitPath,
      abilities: abilities ?? this.abilities,
      proficiencies: proficiencies ?? this.proficiencies,
      feats: feats ?? this.feats,
      spellcasting: spellcasting ?? this.spellcasting,
      equipment: equipment ?? this.equipment,
      derived: derived ?? this.derived,
      conditions: conditions ?? this.conditions,
      notes: notes ?? this.notes,
    );
  }

  Map<String, Object?> toMap() => {
        if (id != null) 'id': id,
        'name': name,
        'ancestry': ancestry,
        'heritage': heritage,
        'background': background,
        'character_class': characterClass,
        'subclass': subclass,
        'level': level,
        'deity': deity,
        'alignment': alignment,
        'size': size,
        'gender': gender,
        'age': age,
        'eyes': eyes,
        'hair': hair,
        'height': height,
        'weight': weight,
        'languages': languages,
        'senses': senses,
        'speed': speed,
        'portrait_path': portraitPath,
        'abilities': abilities.toJson(),
        'proficiencies': proficiencies.toJson(),
        'feats': jsonEncode(feats.map((f) => f.toMap()).toList()),
        'spellcasting': spellcasting.toJson(),
        'equipment': equipment.toJson(),
        'derived': derived.toJson(),
        'conditions': conditions.toJson(),
        'notes': notes,
      };

  factory Character.fromMap(Map<String, Object?> m) {
    final abilitiesJson = m['abilities'] as String? ?? '{}';
    final proficienciesJson = m['proficiencies'] as String? ?? '{}';
    final featsJson = m['feats'] as String? ?? '[]';
    final spellcastingJson = m['spellcasting'] as String? ?? '{}';
    final equipmentJson = m['equipment'] as String? ?? '{}';
    final derivedJson = m['derived'] as String? ?? '{}';
    final conditionsJson = m['conditions'] as String? ?? '{}';

    return Character(
      id: m['id'] as int?,
      name: m['name'] as String? ?? '',
      ancestry: m['ancestry'] as String? ?? '',
      heritage: m['heritage'] as String? ?? '',
      background: m['background'] as String? ?? '',
      characterClass: m['character_class'] as String? ?? '',
      subclass: m['subclass'] as String? ?? '',
      level: (m['level'] as int?) ?? 1,
      deity: m['deity'] as String? ?? '',
      alignment: m['alignment'] as String? ?? '',
      size: m['size'] as String? ?? '',
      gender: m['gender'] as String? ?? '',
      age: (m['age'] as int?) ?? 0,
      eyes: m['eyes'] as String? ?? '',
      hair: m['hair'] as String? ?? '',
      height: m['height'] as String? ?? '',
      weight: m['weight'] as String? ?? '',
      languages: m['languages'] as String? ?? '',
      senses: m['senses'] as String? ?? '',
      speed: m['speed'] as String? ?? '',
      abilities: AbilityScores.fromJson(abilitiesJson),
      proficiencies: Proficiencies.fromJson(proficienciesJson),
      feats: (jsonDecode(featsJson) as List<dynamic>)
          .map((e) => Feat.fromMap(e as Map<String, dynamic>))
          .toList(),
      spellcasting: Spellcasting.fromJson(spellcastingJson),
      equipment: Equipment.fromJson(equipmentJson),
      derived: DerivedStats.fromJson(derivedJson),
      conditions: ConditionTrackers.fromJson(conditionsJson),
      notes: m['notes'] as String? ?? '',
    );
  }

  /// Recalculates all derived stats from the character's other fields.
  Character recalculateDerived() {
    // Ancestry HP
    int ancestryHp = 8;
    switch (ancestry.toLowerCase()) {
      case 'human': ancestryHp = 8; break;
      case 'elf': ancestryHp = 6; break;
      case 'dwarf': ancestryHp = 10; break;
      case 'goblin': ancestryHp = 6; break;
      case 'halfling': ancestryHp = 6; break;
      case 'gnome': ancestryHp = 8; break;
      case 'orc': ancestryHp = 10; break;
      default: ancestryHp = 8;
    }

    // Class HP
    int classHp = 8;
    switch (characterClass.toLowerCase()) {
      case 'barbarian': classHp = 12; break;
      case 'fighter': classHp = 10; break;
      case 'champion': classHp = 10; break;
      case 'ranger': classHp = 10; break;
      case 'rogue': classHp = 8; break;
      case 'monk': classHp = 10; break;
      case 'wizard': classHp = 6; break;
      case 'sorcerer': classHp = 6; break;
      case 'cleric': classHp = 8; break;
      case 'druid': classHp = 8; break;
      case 'bard': classHp = 8; break;
      case 'witch': classHp = 8; break;
      case 'oracle': classHp = 8; break;
      case 'summoner': classHp = 8; break;
      case 'magus': classHp = 8; break;
      case 'inventor': classHp = 8; break;
      case 'psychic': classHp = 6; break;
      case 'thaumaturge': classHp = 8; break;
      case 'gunslinger': classHp = 8; break;
      case 'kineticist': classHp = 8; break;
      case 'animist': classHp = 8; break;
      default: classHp = 8;
    }

    final int hpPerLevel = (classHp + abilities.conMod).clamp(1, 999);
    final int maxHp = ancestryHp + classHp + abilities.conMod + (level - 1) * hpPerLevel;

    int profBonus(Proficiency p) {
      switch (p) {
        case Proficiency.untrained: return 0;
        case Proficiency.trained: return level + 2;
        case Proficiency.expert: return level + 4;
        case Proficiency.master: return level + 6;
        case Proficiency.legendary: return level + 8;
      }
    }

    int armorAc = equipment.armor.acBonus;
    int shieldAc = equipment.shield?.acBonus ?? 0;
    final Proficiency armorProf = switch (equipment.armor.category) {
      'light' => proficiencies.defenses.lightArmor,
      'medium' => proficiencies.defenses.mediumArmor,
      'heavy' => proficiencies.defenses.heavyArmor,
      _ => proficiencies.defenses.unarmored,
    };
    final int effectiveDexMod = abilities.dexMod.clamp(-5, equipment.armor.dexCap);
    int ac = 10 + effectiveDexMod + profBonus(armorProf) + armorAc + shieldAc;

    // Saves
    final int fortitude = abilities.conMod + profBonus(proficiencies.defenses.fortitude);
    final int reflex = abilities.dexMod + profBonus(proficiencies.defenses.reflex);
    final int will = abilities.wisMod + profBonus(proficiencies.defenses.will);
    final int perception = abilities.wisMod + profBonus(proficiencies.defenses.perception);

    // Class DC key ability mod
    int keyAbilityMod(AbilityScores a) {
      // Default to highest mental stat for spellcasters, Str for martials
      final martial = ['barbarian', 'fighter', 'champion', 'ranger', 'rogue', 'monk', 'gunslinger', 'fighter', 'inventor', 'thief'];
      final isMartial = martial.any((c) => characterClass.toLowerCase().contains(c));
      if (isMartial) return a.strMod;
      return [a.intMod, a.wisMod, a.chaMod].reduce((a, b) => a > b ? a : b);
    }

    // Class DC
    final int classDC = 10 + profBonus(proficiencies.classProfs.classDC) + keyAbilityMod(abilities);

    // Spell DC / Attack
    final int spellcastMod = spellcasting.spellcastingMod(abilities);
    final int spellDC = 10 + profBonus(proficiencies.classProfs.spellDC) + spellcastMod;
    final int spellAttack = profBonus(proficiencies.classProfs.spellAttack) + spellcastMod;

    // Speed
    int speed = 25;
    switch (ancestry.toLowerCase()) {
      case 'elf': speed = 30; break;
      case 'dwarf': speed = 20; break;
      case 'goblin': speed = 25; break;
      case 'halfling': speed = 25; break;
      case 'gnome': speed = 25; break;
      case 'orc': speed = 25; break;
      default: speed = 25;
    }
    speed -= equipment.armor.speedPenalty;

    // Bulk limit
    final int bulkLimit = 5 + abilities.strMod;

    // Initiative
final int initiative = perception; // Usually perception, sometimes stealth

  return copyWith(
    derived: DerivedStats(
      hp: derived.hp,
      maxHp: maxHp,
      ac: ac,
      fortitude: fortitude,
      reflex: reflex,
      will: will,
      perception: perception,
      classDC: classDC,
      spellDC: spellDC,
      spellAttack: spellAttack,
      speed: speed,
      bulkLimit: bulkLimit,
      initiative: initiative,
    ),
  );
}
}