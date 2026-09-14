// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

import 'dart:async';

import 'package:audioplayers/audioplayers.dart';
import 'package:shared_preferences/shared_preferences.dart';

enum Sfx { dice, crit, fail, error, tap }

/// App-wide sound service: pooled SFX players + looping background music.
/// Preferences persist via shared_preferences; every call is fail-safe so
/// audio problems can never crash the app (or a widget test).
class AudioService {
  static final AudioService instance = AudioService._();
  AudioService._();

  static const _keySfx = 'sfx_enabled';
  static const _keyMusic = 'music_enabled';

  final List<AudioPlayer> _sfxPool = [];
  AudioPlayer? _music;
  int _next = 0;
  bool _ready = false;
  bool _sfxEnabled = true;
  bool _musicEnabled = true;

  bool get sfxEnabled => _sfxEnabled;
  bool get musicEnabled => _musicEnabled;

  Future<void> init() async {
    if (_ready) return;
    try {
      final prefs = await SharedPreferences.getInstance();
      _sfxEnabled = prefs.getBool(_keySfx) ?? true;
      _musicEnabled = prefs.getBool(_keyMusic) ?? true;

      for (var i = 0; i < 3; i++) {
        final p = AudioPlayer();
        await p.setReleaseMode(ReleaseMode.stop);
        _sfxPool.add(p);
      }

      if (_musicEnabled) await startMusic();
      _ready = true;
    } catch (_) {
      _ready = false;
    }
  }

  Future<void> startMusic() async {
    try {
      final player = _music ??= AudioPlayer();
      await player.setReleaseMode(ReleaseMode.loop);
      await player.setVolume(0.55);
      await player.play(AssetSource('audio/bgm_tavern.wav'));
    } catch (_) {
      _music = null;
    }
  }

  Future<void> stopMusic() async {
    try {
      await _music?.stop();
    } catch (_) {}
  }

  Future<void> setSfxEnabled(bool enabled) async {
    _sfxEnabled = enabled;
    try {
      (await SharedPreferences.getInstance()).setBool(_keySfx, enabled);
    } catch (_) {}
  }

  Future<void> setMusicEnabled(bool enabled) async {
    _musicEnabled = enabled;
    try {
      (await SharedPreferences.getInstance()).setBool(_keyMusic, enabled);
    } catch (_) {}
    if (enabled) {
      await startMusic();
    } else {
      await stopMusic();
    }
  }

  void play(Sfx sfx) {
    if (!_ready || !_sfxEnabled || _sfxPool.isEmpty) return;
    final (asset, volume) = switch (sfx) {
      Sfx.dice => ('audio/dice_roll.wav', 0.9),
      Sfx.crit => ('audio/dice_crit.wav', 0.95),
      Sfx.fail => ('audio/dice_fail.wav', 0.85),
      Sfx.error => ('audio/error.wav', 0.6),
      Sfx.tap => ('audio/tap.wav', 0.5),
    };
    final player = _sfxPool[_next];
    _next = (_next + 1) % _sfxPool.length;
    unawaited(player.play(AssetSource(asset), volume: volume).catchError((_) {}));
  }
}