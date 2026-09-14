// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Haptic feedback service for immersive feedback.
/// Respects user settings for haptics_enabled; persists via shared_preferences.
class HapticsService {
  static const _keyHaptics = 'haptics_enabled';
  static bool _enabled = true;
  static bool _initialized = false;

  static Future<void> init() async {
    if (_initialized) return;
    final prefs = await SharedPreferences.getInstance();
    _enabled = prefs.getBool(_keyHaptics) ?? true;
    _initialized = true;
  }

  static void setEnabled(bool enabled) {
    _enabled = enabled;
    SharedPreferences.getInstance().then((prefs) => prefs.setBool(_keyHaptics, enabled));
  }

  static bool get enabled => _enabled;

  /// Light impact — button taps, selection
  static Future<void> light() async {
    if (_enabled) await HapticFeedback.lightImpact();
  }

  /// Medium impact — errors, warnings
  static Future<void> medium() async {
    if (_enabled) await HapticFeedback.mediumImpact();
  }

  /// Heavy impact — critical hits, major events
  static Future<void> heavy() async {
    if (_enabled) await HapticFeedback.heavyImpact();
  }

  /// Selection click — toggles, discrete changes
  static Future<void> selection() async {
    if (_enabled) await HapticFeedback.selectionClick();
  }

  /// Vibrate — custom pattern (Android only)
  static Future<void> vibrate() async {
    if (_enabled) await HapticFeedback.vibrate();
  }
}