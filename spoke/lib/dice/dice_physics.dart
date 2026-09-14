// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

import 'dart:math';

import 'package:flutter/material.dart';

/// Simple animated dice roller with physics-inspired animation.
/// No Flame dependency - uses Flutter's built-in animation system.
class AnimatedDiceRoller {
  final TickerProvider _vsync;
  late final AnimationController _controller;
  late final Animation<double> _rotationAnimation;
  late final Animation<double> _bounceAnimation;
  late final Animation<double> _scaleAnimation;
  
  int _currentValue = 1;
  bool _isRolling = false;
  final Function(int) _onComplete;

  AnimatedDiceRoller(this._vsync, this._onComplete) {
    _controller = AnimationController(
      duration: const Duration(milliseconds: 1200),
      vsync: _vsync,
    );
    
    _rotationAnimation = TweenSequence<double>([
      TweenSequenceItem(tween: Tween(begin: 0.0, end: 8 * pi), weight: 55),
      TweenSequenceItem(tween: Tween(begin: 8 * pi, end: 9 * pi), weight: 25),
      TweenSequenceItem(tween: Tween(begin: 9 * pi, end: 9.3 * pi), weight: 20),
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
    _controller.dispose();
  }

  void roll() {
    if (_isRolling) {
      debugPrint('AnimatedDiceRoller: already rolling, ignoring');
      return;
    }
    _isRolling = true;
    _currentValue = Random().nextInt(20) + 1;
    debugPrint('AnimatedDiceRoller: roll -> $_currentValue');
    // Ensure controller is not already animating (e.g. hot reload).
    if (_controller.isAnimating) _controller.stop();
    _controller.forward(from: 0).catchError((e) {
      debugPrint('AnimatedDiceRoller: forward error $e');
      _isRolling = false;
    });
  }

  bool get isRolling => _isRolling;

  Animation<double> get rotation => _rotationAnimation;
  Animation<double> get bounce => _bounceAnimation;
  Animation<double> get scale => _scaleAnimation;
  int get currentValue => _currentValue;
}

/// Animated die widget with 3D-like rotation and bounce
class AnimatedDie extends AnimatedWidget {
  final AnimatedDiceRoller roller;
  
  AnimatedDie({super.key, required this.roller}) : super(listenable: roller._controller);

  @override
  Widget build(BuildContext context) {
    final rotation = roller._rotationAnimation.value;
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
            ..rotateX(rotation * 0.5)
            ..rotateY(rotation)
            ..rotateZ(rotation * 0.35),
          child: _buildDieFace(context, roller),
        ),
      ),
    );
  }

  Widget _buildDieFace(BuildContext context, AnimatedDiceRoller roller) {
    final showResult = !roller._isRolling && roller._currentValue > 0;
    
    return Container(
      width: 100,
      height: 100,
      decoration: BoxDecoration(
        color: const Color(0xFFF5A623),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFF3E2723), width: 3),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.3),
            blurRadius: 10,
            offset: const Offset(0, 5),
          ),
        ],
      ),
      child: Center(
        child: Text(
          showResult ? '${roller._currentValue}' : '?',
          style: TextStyle(
            fontSize: showResult ? 48 : 36,
            fontWeight: FontWeight.bold,
            color: Colors.white,
            shadows: [
              Shadow(
                color: Colors.black.withValues(alpha: 0.5),
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

/// Widget that manages the animated dice roller. Tap the die to roll, or pass
/// an externally-owned [roller] to render (the screen then drives it).
class DiceAnimationWidget extends StatefulWidget {
  final AnimatedDiceRoller? roller;
  final Function(int) onResult;
  final bool enabled;

  const DiceAnimationWidget({
    super.key,
    this.roller,
    required this.onResult,
    this.enabled = true,
  });

  @override
  State<DiceAnimationWidget> createState() => _DiceAnimationWidgetState();
}

class _DiceAnimationWidgetState extends State<DiceAnimationWidget> with SingleTickerProviderStateMixin {
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
      onTap: () {
        debugPrint('DiceAnimationWidget: tapped');
        _roll();
      },
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: AnimatedDie(roller: _roller),
      ),
    );
  }
}