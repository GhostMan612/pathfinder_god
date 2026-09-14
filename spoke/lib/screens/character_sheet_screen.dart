// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

import 'package:flutter/material.dart';

import '../api/hub_client.dart';
import '../models/character.dart';
import '../storage/character_store.dart';
import '../theme/app_theme.dart';

/// Create/edit a character with full PF2e fields.
class CharacterSheetScreen extends StatefulWidget {
  final HubClient client;
  final CharacterStore store;
  final Character? initial;
  const CharacterSheetScreen({
    super.key,
    required this.client,
    required this.store,
    this.initial,
  });

  @override
  State<CharacterSheetScreen> createState() => _CharacterSheetScreenState();
}

class _CharacterSheetScreenState extends State<CharacterSheetScreen>
    with SingleTickerProviderStateMixin {
  late final TabController _tabController;

  // Basic info
  final _name = TextEditingController();
  final _ancestry = TextEditingController();
  final _heritage = TextEditingController();
  final _background = TextEditingController();
  final _class = TextEditingController();
  final _subclass = TextEditingController();
  final _level = TextEditingController();
  final _deity = TextEditingController();
  final _alignment = TextEditingController();
  final _size = TextEditingController();
  final _gender = TextEditingController();
  final _age = TextEditingController();
  final _eyes = TextEditingController();
  final _hair = TextEditingController();
  final _height = TextEditingController();
  final _weight = TextEditingController();
  final _languages = TextEditingController();
  final _senses = TextEditingController();
  final _speed = TextEditingController();

  // Abilities
  final _str = TextEditingController(text: '10');
  final _dex = TextEditingController(text: '10');
  final _con = TextEditingController(text: '10');
  final _int = TextEditingController(text: '10');
  final _wis = TextEditingController(text: '10');
  final _cha = TextEditingController(text: '10');

  // Feats, spells, equipment, notes
  final _notes = TextEditingController();
  bool _generating = false;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 9, vsync: this);
    final c = widget.initial;
    if (c != null) {
      _name.text = c.name;
      _ancestry.text = c.ancestry;
      _heritage.text = c.heritage;
      _background.text = c.background;
      _class.text = c.characterClass;
      _subclass.text = c.subclass;
      _level.text = c.level.toString();
      _deity.text = c.deity;
      _alignment.text = c.alignment;
      _size.text = c.size;
      _gender.text = c.gender;
      _age.text = c.age.toString();
      _eyes.text = c.eyes;
      _hair.text = c.hair;
      _height.text = c.height;
      _weight.text = c.weight;
      _languages.text = c.languages;
      _senses.text = c.senses;
      _speed.text = c.speed;
      _str.text = c.abilities.str.toString();
      _dex.text = c.abilities.dex.toString();
      _con.text = c.abilities.con.toString();
      _int.text = c.abilities.int_.toString();
      _wis.text = c.abilities.wis.toString();
      _cha.text = c.abilities.cha.toString();
      _notes.text = c.notes;
    }
  }

  @override
  void dispose() {
    _tabController.dispose();
    for (final c in [
      _name, _ancestry, _heritage, _background, _class, _subclass,
      _level, _deity, _alignment, _size, _gender, _age,
      _eyes, _hair, _height, _weight, _languages, _senses, _speed,
      _str, _dex, _con, _int, _wis, _cha, _notes,
    ]) {
      c.dispose();
    }
    _tabController.dispose();
    super.dispose();
  }

  Character _current() => Character(
        id: widget.initial?.id,
        name: _name.text.trim().isEmpty ? 'Unnamed Hero' : _name.text.trim(),
        ancestry: _ancestry.text.trim(),
        heritage: _heritage.text.trim(),
        background: _background.text.trim(),
        characterClass: _class.text.trim(),
        subclass: _subclass.text.trim(),
        level: int.tryParse(_level.text) ?? 1,
        deity: _deity.text.trim(),
        alignment: _alignment.text.trim(),
        size: _size.text.trim(),
        gender: _gender.text.trim(),
        age: int.tryParse(_age.text) ?? 0,
        eyes: _eyes.text.trim(),
        hair: _hair.text.trim(),
        height: _height.text.trim(),
        weight: _weight.text.trim(),
        languages: _languages.text.trim(),
        senses: _senses.text.trim(),
        speed: _speed.text.trim(),
        abilities: AbilityScores(
          str: int.tryParse(_str.text) ?? 10,
          dex: int.tryParse(_dex.text) ?? 10,
          con: int.tryParse(_con.text) ?? 10,
          int_: int.tryParse(_int.text) ?? 10,
          wis: int.tryParse(_wis.text) ?? 10,
          cha: int.tryParse(_cha.text) ?? 10,
        ),
        proficiencies: Proficiencies(),
        feats: const [],
        spellcasting: Spellcasting(),
        equipment: Equipment(),
        derived: DerivedStats(),
        conditions: ConditionTrackers(),
        notes: _notes.text.trim(),
      ).recalculateDerived();

  Future<void> _save() async {
    await widget.store.upsert(_current().recalculateDerived());
    if (mounted) Navigator.of(context).pop();
  }

  Future<void> _delete() async {
    final id = widget.initial?.id;
    if (id != null) await widget.store.delete(id);
    if (mounted) Navigator.of(context).pop();
  }

  Future<void> _forgeWithGod() async {
    setState(() => _generating = true);
    final descriptor = [
      'Level $_level',
      if (_ancestry.text.trim().isNotEmpty) _ancestry.text.trim(),
      if (_class.text.trim().isNotEmpty) _class.text.trim(),
      if (_background.text.trim().isNotEmpty) 'background: ${_background.text.trim()}',
      if (_name.text.trim().isNotEmpty) 'named ${_name.text.trim()}',
    ].join(', ');

    try {
      final resp = await widget.client.generate('character', descriptor);
      if (!mounted) return;
      setState(() {
        _notes.text = resp.answer;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Forged via ${resp.backend}. Review & Save.')),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text("Couldn't reach the God: $e")),
      );
    } finally {
      if (mounted) setState(() => _generating = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.initial == null ? 'New Hero' : 'Edit Hero'),
        bottom: TabBar(
          controller: _tabController,
          isScrollable: true,
          tabs: const [
            Tab(text: 'Basics'),
            Tab(text: 'Abilities'),
            Tab(text: 'Proficiencies'),
            Tab(text: 'Feats'),
            Tab(text: 'Spells'),
            Tab(text: 'Equipment'),
            Tab(text: 'Derived'),
            Tab(text: 'Conditions'),
            Tab(text: 'Notes'),
          ],
        ),
        actions: [
          if (widget.initial != null)
            IconButton(icon: const Icon(Icons.delete_outline), onPressed: _delete),
          IconButton(icon: const Icon(Icons.save), onPressed: _save),
        ],
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          _buildBasicsTab(),
          _buildAbilitiesTab(),
          _buildProficienciesTab(),
          _buildFeatsTab(),
          _buildSpellsTab(),
          _buildEquipmentTab(),
          _buildDerivedTab(),
          _buildConditionsTab(),
          _buildNotesTab(),
        ],
      ),
    );
  }

  Widget _buildBasicsTab() => SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            _field(_name, 'Name'),
            _field(_ancestry, 'Ancestry'),
            _field(_heritage, 'Heritage'),
            _field(_background, 'Background'),
            _field(_class, 'Class'),
            _field(_subclass, 'Subclass / Archetype'),
            _field(_level, 'Level', keyboard: TextInputType.number),
            _field(_deity, 'Deity'),
            _field(_alignment, 'Alignment'),
            _field(_size, 'Size'),
            _field(_gender, 'Gender'),
            _field(_age, 'Age', keyboard: TextInputType.number),
            _field(_eyes, 'Eyes'),
            _field(_hair, 'Hair'),
            _field(_height, 'Height'),
            _field(_weight, 'Weight'),
            _field(_languages, 'Languages'),
            _field(_senses, 'Senses'),
            _field(_speed, 'Speed', keyboard: TextInputType.number),
          ],
        ),
      );

  Widget _buildAbilitiesTab() => SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            _abilityRow('STR', _str, _strMod),
            _abilityRow('DEX', _dex, _dexMod),
            _abilityRow('CON', _con, _conMod),
            _abilityRow('INT', _int, _intMod),
            _abilityRow('WIS', _wis, _wisMod),
            _abilityRow('CHA', _cha, _chaMod),
            const SizedBox(height: 16),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Key Ability Modifiers',
                        style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: 8),
                    _modRow('STR Mod', _strMod),
                    _modRow('DEX Mod', _dexMod),
                    _modRow('CON Mod', _conMod),
                    _modRow('INT Mod', _intMod),
                    _modRow('WIS Mod', _wisMod),
                    _modRow('CHA Mod', _chaMod),
                  ],
                ),
              ),
            ),
          ],
        ),
      );

  int _modFrom(String text) => ((int.tryParse(text) ?? 10) - 10) ~/ 2;
  int get _strMod => _modFrom(_str.text);
  int get _dexMod => _modFrom(_dex.text);
  int get _conMod => _modFrom(_con.text);
  int get _intMod => _modFrom(_int.text);
  int get _wisMod => _modFrom(_wis.text);
  int get _chaMod => _modFrom(_cha.text);

  Widget _abilityRow(String label, TextEditingController c, int mod) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: Row(
          children: [
            SizedBox(
              width: 60,
              child: Text(label,
                  style: TextStyle(fontWeight: FontWeight.bold, color: PathfinderTheme.gold)),
            ),
            Expanded(
              child: TextField(
                controller: c,
                keyboardType: TextInputType.number,
                decoration: InputDecoration(
                  labelText: 'Score',
                  border: const OutlineInputBorder(),
                  isDense: true,
                  suffixText: 'mod: ${mod >= 0 ? "+" : ""}$mod',
                ),
              ),
            ),
          ],
        ),
      );

  Widget _modRow(String label, int mod) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(label),
            Text('${mod >= 0 ? "+" : ""}$mod',
                style: TextStyle(fontWeight: FontWeight.bold, color: mod >= 0 ? Colors.green : Colors.red)),
          ],
        ),
      );

  Widget _buildProficienciesTab() => SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _sectionHeader('Skills'),
            _proficiencyGrid(SkillProficiencies().toMap().keys.toList(), 
                (s) => _skillField(s)),
            const SizedBox(height: 16),
            _sectionHeader('Defenses'),
            _proficiencyGrid(
                ['Fortitude', 'Reflex', 'Will', 'Perception',
                 'Unarmored', 'Light Armor', 'Medium Armor', 'Heavy Armor',
                 'Simple Weapons', 'Martial Weapons', 'Advanced Weapons', 'Unarmed'],
                (s) => _profField(s)),
            const SizedBox(height: 16),
            _sectionHeader('Class'),
            _proficiencyGrid(['Class DC', 'Spell DC', 'Spell Attack'], (s) => _profField(s)),
          ],
        ),
      );

  Widget _sectionHeader(String title) => Padding(
        padding: const EdgeInsets.only(top: 16, bottom: 8),
        child: Text(title,
            style: Theme.of(context).textTheme.titleMedium?.copyWith(color: PathfinderTheme.gold)),
      );

  Widget _proficiencyGrid(List<String> items, Widget Function(String) builder) => Wrap(
        spacing: 12,
        runSpacing: 8,
        children: items.map(builder).toList(),
      );

  Widget _skillField(String skill) => _profDropdown(skill, SkillProficiencies().toMap()[skill]?.toString() ?? '0');

  Widget _profDropdown(String label, String initial) => SizedBox(
        width: 160,
        child: DropdownButtonFormField<String>(
          initialValue: initial,
          items: Proficiency.values.map((p) => DropdownMenuItem(
                value: p.index.toString(),
                child: Text('${p.name} (${p.index})'),
              )).toList(),
          onChanged: (_) {},
          decoration: InputDecoration(labelText: label, isDense: true, border: const OutlineInputBorder()),
        ),
      );

  Widget _profField(String label) => SizedBox(
        width: 160,
        child: DropdownButtonFormField<String>(
          initialValue: '0',
          items: Proficiency.values.map((p) => DropdownMenuItem(
                value: p.index.toString(),
                child: Text(p.name),
              )).toList(),
          onChanged: (_) {},
          decoration: InputDecoration(labelText: label, isDense: true, border: const OutlineInputBorder()),
        ),
      );

  Widget _buildFeatsTab() => SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _sectionHeader('Feats'),
            const Text('Feat editing UI - add ancestry, class, skill, general, background feats'),
            const SizedBox(height: 16),
            ElevatedButton.icon(
              icon: const Icon(Icons.add),
              label: const Text('Add Feat'),
              onPressed: () {},
            ),
          ],
        ),
      );

  Widget _buildSpellsTab() => SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _sectionHeader('Spellcasting'),
            _field(TextEditingController(text: 'arcane'), 'Tradition'),
            _field(TextEditingController(text: 'cha'), 'Key Ability'),
            _field(TextEditingController(text: 'false'), 'Prepared? (true/false)'),
            const SizedBox(height: 16),
            _sectionHeader('Spell Slots per Level'),
            Wrap(
              spacing: 8,
              children: List.generate(11, (i) => _slotField(i == 0 ? 'Cantrip' : 'Level $i')),
            ),
            const SizedBox(height: 16),
            _sectionHeader('Focus Pool'),
            Row(
              children: [
                Expanded(child: _field(TextEditingController(text: '0'), 'Current Focus')),
                const SizedBox(width: 8),
                Expanded(child: _field(TextEditingController(text: '1'), 'Max Focus')),
              ],
            ),
            const SizedBox(height: 16),
            _sectionHeader('Repertoire / Known Spells'),
            ElevatedButton.icon(
              icon: const Icon(Icons.add),
              label: const Text('Add Spell'),
              onPressed: () {},
            ),
          ],
        ),
      );

  Widget _slotField(String label) => SizedBox(
        width: 70,
        child: TextField(
          decoration: InputDecoration(labelText: label, isDense: true, border: const OutlineInputBorder()),
          keyboardType: TextInputType.number,
        ),
      );

  Widget _buildEquipmentTab() => SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _sectionHeader('Weapons'),
            ElevatedButton.icon(icon: const Icon(Icons.add), label: const Text('Add Weapon'), onPressed: () {}),
            const SizedBox(height: 16),
            _sectionHeader('Armor'),
            _field(TextEditingController(text: 'Unarmored'), 'Armor Name'),
            Row(children: [
              Expanded(child: _field(TextEditingController(text: '0'), 'AC Bonus')),
              const SizedBox(width: 8),
              Expanded(child: _field(TextEditingController(text: '5'), 'Dex Cap')),
              const SizedBox(width: 8),
              Expanded(child: _field(TextEditingController(text: '0'), 'Check Penalty')),
            ]),
            const SizedBox(height: 16),
            _sectionHeader('Shield'),
            _field(TextEditingController(text: ''), 'Shield Name'),
            const SizedBox(height: 16),
            _sectionHeader('Currency'),
            Row(children: [
              Expanded(child: _field(TextEditingController(text: '0'), 'CP')),
              const SizedBox(width: 8),
              Expanded(child: _field(TextEditingController(text: '0'), 'SP')),
              const SizedBox(width: 8),
              Expanded(child: _field(TextEditingController(text: '0'), 'GP')),
              const SizedBox(width: 8),
              Expanded(child: _field(TextEditingController(text: '0'), 'PP')),
            ]),
          ],
        ),
      );

  Widget _buildDerivedTab() {
    final c = _current().recalculateDerived();
    final d = c.derived;
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _sectionHeader('Combat Stats'),
          _statGrid([
            ['HP', '${d.hp} / ${d.maxHp}'],
            ['AC', d.ac.toString()],
            ['Fortitude', '${d.fortitude >= 0 ? "+" : ""}${d.fortitude}'],
            ['Reflex', '${d.reflex >= 0 ? "+" : ""}${d.reflex}'],
            ['Will', '${d.will >= 0 ? "+" : ""}${d.will}'],
            ['Perception', '${d.perception >= 0 ? "+" : ""}${d.perception}'],
            ['Class DC', d.classDC.toString()],
            ['Spell DC', d.spellDC.toString()],
            ['Spell Attack', '${d.spellAttack >= 0 ? "+" : ""}${d.spellAttack}'],
            ['Speed', '${d.speed} ft'],
            ['Initiative', '${d.initiative >= 0 ? "+" : ""}${d.initiative}'],
            ['Bulk Limit', '${d.bulkLimit}'],
          ]),
        ],
      ),
    );
  }

  Widget _buildConditionsTab() => SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _sectionHeader('Hero Points'),
            Row(children: [
              Expanded(child: _field(TextEditingController(text: '1'), 'Current')),
              const SizedBox(width: 8),
              Expanded(child: _field(TextEditingController(text: '1'), 'Max')),
            ]),
            const SizedBox(height: 16),
            _sectionHeader('Conditions'),
            Wrap(
              spacing: 12,
              runSpacing: 8,
              children: [
                _condField('Dying', '0'),
                _condField('Wounded', '0'),
                _condField('Doomed', '0'),
                _condField('Fatigued', '0'),
                _condField('Frightened', '0'),
                _condField('Sickened', '0'),
                _condField('Stunned', '0'),
                _condField('Slowed', '0'),
                _condField('Clumsy', '0'),
                _condField('Enfeebled', '0'),
                _condField('Drained', '0'),
              ],
            ),
          ],
        ),
      );

  Widget _condField(String label, String initial) => SizedBox(
        width: 100,
        child: TextField(
          decoration: InputDecoration(labelText: label, isDense: true, border: const OutlineInputBorder()),
          keyboardType: TextInputType.number,
        ),
      );

  Widget _buildNotesTab() => SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _sectionHeader('Bio, Backstory, Gear & Abilities'),
            const SizedBox(height: 8),
            FilledButton.icon(
              icon: _generating
                  ? const SizedBox(height: 18, width: 18, child: CircularProgressIndicator(strokeWidth: 2))
                  : const Icon(Icons.auto_fix_high),
              label: Text(_generating ? 'Forging…' : 'Forge full bio with the God'),
              onPressed: _generating ? null : _forgeWithGod,
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _notes,
              minLines: 10,
              maxLines: 40,
              decoration: const InputDecoration(
                labelText: 'Bio, backstory, gear & abilities',
                alignLabelWithHint: true,
                border: OutlineInputBorder(),
              ),
            ),
          ],
        ),
      );

  Widget _statGrid(List<List<String>> rows) => Column(
        children: [
          for (int i = 0; i < rows.length; i += 2)
            Row(
              children: [
                for (int j = 0; j < 2; j++)
                  if (i + j < rows.length)
                    Expanded(
                      child: Card(
                        margin: const EdgeInsets.all(4),
                        child: Padding(
                          padding: const EdgeInsets.all(12),
                          child: Column(
                            children: [
                              Text(rows[i + j][0],
                                  style: TextStyle(fontSize: 12, color: PathfinderTheme.ink)),
                              const SizedBox(height: 4),
                              Text(rows[i + j][1],
                                  style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold,
                                      color: PathfinderTheme.gold)),
                            ],
                          ),
                        ),
                      ),
                    ),
              ],
            ),
        ],
      );

  Widget _field(TextEditingController c, String label,
      {TextInputType keyboard = TextInputType.text}) => Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: TextField(
          controller: c,
          keyboardType: keyboard,
          decoration: InputDecoration(labelText: label, border: const OutlineInputBorder(), isDense: true),
        ),
      );
}