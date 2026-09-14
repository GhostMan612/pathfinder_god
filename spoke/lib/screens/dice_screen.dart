// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

import 'package:flutter/material.dart';

import '../dice/dice.dart';
import '../dice/dice_physics.dart';
import '../services/audio_service.dart';
import '../services/haptics_service.dart';
import '../theme/app_theme.dart';

/// Offline dice roller — quick dice, custom notation, advantage/disadvantage,
/// and a rolling history. Works with the laptop off.
/// Now with 3D physics (Flame), haptics, and sound!
class DiceScreen extends StatefulWidget {
  const DiceScreen({super.key});

  @override
  State<DiceScreen> createState() => _DiceScreenState();
}

class _DiceScreenState extends State<DiceScreen> with TickerProviderStateMixin {
  final _roller = DiceRoller();
  late final AnimatedDiceRoller _animatedRoller;
  final _controller = TextEditingController(text: '2d6+3');
  final _history = <DiceResult>[];
  DiceResult? _last;
  String? _error;
  bool _useAnimation = true;
  bool _soundEnabled = AudioService.instance.sfxEnabled;
  bool _hapticsEnabled = true;

  @override
  void initState() {
    super.initState();
    _animatedRoller = AnimatedDiceRoller(this, _onAnimationComplete);
  }

  void _onAnimationComplete(int value) {
    final result = DiceResult(
      'd20 (animated)',
      [
        TermResult(
          DiceTerm(sign: 1, count: 1, sides: 20),
          List.filled(1, value),
          List.filled(1, value),
          value,
        ),
      ],
      value,
    );
    setState(() {
      _last = result;
      _history.insert(0, result);
      if (_history.length > 30) _history.removeLast();
    });
    AudioService.instance.play(_resultSfx(result));
    HapticsService.heavy();
  }

  void _rollAnimated() {
    if (_animatedRoller.isRolling) return;
    setState(() {}); // hide old "Result:" text immediately
    HapticsService.light();
    AudioService.instance.play(Sfx.dice);
    _animatedRoller.roll();
  }

  Sfx _resultSfx(DiceResult result) {
    final terms = result.terms;
    if (terms.length == 1 &&
        !terms.first.term.isFlat &&
        terms.first.term.count == 1 &&
        terms.first.term.sides == 20) {
      if (result.total == 20) return Sfx.crit;
      if (result.total == 1) return Sfx.fail;
    }
    return Sfx.dice;
  }

  void _roll(String notation) {
    try {
      final result = _roller.roll(notation);
      setState(() {
        _last = result;
        _error = null;
        _history.insert(0, result);
        if (_history.length > 30) _history.removeLast();
      });
      AudioService.instance.play(_resultSfx(result));
      HapticsService.light();
    } on DiceFormatException catch (e) {
      setState(() => _error = e.message);
      AudioService.instance.play(Sfx.error);
      HapticsService.medium();
    }
  }

  @override
  void dispose() {
    _animatedRoller.dispose();
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Dice'),
        actions: [
          IconButton(
            icon: Icon(_useAnimation ? Icons.casino : Icons.casino_outlined),
            tooltip: _useAnimation ? '3D Animation ON' : '3D Animation OFF',
            onPressed: () => setState(() => _useAnimation = !_useAnimation),
          ),
          IconButton(
            icon: Icon(_soundEnabled ? Icons.volume_up : Icons.volume_off),
            tooltip: 'Sound FX',
            onPressed: () {
              final v = !_soundEnabled;
              AudioService.instance.setSfxEnabled(v);
              if (v) AudioService.instance.play(Sfx.tap);
              setState(() => _soundEnabled = v);
            },
          ),
          IconButton(
            icon: Icon(_hapticsEnabled ? Icons.vibration : Icons.vibration_outlined),
            tooltip: 'Haptics',
            onPressed: () {
              HapticsService.setEnabled(!_hapticsEnabled);
              setState(() => _hapticsEnabled = !_hapticsEnabled);
            },
          ),
        ],
      ),
      body: Column(
        children: [
          _buildResultPanel(context),
          if (_useAnimation) _buildAnimatedDice() else _buildQuickDice(),
          _buildCustomInput(),
          const Divider(height: 1),
          Expanded(child: _buildHistory()),
        ],
      ),
    );
  }

  Widget _buildResultPanel(BuildContext context) {
    final last = _last;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      margin: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: PathfinderTheme.crimson,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: PathfinderTheme.gold, width: 2),
      ),
      child: Column(
        children: [
          Text(
            last == null ? '—' : '${last.total}',
            style: const TextStyle(fontSize: 56, fontWeight: FontWeight.bold, color: PathfinderTheme.parchment),
          ),
          const SizedBox(height: 4),
          Text(
            _error != null ? 'Error: $_error' : (last?.breakdown ?? 'Roll some dice'),
            textAlign: TextAlign.center,
            style: TextStyle(color: _error != null ? PathfinderTheme.gold : PathfinderTheme.parchment.withValues(alpha: 0.85)),
          ),
        ],
      ),
    );
  }

  Widget _buildAnimatedDice() {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 12),
      child: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            // Rebuild wrapper so "Rolling…" text tracks isRolling without
            // waiting for the animation tick.
            AnimatedBuilder(
              animation: _animatedRoller.rotation,
              builder: (_, _) => Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  DiceAnimationWidget(
                    roller: _animatedRoller,
                    onResult: _onAnimationComplete,
                    enabled: true,
                  ),
                  const SizedBox(height: 8),
                  Text(
                    _animatedRoller.isRolling
                        ? 'Rolling…'
                        : (_animatedRoller.currentValue > 0
                            ? 'Tap die or press Roll'
                            : ''),
                    style: TextStyle(
                      fontSize: 12,
                      color: Colors.grey[600],
                      fontStyle: FontStyle.italic,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 12),
            FilledButton.icon(
              onPressed: _rollAnimated,
              icon: const Icon(Icons.casino),
              label: const Text('Roll Animated Die'),
              style: FilledButton.styleFrom(padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 16)),
            ),
            const SizedBox(height: 8),
            // Keep a fixed-height slot so layout doesn't jump when
            // rolling vs idle.
            SizedBox(
              height: 32,
              child: _animatedRoller.isRolling
                  ? const SizedBox.shrink()
                  : (_animatedRoller.currentValue > 0
                      ? Text(
                          'Result: ${_animatedRoller.currentValue}!',
                          style: const TextStyle(fontSize: 24, fontWeight: FontWeight.bold, color: PathfinderTheme.gold),
                        )
                      : const SizedBox.shrink()),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildQuickDice() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 8),
      child: Wrap(
        spacing: 8,
        runSpacing: 4,
        alignment: WrapAlignment.center,
        children: [
          for (final d in quickDice)
            ActionChip(label: Text(d), onPressed: () => _roll(d)),
          ActionChip(
            avatar: const Icon(Icons.trending_up, size: 18),
            label: const Text('Adv'),
            onPressed: () => setState(() {
              final r = _roller.advantage();
              _last = r;
              _error = null;
              _history.insert(0, r);
            }),
          ),
          ActionChip(
            avatar: const Icon(Icons.trending_down, size: 18),
            label: const Text('Dis'),
            onPressed: () => setState(() {
              final r = _roller.disadvantage();
              _last = r;
              _error = null;
              _history.insert(0, r);
            }),
          ),
        ],
      ),
    );
  }

  Widget _buildCustomInput() {
    return Padding(
      padding: const EdgeInsets.all(12),
      child: Row(
        children: [
          Expanded(
            child: TextField(
              controller: _controller,
              textInputAction: TextInputAction.done,
              onSubmitted: _roll,
              decoration: const InputDecoration(
                labelText: 'Custom (e.g. 4d6kh3+2)',
                border: OutlineInputBorder(),
                isDense: true,
              ),
            ),
          ),
          const SizedBox(width: 8),
          FilledButton.icon(
            onPressed: () => _roll(_controller.text),
            icon: const Icon(Icons.casino),
            label: const Text('Roll'),
          ),
        ],
      ),
    );
  }

  Widget _buildHistory() {
    if (_history.isEmpty) {
      return const Center(child: Text('No rolls yet.'));
    }
    return ListView.builder(
      itemCount: _history.length,
      itemBuilder: (context, i) {
        final r = _history[i];
        return ListTile(
          dense: true,
          leading: CircleAvatar(
            backgroundColor: PathfinderTheme.gold,
            child: Text('${r.total}', style: const TextStyle(color: PathfinderTheme.ink, fontWeight: FontWeight.bold)),
          ),
          title: Text(r.notation),
          subtitle: Text(r.breakdown),
        );
      },
    );
  }
}
