// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import '../api/hub_client.dart';

/// Offline miss queue — queries nothing could answer.
///
/// When a rulebook search comes back empty (offline DB miss + hub miss or
/// hub unreachable), the query is saved here. The next time the hub is
/// reachable the queue drains to POST /rules/missed, and the hub's chunked
/// fleet backfill scrapes those exact terms — so every miss permanently
/// improves the database.
class MissQueue {
  static const _key = 'miss_queue';
  static const maxItems = 100;

  static Future<List<Map<String, String>>> pending() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final raw = prefs.getString(_key);
      if (raw == null || raw.isEmpty) return <Map<String, String>>[];
      final decoded = jsonDecode(raw);
      if (decoded is! List) return <Map<String, String>>[];
      return decoded
          .whereType<Map>()
          .map((m) => {
                'q': '${m['q'] ?? ''}',
                'edition': '${m['edition'] ?? 'both'}',
              })
          .where((m) => (m['q'] ?? '').isNotEmpty)
          .toList();
    } catch (_) {
      return <Map<String, String>>[];
    }
  }

  static Future<void> queue(String query, {String edition = 'both'}) async {
    final q = query.trim();
    if (q.isEmpty) return;
    try {
      final prefs = await SharedPreferences.getInstance();
      final items = await pending();
      if (items.any((m) => m['q'] == q && m['edition'] == edition)) return;
      items.add({'q': q, 'edition': edition});
      while (items.length > maxItems) {
        items.removeAt(0);
      }
      await prefs.setString(_key, jsonEncode(items));
    } catch (_) {}
  }

  static Future<void> clear() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.remove(_key);
    } catch (_) {}
  }

  /// Send everything queued to the hub. Clears on success; keeps the
  /// queue intact when the hub is unreachable. Returns queued count.
  static Future<int> drain(HubClient client) async {
    final items = await pending();
    if (items.isEmpty) return 0;
    try {
      final n = await client.reportMisses(items);
      if (n > 0) await clear();
      return n;
    } catch (_) {
      return 0;
    }
  }
}
