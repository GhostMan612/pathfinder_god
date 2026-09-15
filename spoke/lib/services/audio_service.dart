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
  static const _keyTrack = 'music_track';

  static const List<String> tracks = ['Tavern', 'Inn'];
  static const List<String> _trackAssets = [
    'audio/bgm_tavern.mp3',
    'audio/bgm_inn.mp3',
  ];

  final List<AudioPlayer> _sfxPool = [];
  AudioPlayer? _music;
  int _next = 0;
  bool _ready = false;
  bool _sfxEnabled = true;
  bool _musicEnabled = true;
  int _track = 0;

  bool get sfxEnabled => _sfxEnabled;
  bool get musicEnabled => _musicEnabled;
  int get musicTrack => _track;
  String get musicTrackName => tracks[_track.clamp(0, tracks.length - 1)];

  Future<void> init() async {
    if (_ready) return;
    try {
      final prefs = await SharedPreferences.getInstance();
      _sfxEnabled = prefs.getBool(_keySfx) ?? true;
      _musicEnabled = prefs.getBool(_keyMusic) ?? true;
      _track = (prefs.getInt(_keyTrack) ?? 0).clamp(0, tracks.length - 1);

      for (var i = 0; i < 4; i++) {
        final p = AudioPlayer();
        await p.setReleaseMode(ReleaseMode.stop);
        try {
          await p.setPlayerMode(PlayerMode.lowLatency);
          await p.setAudioContext(
            AudioContext(
              android: const AudioContextAndroid(
                contentType: AndroidContentType.sonification,
                usageType: AndroidUsageType.game,
                audioFocus: AndroidAudioFocus.none,
              ),
            ),
          );
        } catch (_) {}
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
      await player.play(AssetSource(_trackAssets[_track.clamp(0, _trackAssets.length - 1)]));
    } catch (_) {
      _music = null;
    }
  }

  Future<void> setMusicTrack(int index) async {
    _track = index.clamp(0, tracks.length - 1);
    try {
      (await SharedPreferences.getInstance()).setInt(_keyTrack, _track);
    } catch (_) {}
    if (_musicEnabled) {
      await stopMusic();
      _music = null;
      await startMusic();
    }
  }

  Future<void> nextTrack() async {
    await setMusicTrack((_track + 1) % tracks.length);
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
      Sfx.dice => ('audio/dice_roll.ogg', 0.9),
      Sfx.crit => ('audio/dice_crit.wav', 0.95),
      Sfx.fail => ('audio/dice_fail.ogg', 0.85),
      Sfx.error => ('audio/error.ogg', 0.6),
      Sfx.tap => ('audio/tap.wav', 0.5),
    };
    final player = _sfxPool[_next];
    _next = (_next + 1) % _sfxPool.length;
    unawaited(player.play(AssetSource(asset), volume: volume).catchError((_) {}));
  }
}

/// Track/artist/license credits for the bundled royalty-free audio.
/// Full sources + URLs: docs/audio-credits.md
const kAudioCredits = '''
Background music
- "The Old Tower Inn" by RandomMind (CC0) — Tavern track
- "Inn Music" by tcarisland (CC BY 4.0) — Inn track

Sound effects
- Dice rattle, fail yelp, error thud — 80 CC0 RPG SFX + 100 CC0 SFX (CC0, via OpenGameArt.org)
- Crit coin, UI tap, CC dice/tap — "RPG Sound Pack" by Tuomo Untinen (CC BY 3.0, Heroes of Hawks Haven)
''';
