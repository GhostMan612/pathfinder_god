// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

import 'dart:async';
import 'dart:math';

import 'package:flutter/material.dart';

import 'dice_impact.dart';

class AnimatedDiceRoller {
  static const double finalTumbleX = 4 * pi;
  static const double finalTumbleY = 8 * pi;
  static const double finalSpinZ = 4 * pi;

  final TickerProvider _vsync;
  late final AnimationController _controller;
  late final Animation<double> _tumbleXAnimation;
  late final Animation<double> _tumbleYAnimation;
  late final Animation<double> _spinAnimation;
  late final Animation<double> _bounceAnimation;
  late final Animation<double> _scaleAnimation;

  int _currentValue = 1;
  bool _isRolling = false;
  final Function(int) _onComplete;
  void Function(int impactIndex)? onImpact;
  int _rollId = 0;
  bool _disposed = false;

  AnimatedDiceRoller(this._vsync, this._onComplete, {this.onImpact}) {
    _controller = AnimationController(
      duration: const Duration(milliseconds: 1200),
      vsync: _vsync,
    );

    _tumbleXAnimation = TweenSequence<double>([
      TweenSequenceItem(tween: Tween(begin: 0.0, end: 2.6 * pi), weight: 55),
      TweenSequenceItem(tween: Tween(begin: 2.6 * pi, end: 3.7 * pi), weight: 25),
      TweenSequenceItem(tween: Tween(begin: 3.7 * pi, end: finalTumbleX), weight: 20),
    ]).animate(CurvedAnimation(parent: _controller, curve: Curves.easeOutCubic));

    _tumbleYAnimation = TweenSequence<double>([
      TweenSequenceItem(tween: Tween(begin: 0.0, end: 6 * pi), weight: 55),
      TweenSequenceItem(tween: Tween(begin: 6 * pi, end: 7.6 * pi), weight: 25),
      TweenSequenceItem(tween: Tween(begin: 7.6 * pi, end: finalTumbleY), weight: 20),
    ]).animate(CurvedAnimation(parent: _controller, curve: Curves.easeOutCubic));

    _spinAnimation = TweenSequence<double>([
      TweenSequenceItem(tween: Tween(begin: 0.0, end: 3 * pi), weight: 55),
      TweenSequenceItem(tween: Tween(begin: 3 * pi, end: 3.8 * pi), weight: 25),
      TweenSequenceItem(tween: Tween(begin: 3.8 * pi, end: finalSpinZ), weight: 20),
    ]).animate(CurvedAnimation(parent: _controller, curve: Curves.easeOutCubic));

    _bounceAnimation = TweenSequence<double>([
      TweenSequenceItem(tween: Tween(begin: 0.0, end: 1.0), weight: 25),
      TweenSequenceItem(tween: Tween(begin: 1.0, end: 0.0), weight: 18),
      TweenSequenceItem(tween: Tween(begin: 0.0, end: 0.45), weight: 15),
      TweenSequenceItem(tween: Tween(begin: 0.45, end: 0.0), weight: 14),
      TweenSequenceItem(tween: Tween(begin: 0.0, end: 0.18), weight: 14),
      TweenSequenceItem(tween: Tween(begin: 0.18, end: 0.0), weight: 14),
    ]).animate(CurvedAnimation(parent: _controller, curve: Curves.easeOut));

    _scaleAnimation = TweenSequence<double>([
      TweenSequenceItem(tween: Tween(begin: 1.0, end: 1.35), weight: 18),
      TweenSequenceItem(tween: Tween(begin: 1.35, end: 0.82), weight: 18),
      TweenSequenceItem(tween: Tween(begin: 0.82, end: 1.12), weight: 16),
      TweenSequenceItem(tween: Tween(begin: 1.12, end: 0.97), weight: 16),
      TweenSequenceItem(tween: Tween(begin: 0.97, end: 1.0), weight: 32),
    ]).animate(CurvedAnimation(parent: _controller, curve: Curves.easeOutCubic));

    _controller.addStatusListener((status) {
      if (status == AnimationStatus.completed) {
        _isRolling = false;
        _onComplete(_currentValue);
      }
    });
  }

  void dispose() {
    _disposed = true;
    _rollId++;
    _controller.dispose();
  }

  void roll() {
    if (_isRolling) {
      return;
    }
    _isRolling = true;
    _currentValue = Random().nextInt(20) + 1;
    if (_controller.isAnimating) _controller.stop();
    final id = ++_rollId;
    _scheduleImpacts(id);
    _controller.forward(from: 0).catchError((e) {
      _isRolling = false;
    });
  }

  void _scheduleImpacts(int id) {
    final cb = onImpact;
    if (cb == null) return;
    const timings = [300, 620, 920];
    for (var i = 0; i < timings.length; i++) {
      Future.delayed(Duration(milliseconds: timings[i]), () {
        if (_disposed || id != _rollId || !_isRolling) return;
        cb(i);
      });
    }
  }

  bool get isRolling => _isRolling;

  Animation<double> get spin => _spinAnimation;
  Animation<double> get tumbleX => _tumbleXAnimation;
  Animation<double> get tumbleY => _tumbleYAnimation;
  Animation<double> get bounce => _bounceAnimation;
  Animation<double> get scale => _scaleAnimation;
  int get currentValue => _currentValue;
}

class AnimatedDie extends AnimatedWidget {
  final AnimatedDiceRoller roller;
  final DiceSkin skin;

  AnimatedDie({super.key, required this.roller, this.skin = DiceSkin.obsidian})
      : super(listenable: roller._controller);

  @override
  Widget build(BuildContext context) {
    final tx = roller._tumbleXAnimation.value;
    final ty = roller._tumbleYAnimation.value;
    final sz = roller._spinAnimation.value;
    final bounce = roller._bounceAnimation.value;
    final scale = roller._scaleAnimation.value;

    return Transform.translate(
      offset: Offset(0, -bounce * 95),
      child: Transform.scale(
        scale: scale,
        child: Transform(
          alignment: Alignment.center,
          transform: Matrix4.identity()
            ..setEntry(3, 2, 0.002)
            ..rotateX(tx)
            ..rotateY(ty)
            ..rotateZ(sz),
          child: _buildDieFace(context, roller, skin),
        ),
      ),
    );
  }

  Widget _buildDieFace(
      BuildContext context, AnimatedDiceRoller roller, DiceSkin skin) {
    final showResult = !roller._isRolling && roller._currentValue > 0;
    final v = roller._currentValue;
    final isCrit = showResult && v == 20;
    final isFumble = showResult && v == 1;
    final edge =
        isCrit ? const Color(0xFFFF2D2D) : (isFumble ? Colors.grey : skin.edge);
    final glowOpacity = isCrit ? 0.85 : (isFumble ? 0.0 : 0.35);

    return Container(
      width: 100,
      height: 100,
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: skin.gradient,
        ),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: edge, width: isCrit ? 4 : 2.5),
        boxShadow: [
          BoxShadow(
            color: skin.glow.withValues(alpha: glowOpacity),
            blurRadius: isCrit ? 28 : 12,
            spreadRadius: isCrit ? 4 : 1,
          ),
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.45),
            blurRadius: 10,
            offset: const Offset(0, 5),
          ),
        ],
      ),
      child: Center(
        child: Text(
          showResult ? '$v' : '?',
          style: TextStyle(
            fontSize: showResult ? 48 : 36,
            fontWeight: FontWeight.bold,
            color: skin.face,
            shadows: [
              Shadow(
                color: Colors.black.withValues(alpha: 0.6),
                offset: const Offset(2, 2),
                blurRadius: 4,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class DiceAnimationWidget extends StatefulWidget {
  final AnimatedDiceRoller? roller;
  final Function(int) onResult;
  final bool enabled;
  final DiceSkin skin;

  const DiceAnimationWidget({
    super.key,
    this.roller,
    required this.onResult,
    this.enabled = true,
    this.skin = DiceSkin.obsidian,
  });

  @override
  State<DiceAnimationWidget> createState() => _DiceAnimationWidgetState();
}

class _DiceAnimationWidgetState extends State<DiceAnimationWidget>
    with SingleTickerProviderStateMixin {
  late final AnimatedDiceRoller _roller;
  bool get _ownsRoller => widget.roller == null;

  @override
  void initState() {
    super.initState();
    _roller = widget.roller ?? AnimatedDiceRoller(this, widget.onResult);
  }

  @override
  void dispose() {
    if (_ownsRoller) _roller.dispose();
    super.dispose();
  }

  void _roll() {
    if (widget.enabled) {
      _roller.roll();
    }
  }

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: _roll,
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: AnimatedDie(roller: _roller, skin: widget.skin),
      ),
    );
  }
}
