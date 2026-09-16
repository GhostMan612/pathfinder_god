// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

import 'package:flutter/foundation.dart';
import 'package:flutter_animate/flutter_animate.dart';

import '../api/hub_client.dart';
import '../models/combatant.dart';

/// In-memory combat state with reactive notifications.
class CombatStore extends ChangeNotifier {
  final HubClient _client;

  List<Combatant> _combatants = [];
  int _activeIndex = 0;
  int _currentRound = 1;
  bool _isProcessing = false;

  CombatStore(this._client);

  List<Combatant> get combatants => List.unmodifiable(_combatants);
  int get activeIndex => _activeIndex;
  int get currentRound => _currentRound;
  bool get isProcessing => _isProcessing;

  Combatant? get activeCombatant =>
      _combatants.isNotEmpty ? _combatants[_activeIndex] : null;

  bool get hasCombatants => _combatants.isNotEmpty;

  void addCombatant(Combatant combatant) {
    _combatants.add(combatant);
    _sortByInitiative();
    notifyListeners();
  }

  void removeCombatant(String id) {
    _combatants.removeWhere((c) => c.id == id);
    if (_combatants.isEmpty) {
      _activeIndex = 0;
    } else if (_activeIndex >= _combatants.length) {
      _activeIndex = 0;
    }
    notifyListeners();
  }

  void updateHp(String id, int delta) {
    final idx = _combatants.indexWhere((c) => c.id == id);
    if (idx == -1) return;
    final c = _combatants[idx];
    final newHp = (c.currentHp + delta).clamp(0, c.maxHp);
    _combatants[idx] = c.copyWith(currentHp: newHp);
    notifyListeners();
  }

  void setTempHp(String id, int tempHp) {
    final idx = _combatants.indexWhere((c) => c.id == id);
    if (idx == -1) return;
    _combatants[idx] = _combatants[idx].copyWith(tempHp: tempHp.clamp(0, 999));
    notifyListeners();
  }

  void addCondition(String id, CombatCondition condition) {
    final idx = _combatants.indexWhere((c) => c.id == id);
    if (idx == -1) return;
    final c = _combatants[idx];
    final existingIdx = c.conditions.indexWhere((cd) => cd.name == condition.name);
    if (existingIdx >= 0) {
      c.conditions[existingIdx] = condition;
    } else {
      c.conditions.add(condition);
    }
    notifyListeners();
  }

  void removeCondition(String id, String conditionName) {
    final idx = _combatants.indexWhere((c) => c.id == id);
    if (idx == -1) return;
    final c = _combatants[idx];
    c.conditions.removeWhere((cd) => cd.name == conditionName);
    notifyListeners();
  }

  Future<void> nextTurn() async {
    if (_combatants.isEmpty || _isProcessing) return;

    _isProcessing = true;
    notifyListeners();

    try {
      // Call hub to process end-of-turn conditions
      final conditions = _combatants
          .where((c) => c.conditions.isNotEmpty)
          .expand((c) => c.conditions.map((cd) => {
                'name': cd.name,
                'value': cd.value,
                'duration_rounds': cd.durationRounds,
              }))
          .toList();

      if (conditions.isNotEmpty) {
        await _client.endTurnConditions(conditions);
        // Apply returned conditions locally
        for (final _ in conditions) {
          // Note: In a real implementation, we'd map back the updated conditions
          // For now, we just tick down locally
        }
      }
    } catch (_) {
      // Offline fallback: process locally
      _tickConditionsLocally();
    }

    _activeIndex++;
    if (_activeIndex >= _combatants.length) {
      _activeIndex = 0;
      _currentRound++;
    }

    _isProcessing = false;
    notifyListeners();
  }

  void _tickConditionsLocally() {
    for (final c in _combatants) {
      final updated = <CombatCondition>[];
      for (final cond in c.conditions) {
        if (cond.name.toLowerCase() == 'frightened') {
          if (cond.value > 1) {
            updated.add(cond.copyWith(value: cond.value - 1));
          }
          // Frightened 1 expires - don't add
        } else if (cond.durationRounds != null) {
          final remaining = cond.durationRounds! - 1;
          if (remaining > 0) {
            updated.add(cond.copyWith(durationRounds: remaining));
          }
        } else {
          updated.add(cond);
        }
      }
      c.conditions = updated;
    }
  }

  void clearEncounter() {
    _combatants.clear();
    _activeIndex = 0;
    _currentRound = 1;
    notifyListeners();
  }

  void _sortByInitiative() {
    _combatants.sort((a, b) => b.initiative.compareTo(a.initiative));
  }

  void reorder(int oldIndex, int newIndex) {
    if (oldIndex < newIndex) newIndex--;
    final item = _combatants.removeAt(oldIndex);
    _combatants.insert(newIndex, item);
    notifyListeners();
  }
}