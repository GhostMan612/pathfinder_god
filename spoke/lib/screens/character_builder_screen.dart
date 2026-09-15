// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

import 'package:flutter/material.dart';

import '../api/hub_client.dart';
import '../models/character.dart';
import '../storage/character_store.dart';
import '../theme/app_theme.dart';
import 'character_sheet_screen.dart';

/// Character Builder — LLM prompt → Rules Lawyer validation → local save.
class CharacterBuilderScreen extends StatefulWidget {
  final HubClient client;
  final CharacterStore store;

  const CharacterBuilderScreen({
    super.key,
    required this.client,
    required this.store,
  });

  @override
  State<CharacterBuilderScreen> createState() => _CharacterBuilderScreenState();
}

class _CharacterBuilderScreenState extends State<CharacterBuilderScreen> {
  final _promptController = TextEditingController(
    text: 'Make me a level 4 Goblin Alchemist who throws bombs and hates fire',
  );
  final _examples = const [
    'Make me a level 4 Goblin Alchemist who throws bombs and hates fire',
    'Create a level 1 Human Fighter with a greatsword and heavy armor',
    'Build a level 3 Elf Wizard specializing in illusion magic',
    'Level 5 Dwarf Cleric of Torag, focused on healing and defense',
    'Level 2 Halfling Rogue thief with high stealth and thievery',
  ];

  bool _building = false;
  String? _error;
  List<String> _errors = [];

  @override
  void dispose() {
    _promptController.dispose();
    super.dispose();
  }

  Future<void> _build() async {
    final prompt = _promptController.text.trim();
    if (prompt.isEmpty) return;

    setState(() {
      _building = true;
      _error = null;
      _errors = [];
    });

    try {
      final result = await widget.client.buildCharacter(prompt);
      final valid = result['valid'] as bool? ?? false;

      if (!valid) {
        _errors = (result['errors'] as List<dynamic>?)
                ?.map((e) => e.toString())
                .toList() ??
            ['Unknown validation error'];
        setState(() {
          _building = false;
        });
        return;
      }

      final charMap = result['character'] as Map<String, dynamic>?;
      if (charMap == null) {
        setState(() {
          _building = false;
          _error = 'Valid but no character data returned';
        });
        return;
      }

      // Convert hub CharacterSheetModel -> Spoke Character
      final character = _mapToCharacter(charMap);
      await widget.store.upsertRaw(character);

      if (!mounted) return;

      // Navigate to the character sheet for the new character
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(
          builder: (_) => CharacterSheetScreen(
            client: widget.client,
            store: widget.store,
            initial: character,
          ),
        ),
      );
    } catch (e) {
      if (mounted) {
        setState(() {
          _building = false;
          _error = 'Build failed: $e';
        });
      }
    }
  }

  Character _mapToCharacter(Map<String, dynamic> hub) {
    // Hub CharacterSheetModel -> Spoke Character
    // Fields match closely; fill in defaults for Spoke-only fields
    final abilitiesMap = hub['abilities'] as Map<String, dynamic>? ?? {};
    final profsMap = hub['proficiencies'] as Map<String, dynamic>? ?? {};

    return Character(
      name: hub['name'] as String? ?? 'Unnamed Hero',
      ancestry: hub['ancestry'] as String? ?? 'Human',
      heritage: hub['heritage'] as String? ?? '',
      background: hub['background'] as String? ?? '',
      characterClass: hub['character_class'] as String? ?? 'Fighter',
      subclass: hub['subclass'] as String? ?? '',
      level: (hub['level'] as int?)?.clamp(1, 20) ?? 1,
      deity: hub['deity'] as String? ?? '',
      alignment: hub['alignment'] as String? ?? 'N',
      size: hub['size'] as String? ?? 'Medium',
      gender: hub['gender'] as String? ?? '',
      age: hub['age'] as int? ?? 0,
      eyes: hub['eyes'] as String? ?? '',
      hair: hub['hair'] as String? ?? '',
      height: hub['height'] as String? ?? '',
      weight: hub['weight'] as String? ?? '',
      languages: hub['languages'] as String? ?? 'Common',
      senses: hub['senses'] as String? ?? '',
      speed: hub['speed'] as String? ?? '25',
      abilities: AbilityScores.fromMap(abilitiesMap),
      proficiencies: Proficiencies.fromMap(profsMap),
      feats: (hub['feats'] as List<dynamic>?)
              ?.map((e) => Feat.fromMap(e as Map<String, dynamic>))
              .toList() ??
          [],
      spellcasting: Spellcasting.fromJson(
        (hub['spellcasting'] as Map<String, dynamic>?)?.toString() ?? '{}',
      ),
      equipment: Equipment.fromJson(
        (hub['equipment'] as Map<String, dynamic>?)?.toString() ?? '{}',
      ),
      derived: DerivedStats.fromJson(
        (hub['derived'] as Map<String, dynamic>?)?.toString() ?? '{}',
      ),
      conditions: ConditionTrackers.fromJson(
        (hub['conditions'] as Map<String, dynamic>?)?.toString() ?? '{}',
      ),
      notes: hub['notes'] as String? ?? '',
    ).recalculateDerived();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Character Builder'),
        actions: [
          IconButton(
            icon: const Icon(Icons.auto_awesome),
            tooltip: 'Fill random example',
            onPressed: _building
                ? null
                : () {
                    final ex = _examples[
                        (DateTime.now().millisecondsSinceEpoch % _examples.length)];
                    _promptController.text = ex;
                  },
          ),
        ],
      ),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              'Describe the character you want. The God will forge a rules-legal PF2e character, '
              'validated by the Rules Lawyer, and save it to your vault.',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: Colors.grey[700],
                  ),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: _promptController,
              maxLines: 4,
              minLines: 3,
              enabled: !_building,
              decoration: InputDecoration(
                labelText: 'Prompt',
                hintText: 'e.g. "Level 4 Goblin Alchemist, bomber, hates fire"',
                border: const OutlineInputBorder(),
                alignLabelWithHint: true,
              ),
            ),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: _examples.map((ex) {
                return ActionChip(
                  label: Text(ex, style: const TextStyle(fontSize: 11)),
                  onPressed: _building
                      ? null
                      : () => _promptController.text = ex,
                );
              }).toList(),
            ),
            const SizedBox(height: 20),
            if (_error != null)
              Card(
                color: PathfinderTheme.crimson.withValues(alpha: 0.1),
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Text(
                    _error!,
                    style: TextStyle(color: PathfinderTheme.crimson, fontSize: 13),
                  ),
                ),
              ),
            if (_errors.isNotEmpty) ...[
              const SizedBox(height: 8),
              Card(
                color: PathfinderTheme.crimson.withValues(alpha: 0.1),
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Icon(Icons.gavel, color: PathfinderTheme.crimson, size: 18),
                          const SizedBox(width: 8),
                          Text(
                            'Rules Lawyer Rejected',
                            style: TextStyle(
                              color: PathfinderTheme.crimson,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      for (final err in _errors)
                        Padding(
                          padding: const EdgeInsets.only(bottom: 4),
                          child: Text('• $err',
                              style: TextStyle(
                                color: PathfinderTheme.crimson,
                                fontSize: 12,
                              )),
                        ),
                    ],
                  ),
                ),
              ),
            ],
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: _building ? null : _build,
              icon: _building
                  ? const SizedBox(
                      height: 20,
                      width: 20,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.auto_fix_high),
              label: Text(_building ? 'Forging…' : 'Forge Character'),
              style: FilledButton.styleFrom(
                padding: const EdgeInsets.symmetric(vertical: 16),
                backgroundColor: PathfinderTheme.gold,
                foregroundColor: PathfinderTheme.ink,
              ),
            ),
            const SizedBox(height: 16),
            Expanded(
              child: Center(
                child: Text(
                  'The Rules Lawyer validates every proficiency, DC, and feat prerequisite. '
                  'Only fully-legal characters reach your vault.',
                  textAlign: TextAlign.center,
                  style: TextStyle(fontSize: 12, color: Colors.grey[600]),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}