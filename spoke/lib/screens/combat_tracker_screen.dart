// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:provider/provider.dart';

import '../api/hub_client.dart';
import '../models/combatant.dart';
import '../services/audio_service.dart';
import '../services/combat_store.dart';
import '../theme/app_theme.dart';
import '../widgets/rpg_panel.dart';

/// Combat Tracker — Live encounter management with deterministic resolution.
class CombatTrackerScreen extends StatefulWidget {
  final HubClient client;
  final CombatStore store;
  const CombatTrackerScreen({
    super.key,
    required this.client,
    required this.store,
  });

  @override
  State<CombatTrackerScreen> createState() => _CombatTrackerScreenState();
}

class _CombatTrackerScreenState extends State<CombatTrackerScreen> {
  final _nameController = TextEditingController();
  final _initController = TextEditingController(text: '10');
  final _hpController = TextEditingController(text: '20');
  final _maxHpController = TextEditingController(text: '20');
  final _acController = TextEditingController(text: '15');
  bool _isPc = false;
  String? _error;

  @override
  void dispose() {
    _nameController.dispose();
    _initController.dispose();
    _hpController.dispose();
    _maxHpController.dispose();
    _acController.dispose();
    super.dispose();
  }

  void _showAddCombatantDialog({Combatant? edit}) {
    if (edit != null) {
      _nameController.text = edit.name;
      _initController.text = edit.initiative.toString();
      _hpController.text = edit.currentHp.toString();
      _maxHpController.text = edit.maxHp.toString();
      _acController.text = edit.ac.toString();
      _isPc = edit.isPc;
    } else {
      _nameController.clear();
      _initController.text = '10';
      _hpController.text = '20';
      _maxHpController.text = '20';
      _acController.text = '15';
      _isPc = false;
    }
    _error = null;

    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        title: Text(edit == null ? 'Add Combatant' : 'Edit Combatant'),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: _nameController,
                decoration: const InputDecoration(labelText: 'Name'),
              ),
              Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _initController,
                      keyboardType: TextInputType.number,
                      decoration: const InputDecoration(labelText: 'Initiative'),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: TextField(
                      controller: _acController,
                      keyboardType: TextInputType.number,
                      decoration: const InputDecoration(labelText: 'AC'),
                    ),
                  ),
                ],
              ),
              Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _hpController,
                      keyboardType: TextInputType.number,
                      decoration: const InputDecoration(labelText: 'Current HP'),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: TextField(
                      controller: _maxHpController,
                      keyboardType: TextInputType.number,
                      decoration: const InputDecoration(labelText: 'Max HP'),
                    ),
                  ),
                ],
              ),
              SwitchListTile(
                title: const Text('Player Character'),
                value: _isPc,
                onChanged: (v) => setState(() => _isPc = v),
                dense: true,
              ),
              if (_error != null)
                Padding(
                  padding: const EdgeInsets.only(top: 8),
                  child: Text(_error!, style: const TextStyle(color: PathfinderTheme.crimson)),
                ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => _submitCombatant(edit),
            child: Text(edit == null ? 'Add' : 'Save'),
          ),
        ],
      ),
    );
  }

  void _submitCombatant(Combatant? edit) {
    final name = _nameController.text.trim();
    final initiative = int.tryParse(_initController.text) ?? 0;
    final currentHp = int.tryParse(_hpController.text) ?? 0;
    final maxHp = int.tryParse(_maxHpController.text) ?? 0;
    final ac = int.tryParse(_acController.text) ?? 0;

    if (name.isEmpty) {
      setState(() => _error = 'Name required');
      return;
    }
    if (maxHp <= 0) {
      setState(() => _error = 'Max HP must be > 0');
      return;
    }
    if (ac < 0) {
      setState(() => _error = 'AC must be >= 0');
      return;
    }

    final combatant = Combatant(
      id: edit?.id ?? 'combatant_${DateTime.now().millisecondsSinceEpoch}',
      name: name,
      isPc: _isPc,
      initiative: initiative,
      currentHp: currentHp.clamp(0, maxHp),
      maxHp: maxHp,
      ac: ac,
    );

    if (edit != null) {
      final idx = widget.store.combatants.indexWhere((c) => c.id == edit.id);
      if (idx >= 0) {
        final c = widget.store.combatants[idx];
        final updated = c.copyWith(
          name: name,
          initiative: initiative,
          currentHp: currentHp.clamp(0, maxHp),
          maxHp: maxHp,
          ac: ac,
        );
        widget.store.combatants[idx] = updated;
      }
    } else {
      widget.store.addCombatant(combatant);
    }
    widget.store.notifyListeners();
    Navigator.pop(context);
  }

  Future<void> _resolveStrike(Combatant target, {required int attackRoll, required int damageRoll}) async {
    final result = await widget.client.resolveStrike(
      attackRoll: attackRoll,
      targetAc: target.ac,
      damageRoll: damageRoll,
      targetHp: target.currentHp,
      targetTempHp: target.tempHp,
    );

    final outcome = result['outcome'] as String;
    final damage = result['damage_dealt'] as int;
    final newHp = result['new_hp'] as int;
    final newTempHp = result['new_temp_hp'] as int;
    final notes = result['notes'] as String;

    widget.store.combatants[
        widget.store.combatants.indexWhere((c) => c.id == target.id)
    ] = target.copyWith(currentHp: newHp, tempHp: newTempHp);

    if (!mounted) return;

    final isCrit = outcome == 'Critical Success';
    final isFumble = outcome == 'Critical Failure';

    if (isCrit) {
      AudioService.instance.play(Sfx.crit);
    } else if (isFumble) {
      AudioService.instance.play(Sfx.fail);
    } else if (damage > 0) {
      AudioService.instance.play(Sfx.dice);
    }

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('$outcome on ${target.name}: $notes (Damage: $damage)'),
        backgroundColor: isCrit
            ? PathfinderTheme.crimson
            : (isFumble ? Colors.grey[700] : PathfinderTheme.gold),
        behavior: SnackBarBehavior.floating,
      ),
    );
  }

  void _showStrikeDialog(Combatant target) {
    final attackCtrl = TextEditingController(text: '20');
    final damageCtrl = TextEditingController(text: '6');
    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        title: Text('Strike ${target.name} (AC ${target.ac})'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: attackCtrl,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(labelText: 'Attack Roll'),
            ),
            TextField(
              controller: damageCtrl,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(labelText: 'Damage Roll'),
            ),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
          FilledButton(
            onPressed: () {
              Navigator.pop(context);
              _resolveStrike(target, attackRoll: int.tryParse(attackCtrl.text) ?? 0, damageRoll: int.tryParse(damageCtrl.text) ?? 0);
            },
            child: const Text('Resolve'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Combat Tracker'),
        actions: [
          IconButton(
            icon: const Icon(Icons.add),
            tooltip: 'Add Combatant',
            onPressed: () => _showAddCombatantDialog(),
          ),
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: 'Next Turn',
            onPressed: widget.store.isProcessing ? null : () => widget.store.nextTurn(),
          ),
          IconButton(
            icon: const Icon(Icons.clear_all),
            tooltip: 'Clear Encounter',
            onPressed: widget.store.combatants.isEmpty ? null : () => widget.store.clearEncounter(),
          ),
        ],
      ),
      body: Consumer<CombatStore>(
        builder: (context, store, _) {
          return Column(
            children: [
              // Round / Active Turn Header
              Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 16),
                decoration: BoxDecoration(
                  color: PathfinderTheme.crimson.withValues(alpha: 0.15),
                  border: Border(
                    bottom: BorderSide(color: PathfinderTheme.gold, width: 2),
                  ),
                ),
                child: Row(
                  children: [
                    Expanded(
                      child: Text(
                        'Round ${store.currentRound}',
                        style: const TextStyle(
                          fontSize: 20,
                          fontWeight: FontWeight.bold,
                          color: PathfinderTheme.crimson,
                        ),
                      ),
                    ),
                    if (store.activeCombatant != null)
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                        decoration: BoxDecoration(
                          color: PathfinderTheme.gold,
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Text(
                          'Turn: ${store.activeCombatant!.name}',
                          style: const TextStyle(
                            fontWeight: FontWeight.bold,
                            color: PathfinderTheme.ink,
                          ),
                        ),
                      ),
                  ],
                ),
              ),
              // Combatant List
              Expanded(
                child: store.combatants.isEmpty
                    ? Center(
                        child: Column(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            const Icon(Icons.auto_fix_high, size: 64, color: Colors.grey),
                            const SizedBox(height: 16),
                            Text(
                              'No combatants yet',
                              style: TextStyle(fontSize: 18, color: Colors.grey[600]),
                            ),
                            const SizedBox(height: 8),
                            FilledButton.icon(
                              onPressed: () => _showAddCombatantDialog(),
                              icon: const Icon(Icons.add),
                              label: const Text('Add First Combatant'),
                            ),
                          ],
                        ),
                      )
                    : ReorderableListView.builder(
                        padding: const EdgeInsets.all(12),
                        onReorder: store.reorder,
                        itemCount: store.combatants.length,
                        itemBuilder: (context, index) {
                          final c = store.combatants[index];
                          final isActive = index == store.activeIndex;
                          return _CombatantCard(
                            key: ValueKey(c.id),
                            combatant: c,
                            isActive: isActive,
                            onStrike: () => _showStrikeDialog(c),
                            onEdit: () => _showAddCombatantDialog(edit: c),
                            onRemove: () => store.removeCombatant(c.id),
                            onHpChanged: (delta) => store.updateHp(c.id, delta),
                            onTempHpChanged: (temp) => store.setTempHp(c.id, temp),
                            onConditionAdded: (cond) => store.addCondition(c.id, cond),
                            onConditionRemoved: (name) => store.removeCondition(c.id, name),
                          );
                        },
                      ),
              ),
            ],
          );
        },
      ),
    );
  }
}

class _CombatantCard extends StatefulWidget {
  final Combatant combatant;
  final bool isActive;
  final VoidCallback onStrike;
  final VoidCallback onEdit;
  final VoidCallback onRemove;
  final ValueChanged<int> onHpChanged;
  final ValueChanged<int> onTempHpChanged;
  final ValueChanged<CombatCondition> onConditionAdded;
  final ValueChanged<String> onConditionRemoved;

  const _CombatantCard({
    super.key,
    required this.combatant,
    required this.isActive,
    required this.onStrike,
    required this.onEdit,
    required this.onRemove,
    required this.onHpChanged,
    required this.onTempHpChanged,
    required this.onConditionAdded,
    required this.onConditionRemoved,
  });

  @override
  State<_CombatantCard> createState() => _CombatantCardState();
}

class _CombatantCardState extends State<_CombatantCard> {
  final _conditionNameCtrl = TextEditingController();
  final _conditionValueCtrl = TextEditingController(text: '1');
  final _conditionDurationCtrl = TextEditingController();

  @override
  void dispose() {
    _conditionNameCtrl.dispose();
    _conditionValueCtrl.dispose();
    _conditionDurationCtrl.dispose();
    super.dispose();
  }

  void _showAddConditionDialog() {
    _conditionNameCtrl.clear();
    _conditionValueCtrl.text = '1';
    _conditionDurationCtrl.clear();
    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Add Condition'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: _conditionNameCtrl,
              decoration: const InputDecoration(labelText: 'Name (e.g., Frightened, Prone)'),
            ),
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _conditionValueCtrl,
                    keyboardType: TextInputType.number,
                    decoration: const InputDecoration(labelText: 'Value'),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: TextField(
                    controller: _conditionDurationCtrl,
                    keyboardType: TextInputType.number,
                    decoration: const InputDecoration(labelText: 'Duration (rounds, optional)'),
                  ),
                ),
              ],
            ),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
          FilledButton(
            onPressed: () {
              final name = _conditionNameCtrl.text.trim();
              if (name.isEmpty) return;
              Navigator.pop(context);
              widget.onConditionAdded(CombatCondition(
                name: name,
                value: int.tryParse(_conditionValueCtrl.text) ?? 1,
                durationRounds: _conditionDurationCtrl.text.isEmpty ? null : int.tryParse(_conditionDurationCtrl.text),
              ));
            },
            child: const Text('Add'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final c = widget.combatant;
    final hpPercent = c.hpPercent / 100.0;
    final isDead = c.isDead;

    return RpgPanels.gothicStone.build(
      padding: const EdgeInsets.all(12),
      child: AnimatedContainer(
        duration: 300.ms,
        curve: Curves.easeOut,
        decoration: widget.isActive
            ? BoxDecoration(
                border: Border.all(color: PathfinderTheme.gold, width: 3),
                borderRadius: BorderRadius.circular(8),
                boxShadow: [
                  BoxShadow(
                    color: PathfinderTheme.gold.withValues(alpha: 0.4),
                    blurRadius: 8,
                    spreadRadius: 1,
                  ),
                ],
              )
            : null,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header row
            Row(
              children: [
                // Active indicator
                if (widget.isActive)
                  Container(
                    width: 8,
                    height: 8,
                    margin: const EdgeInsets.only(right: 8),
                    decoration: const BoxDecoration(
                      color: PathfinderTheme.gold,
                      shape: BoxShape.circle,
                    ),
                  )
                else
                  const SizedBox(width: 16),
                // Name + badges
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Text(
                            c.name,
                            style: TextStyle(
                              fontSize: 18,
                              fontWeight: FontWeight.bold,
                              color: isDead ? Colors.grey : PathfinderTheme.crimson,
                            ),
                          ),
                          const SizedBox(width: 8),
                          if (c.isPc)
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                              decoration: BoxDecoration(
                                color: PathfinderTheme.gold.withValues(alpha: 0.3),
                                borderRadius: BorderRadius.circular(4),
                              ),
                              child: const Text('PC', style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold)),
                            ),
                        ],
                      ),
                      Text(
                        'Init: ${c.initiative}  |  AC: ${c.ac}',
                        style: TextStyle(fontSize: 12, color: Colors.grey[700]),
                      ),
                    ],
                  ),
                ),
                // Actions
                PopupMenuButton<String>(
                  onSelected: (value) {
                    switch (value) {
                      case 'edit':
                        widget.onEdit();
                        break;
                      case 'strike':
                        widget.onStrike();
                        break;
                      case 'remove':
                        widget.onRemove();
                        break;
                    }
                  },
                  itemBuilder: (_) => const [
                    PopupMenuItem(value: 'strike', child: Text('Strike')),
                    PopupMenuItem(value: 'edit', child: Text('Edit')),
                    PopupMenuItem(value: 'remove', child: Text('Remove')),
                  ],
                ),
              ],
            ),
            const SizedBox(height: 12),
            // HP Bar
            Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Text(
                            'HP: ${c.currentHp} / ${c.maxHp}',
                            style: const TextStyle(fontWeight: FontWeight.bold),
                          ),
                          if (c.tempHp > 0) ...[
                            const SizedBox(width: 8),
                            Text(
                              '+${c.tempHp} temp',
                              style: TextStyle(
                                fontSize: 12,
                                color: PathfinderTheme.gold,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ],
                        ],
                      ),
                      const SizedBox(height: 4),
                      LinearProgressIndicator(
                        value: hpPercent.clamp(0.0, 1.0),
                        minHeight: 10,
                        backgroundColor: Colors.grey[300],
                        valueColor: AlwaysStoppedAnimation<Color>(
                          isDead
                              ? Colors.grey
                              : (hpPercent > 0.5
                                  ? Colors.green
                                  : (hpPercent > 0.25 ? Colors.orange : PathfinderTheme.crimson)),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 12),
                // Quick HP buttons
                Column(
                  children: [
                    Row(
                      children: [
                        _HpButton(-5, () => widget.onHpChanged(-5)),
                        const SizedBox(width: 4),
                        _HpButton(-1, () => widget.onHpChanged(-1)),
                      ],
                    ),
                    const SizedBox(height: 4),
                    Row(
                      children: [
                        _HpButton(1, () => widget.onHpChanged(1)),
                        const SizedBox(width: 4),
                        _HpButton(5, () => widget.onHpChanged(5)),
                      ],
                    ),
                  ],
                ),
              ],
            ),
            const SizedBox(height: 8),
            // Conditions
            if (c.conditions.isNotEmpty) ...[
              const Divider(),
              Wrap(
                spacing: 6,
                runSpacing: 4,
                children: c.conditions.map((cond) {
                  return Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: PathfinderTheme.crimson.withValues(alpha: 0.15),
                      border: Border.all(color: PathfinderTheme.crimson.withValues(alpha: 0.5)),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(
                          '${cond.name} ${cond.value}',
                          style: const TextStyle(
                            fontWeight: FontWeight.bold,
                            color: PathfinderTheme.crimson,
                          ),
                        ),
                        if (cond.durationRounds != null) ...[
                          const SizedBox(width: 6),
                          Text(
                            '${cond.durationRounds} r',
                            style: TextStyle(fontSize: 11, color: Colors.grey[600]),
                          ),
                        ],
                        const SizedBox(width: 4),
                        GestureDetector(
                          onTap: () => widget.onConditionRemoved(cond.name),
                          child: const Icon(Icons.close, size: 14, color: PathfinderTheme.crimson),
                        ),
                      ],
                    ),
                  );
                }).toList(),
              ),
              const SizedBox(height: 4),
            ],
            // Add condition button
            if (c.conditions.isEmpty || c.conditions.length < 6)
              TextButton.icon(
                onPressed: _showAddConditionDialog,
                icon: const Icon(Icons.add, size: 16),
                label: const Text('Add Condition'),
                style: TextButton.styleFrom(
                  foregroundColor: PathfinderTheme.gold,
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _HpButton extends StatelessWidget {
  final int delta;
  final VoidCallback onTap;
  const _HpButton(this.delta, this.onTap);

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(6),
      child: Container(
        width: 44,
        height: 32,
        decoration: BoxDecoration(
          color: delta > 0 ? Colors.green.withValues(alpha: 0.2) : PathfinderTheme.crimson.withValues(alpha: 0.2),
          border: Border.all(color: delta > 0 ? Colors.green : PathfinderTheme.crimson),
          borderRadius: BorderRadius.circular(6),
        ),
        child: Center(
          child: Text(
            delta > 0 ? '+$delta' : '$delta',
            style: TextStyle(
              fontWeight: FontWeight.bold,
              color: delta > 0 ? Colors.green : PathfinderTheme.crimson,
            ),
          ),
        ),
      ),
    );
  }
}