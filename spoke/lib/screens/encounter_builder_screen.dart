// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:provider/provider.dart';

import '../api/hub_client.dart';
import '../models/combatant.dart';
import '../models/encounter.dart';
import '../services/audio_service.dart';
import '../services/combat_store.dart';
import '../theme/app_theme.dart';
import '../widgets/rpg_panel.dart';
import 'combat_tracker_screen.dart';

/// Encounter Builder — PF2e XP budget + LLM selection → Combat Tracker.
class EncounterBuilderScreen extends StatefulWidget {
  final HubClient client;
  final CombatStore store;

  const EncounterBuilderScreen({
    super.key,
    required this.client,
    required this.store,
  });

  @override
  State<EncounterBuilderScreen> createState() => _EncounterBuilderScreenState();
}

class _EncounterBuilderScreenState extends State<EncounterBuilderScreen> {
  final _themeController = TextEditingController(text: 'Swamp ambush');
  final _partyLevelCtrl = TextEditingController(text: '4');
  final _partySizeCtrl = TextEditingController(text: '4');
  String _threat = 'moderate';
  bool _building = false;
  String? _error;
  GeneratedEncounter? _result;

  static const _threats = ['trivial', 'low', 'moderate', 'severe', 'extreme'];
  static const _threatLabels = {
    'trivial': 'Trivial (40 XP)',
    'low': 'Low (60 XP)',
    'moderate': 'Moderate (80 XP)',
    'severe': 'Severe (120 XP)',
    'extreme': 'Extreme (160 XP)',
  };

  @override
  void dispose() {
    _themeController.dispose();
    super.dispose();
  }

  Future<void> _generate() async {
    final partyLevel = int.tryParse(_partyLevelCtrl.text) ?? 1;
    final partySize = int.tryParse(_partySizeCtrl.text) ?? 4;
    final theme = _themeController.text.trim();

    if (theme.isEmpty) {
      setState(() => _error = 'Theme required');
      return;
    }
    if (partyLevel < 1 || partyLevel > 20) {
      setState(() => _error = 'Party level must be 1-20');
      return;
    }
    if (partySize < 1 || partySize > 10) {
      setState(() => _error = 'Party size must be 1-10');
      return;
    }

    setState(() {
      _building = true;
      _error = null;
      _result = null;
    });

    try {
      final result = await widget.client.generateEncounter(
        partyLevel: partyLevel,
        partySize: partySize,
        threat: _threat,
        theme: theme,
      );

      if (!mounted) return;

      final encounter = GeneratedEncounter.fromJson(result);
      setState(() {
        _building = false;
        _result = encounter;
      });
    } catch (e) {
      if (mounted) {
        setState(() {
          _building = false;
          _error = 'Generation failed: $e';
        });
      }
    }
  }

  Future<void> _deployToCombatTracker() async {
    if (_result == null) return;

    for (final m in _result!.monsters) {
      final hp = _extractHp(m.content);
      final ac = _extractAc(m.content);
      final init = 10 + m.level + (DateTime.now().millisecondsSinceEpoch % 6);

      for (var i = 0; i < m.count; i++) {
        final combatant = Combatant(
          id: 'enc_${m.name}_${DateTime.now().millisecondsSinceEpoch}_$i',
          name: m.count > 1 ? '${m.name} ${i + 1}' : m.name,
          isPc: false,
          initiative: init + i,
          currentHp: hp,
          maxHp: hp,
          ac: ac,
        );
        widget.store.addCombatant(combatant);
      }
    }

    if (!mounted) return;
    Navigator.pushReplacement(
      context,
      MaterialPageRoute(
        builder: (_) => CombatTrackerScreen(
          client: widget.client,
          store: widget.store,
        ),
      ),
    );
  }

  int _extractHp(String content) {
    final m = RegExp(r'HP\s*(\d+)', caseSensitive: false).firstMatch(content);
    return int.tryParse(m?.group(1) ?? '') ?? 20;
  }

  int _extractAc(String content) {
    final m = RegExp(r'AC\s*(\d+)', caseSensitive: false).firstMatch(content);
    return int.tryParse(m?.group(1) ?? '') ?? 15;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Encounter Builder'),
        actions: [
          if (_result != null)
            IconButton(
              icon: const Icon(Icons.refresh),
              tooltip: 'Clear',
              onPressed: () => setState(() => _result = null),
            ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (_result == null) ...[
              _buildForm(),
            ] else ...[
              _buildResult(),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildForm() {
    return RpgPanels.gothicStone.build(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            'Forge an Encounter',
            style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                  color: PathfinderTheme.gold,
                ),
          ),
          const SizedBox(height: 8),
          Text(
            'Set the party parameters and a theme. The God will calculate the exact XP budget and select a synergistic monster group.',
            style: TextStyle(color: Colors.grey[700]),
          ),
          const SizedBox(height: 20),
          _buildThreatSelector(),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _partyLevelCtrl,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(
                    labelText: 'Party Level',
                    border: OutlineInputBorder(),
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: TextField(
                  controller: _partySizeCtrl,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(
                    labelText: 'Party Size',
                    border: OutlineInputBorder(),
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          TextField(
            controller: _themeController,
            decoration: const InputDecoration(
              labelText: 'Theme',
              hintText: 'e.g., Undead swamp ambush, Cultist ritual, Goblin tribe',
              border: OutlineInputBorder(),
            ),
          ),
          if (_error != null) ...[
            const SizedBox(height: 12),
            Text(_error!, style: const TextStyle(color: PathfinderTheme.crimson)),
          ],
          const SizedBox(height: 20),
          FilledButton.icon(
            onPressed: _building ? null : _generate,
            icon: _building
                ? const SizedBox(
                    height: 20,
                    width: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.auto_fix_high),
            label: Text(_building ? 'Forging…' : 'Generate Encounter'),
            style: FilledButton.styleFrom(
              padding: const EdgeInsets.symmetric(vertical: 16),
              backgroundColor: PathfinderTheme.gold,
              foregroundColor: PathfinderTheme.ink,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildThreatSelector() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Threat Level',
          style: Theme.of(context).textTheme.titleMedium?.copyWith(
                color: PathfinderTheme.crimson,
              ),
        ),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: _threats.map((t) {
            final selected = _threat == t;
            return ChoiceChip(
              label: Text(_threatLabels[t]!),
              selected: selected,
              onSelected: (_) => setState(() => _threat = t),
              selectedColor: PathfinderTheme.gold.withValues(alpha: 0.3),
              labelStyle: TextStyle(
                color: selected ? PathfinderTheme.ink : Colors.grey[800],
                fontWeight: selected ? FontWeight.bold : FontWeight.normal,
              ),
            );
          }).toList(),
        ),
      ],
    );
  }

  Widget _buildResult() {
    final r = _result!;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        RpgPanels.gothicStone.build(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Icon(Icons.auto_fix_high, color: PathfinderTheme.gold, size: 28),
                  const SizedBox(width: 8),
                  Text(
                    'Encounter Forged',
                    style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                          color: PathfinderTheme.gold,
                        ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  _statChip(label: 'Target XP', value: '${r.targetXp}'),
                  const SizedBox(width: 8),
                  _statChip(label: 'Total XP', value: '${r.totalXp}'),
                  const SizedBox(width: 8),
                  _statChip(label: 'Monsters', value: '${r.monsterCount}'),
                ],
              ),
              const SizedBox(height: 8),
              Text(
                'Party: L${r.partyLevel} × ${r.partySize}  |  ${r.threat.toUpperCase()}  |  ${r.theme}',
                style: TextStyle(fontSize: 12, color: Colors.grey[700]),
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),
        ListView.separated(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          itemCount: r.monsters.length,
          separatorBuilder: (_, __) => const SizedBox(height: 8),
          itemBuilder: (_, i) {
            final m = r.monsters[i];
            return _MonsterCard(monster: m);
          },
        ),
        const SizedBox(height: 16),
        FilledButton.icon(
          onPressed: _deployToCombatTracker,
          icon: const Icon(Icons.auto_fix_high),
          label: const Text('Deploy to Combat Tracker'),
          style: FilledButton.styleFrom(
            padding: const EdgeInsets.symmetric(vertical: 16),
            backgroundColor: PathfinderTheme.crimson,
            foregroundColor: Colors.white,
          ),
        ),
        const SizedBox(height: 8),
        TextButton(
          onPressed: () => setState(() => _result = null),
          child: const Text('Generate Another'),
        ),
      ],
    );
  }

  Widget _statChip({required String label, required String value}) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 8),
        decoration: BoxDecoration(
          color: PathfinderTheme.gold.withValues(alpha: 0.15),
          border: Border.all(color: PathfinderTheme.gold),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Column(
          children: [
            Text(value, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
            Text(label, style: TextStyle(fontSize: 11, color: Colors.grey[700])),
          ],
        ),
      ),
    );
  }
}

class _MonsterCard extends StatefulWidget {
  final EncounterMonster monster;
  const _MonsterCard({super.key, required this.monster});

  @override
  State<_MonsterCard> createState() => _MonsterCardState();
}

class _MonsterCardState extends State<_MonsterCard> {
  bool _expanded = false;

  @override
  Widget build(BuildContext context) {
    final m = widget.monster;
    return RpgPanels.gothicStone.build(
      padding: const EdgeInsets.all(12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  m.name,
                  style: const TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                    color: PathfinderTheme.crimson,
                  ),
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                decoration: BoxDecoration(
                  color: PathfinderTheme.gold.withValues(alpha: 0.2),
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(
                  '${m.count} × Level ${m.level}  (${m.xpEach} XP each = ${m.totalXp} XP)',
                  style: const TextStyle(fontSize: 11, fontWeight: FontWeight.bold),
                ),
              ),
            ],
          ),
          if (m.sourceBook.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text(
                'Source: ${m.sourceBook}',
                style: TextStyle(fontSize: 11, color: Colors.grey[600]),
              ),
            ),
          const SizedBox(height: 8),
          InkWell(
            onTap: () => setState(() => _expanded = !_expanded),
            borderRadius: BorderRadius.circular(8),
            child: Row(
              children: [
                const Text('Stat Block', style: TextStyle(fontWeight: FontWeight.bold)),
                const SizedBox(width: 8),
                Icon(_expanded ? Icons.expand_less : Icons.expand_more, size: 20),
              ],
            ),
          ),
          if (_expanded) ...[
            const SizedBox(height: 8),
            Text(
              widget.monster.content,
              style: const TextStyle(fontSize: 12, height: 1.4),
            ),
          ],
        ],
      ),
    );
  }
}