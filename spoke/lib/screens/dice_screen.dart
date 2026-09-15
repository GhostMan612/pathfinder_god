// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

import 'dart:async';
import 'dart:math';

import 'package:flutter/material.dart';

import '../dice/dice.dart';
import '../dice/dice_impact.dart';
import '../dice/dice_physics.dart';
import '../services/audio_service.dart';
import '../services/haptics_service.dart';
import '../theme/app_theme.dart';

class _FloatMarker {
  final int id;
  final String label;
  final bool isCrit;
  final bool isFumble;
  const _FloatMarker({
    required this.id,
    required this.label,
    required this.isCrit,
    required this.isFumble,
  });
}

class DiceScreen extends StatefulWidget {
  const DiceScreen({super.key});

  @override
  State<DiceScreen> createState() => _DiceScreenState();
}

class _DiceScreenState extends State<DiceScreen> with TickerProviderStateMixin {
  final _roller = DiceRoller();
  late final AnimatedDiceRoller _animatedRoller;
  late final AnimationController _shakeController;
  late final Animation<double> _shakeAnim;
  final _controller = TextEditingController(text: '2d6+3');
  final _history = <DiceResult>[];
  final _markers = <_FloatMarker>[];
  int _markerId = 0;
  DiceResult? _last;
  String? _error;
  bool _useAnimation = true;
  bool _soundEnabled = AudioService.instance.sfxEnabled;
  bool _hapticsEnabled = true;
  DiceSkin _skin = DiceSkin.obsidian;
  bool _critFlash = false;
  double _shakeStrength = 0.15;

  @override
  void initState() {
    super.initState();
    _animatedRoller = AnimatedDiceRoller(this, _onAnimationComplete);
    _animatedRoller.onImpact = _onImpact;
    _shakeController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 450),
    );
    _shakeAnim = CurvedAnimation(
      parent: _shakeController,
      curve: Curves.easeOut,
    );
  }

  void _onImpact(int index) {
    HapticsService.light();
    AudioService.instance.play(Sfx.tap);
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
    final isCrit = DiceImpact.isNat20(value, 20);
    final isFumble = DiceImpact.isNat1(value, 20);
    setState(() {
      _last = result;
      _history.insert(0, result);
      if (_history.length > 30) _history.removeLast();
    });
    AudioService.instance.play(DiceImpact.sfxFor(value, 20));
    if (isCrit) {
      HapticsService.heavy();
      HapticsService.vibrate();
      _triggerShake(1.0);
      _triggerFlash();
      _spawnMarker(DiceImpact.markerFor(value, 20), true, false);
    } else if (isFumble) {
      HapticsService.medium();
      HapticsService.vibrate();
      _triggerShake(0.7);
      _triggerFlash();
      _spawnMarker(DiceImpact.markerFor(value, 20), false, true);
    } else {
      HapticsService.heavy();
      if (value >= 18) _spawnMarker('$value', false, false);
    }
  }

  void _triggerShake(double strength) {
    _shakeStrength = strength;
    _shakeController.forward(from: 0);
  }

  void _triggerFlash() {
    setState(() => _critFlash = true);
    Future.delayed(const Duration(milliseconds: 900), () {
      if (mounted) setState(() => _critFlash = false);
    });
  }

  void _spawnMarker(String label, bool isCrit, bool isFumble) {
    final id = ++_markerId;
    setState(() {
      _markers.add(_FloatMarker(
          id: id, label: label, isCrit: isCrit, isFumble: isFumble));
    });
    Future.delayed(const Duration(milliseconds: 1300), () {
      if (mounted) setState(() => _markers.removeWhere((m) => m.id == id));
    });
  }

  void _rollAnimated() {
    if (_animatedRoller.isRolling) return;
    setState(() {});
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
      return DiceImpact.sfxFor(result.total, 20);
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
      if (result.terms.length == 1 &&
          result.terms.first.term.sides == 20 &&
          result.terms.first.term.count == 1) {
        final v = result.total;
        if (DiceImpact.isNat20(v, 20) || DiceImpact.isNat1(v, 20)) {
          _triggerShake(DiceImpact.shakeFor(v, 20));
          _triggerFlash();
          _spawnMarker(DiceImpact.markerFor(v, 20), v == 20, v == 1);
          HapticsService.vibrate();
        }
      }
    } on DiceFormatException catch (e) {
      setState(() => _error = e.message);
      AudioService.instance.play(Sfx.error);
      HapticsService.medium();
    }
  }

  @override
  void dispose() {
    _animatedRoller.dispose();
    _shakeController.dispose();
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
      body: Stack(
        children: [
          Column(
            children: [
              _buildResultPanel(context),
              if (_useAnimation) _buildAnimatedDice() else _buildQuickDice(),
              _buildSkinPicker(),
              _buildCustomInput(),
              const Divider(height: 1),
              Expanded(child: _buildHistory()),
            ],
          ),
          if (_critFlash)
            Positioned.fill(
              child: IgnorePointer(
                child: AnimatedOpacity(
                  opacity: _critFlash ? 1.0 : 0.0,
                  duration: const Duration(milliseconds: 250),
                  child: Container(
                    decoration: BoxDecoration(
                      border: Border.all(
                        color: (_last?.total == 20)
                            ? const Color(0xFFFF2D2D)
                            : Colors.grey,
                        width: 6,
                      ),
                    ),
                  ),
                ),
              ),
            ),
          for (final m in _markers) _buildFloatingMarker(m),
        ],
      ),
    );
  }

  Widget _buildFloatingMarker(_FloatMarker m) {
    final color = m.isCrit
        ? const Color(0xFFFF2D2D)
        : (m.isFumble ? Colors.grey[400]! : PathfinderTheme.gold);
    return Positioned(
      top: 120 + ((_markers.indexOf(m) % 3) * 34.0),
      left: 0,
      right: 0,
      child: IgnorePointer(
        child: TweenAnimationBuilder<double>(
          tween: Tween(begin: 0.0, end: 1.0),
          duration: const Duration(milliseconds: 1300),
          builder: (context, t, _) {
            return Opacity(
              opacity: 1.0 - t,
              child: Transform.translate(
                offset: Offset(0, -t * 70),
                child: Center(
                  child: Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
                    decoration: BoxDecoration(
                      color: Colors.black.withValues(alpha: 0.75),
                      borderRadius: BorderRadius.circular(20),
                      border: Border.all(color: color, width: 2),
                    ),
                    child: Text(
                      m.label,
                      style: TextStyle(
                        fontSize: m.isCrit ? 26 : 20,
                        fontWeight: FontWeight.w900,
                        color: color,
                        letterSpacing: 1.2,
                      ),
                    ),
                  ),
                ),
              ),
            );
          },
        ),
      ),
    );
  }

  Widget _buildResultPanel(BuildContext context) {
    final last = _last;
    return AnimatedBuilder(
      animation: _shakeAnim,
      builder: (context, _) {
        final t = _shakeAnim.value;
        final dx = sin(t * pi * 5) * (1 - t) * 14 * _shakeStrength;
        return Transform.translate(
          offset: Offset(dx, 0),
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 250),
            width: double.infinity,
            padding: const EdgeInsets.all(20),
            margin: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              gradient: _critFlash
                  ? const LinearGradient(colors: [
                      Color(0xFF7B1E1E),
                      Color(0xFF3D0A0A),
                    ])
                  : null,
              color: _critFlash ? null : PathfinderTheme.crimson,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(
                color:
                    _critFlash ? const Color(0xFFFF2D2D) : PathfinderTheme.gold,
                width: _critFlash ? 3.5 : 2,
              ),
              boxShadow: _critFlash
                  ? [
                      const BoxShadow(
                        color: Color(0xFFFF2D2D),
                        blurRadius: 24,
                        spreadRadius: 2,
                      ),
                    ]
                  : null,
            ),
            child: Column(
              children: [
                Text(
                  last == null ? '—' : '${last.total}',
                  style: const TextStyle(
                      fontSize: 56,
                      fontWeight: FontWeight.bold,
                      color: PathfinderTheme.parchment),
                ),
                const SizedBox(height: 4),
                Text(
                  _error != null
                      ? 'Error: $_error'
                      : (last?.breakdown ?? 'Roll some dice'),
                  textAlign: TextAlign.center,
                  style: TextStyle(
                      color: _error != null
                          ? PathfinderTheme.gold
                          : PathfinderTheme.parchment
                              .withValues(alpha: 0.85)),
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _buildSkinPicker() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
      child: Wrap(
        spacing: 8,
        alignment: WrapAlignment.center,
        children: [
          for (final s in DiceSkin.all)
            ChoiceChip(
              label: Text(s.label),
              selected: _skin.kind == s.kind,
              onSelected: (_) => setState(() => _skin = s),
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
            AnimatedBuilder(
              animation: _animatedRoller.spin,
              builder: (_, _) => Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  DiceAnimationWidget(
                    roller: _animatedRoller,
                    onResult: _onAnimationComplete,
                    enabled: true,
                    skin: _skin,
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
              style: FilledButton.styleFrom(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 32, vertical: 16)),
            ),
            const SizedBox(height: 8),
            SizedBox(
              height: 32,
              child: _animatedRoller.isRolling
                  ? const SizedBox.shrink()
                  : (_animatedRoller.currentValue > 0
                      ? Text(
                          'Result: ${_animatedRoller.currentValue}!',
                          style: const TextStyle(
                              fontSize: 24,
                              fontWeight: FontWeight.bold,
                              color: PathfinderTheme.gold),
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
            child: Text('${r.total}',
                style: const TextStyle(
                    color: PathfinderTheme.ink, fontWeight: FontWeight.bold)),
          ),
          title: Text(r.notation),
          subtitle: Text(r.breakdown),
        );
      },
    );
  }
}
