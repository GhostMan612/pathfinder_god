// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

import 'dart:convert';

import 'dart:async';
import 'dart:io' show Platform;

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:web_socket_channel/io.dart' show IOWebSocketChannel;
import 'package:web_socket_channel/web_socket_channel.dart';

import '../config/hub_config.dart';
import 'models.dart';

/// Talks to the Pathfinder God hub over HTTP + WebSocket.
class HubClient {
  final HubConfig config;
  final http.Client _http;

  HubClient(this.config, {http.Client? httpClient})
      : _http = httpClient ?? http.Client();

  Future<HubHealth> health() async {
    final resp = await _http
        .get(config.httpUri('/health'))
        .timeout(const Duration(seconds: 6));
    _ensureOk(resp);
    return HubHealth.fromJson(jsonDecode(resp.body) as Map<String, dynamic>);
  }

  /// General GM Q&A / generation (buffered).
  Future<AskResponse> ask(
      String query, {
        String edition = 'both',
        String? mode,
        List<List<String>> history = const [],
      }) async {
    final resp = await _http.post(
      config.httpUri('/ask'),
      headers: const {'Content-Type': 'application/json'},
      body: jsonEncode({
        'query': query,
        'edition': edition,
        'mode': mode,
        'history': history,
      }),
    );
    _ensureOk(resp);
    return AskResponse.fromJson(jsonDecode(resp.body) as Map<String, dynamic>);
  }

  /// Typed generator: character | npc | monster | boss | map | campaign | encounter.
  Future<AskResponse> generate(
      String kind,
      String prompt, {
        String edition = 'both',
      }) async {
    final resp = await _http.post(
      config.httpUri('/generate/$kind'),
      headers: const {'Content-Type': 'application/json'},
      body: jsonEncode({'prompt': prompt, 'edition': edition}),
    );
    _ensureOk(resp);
    return AskResponse.fromJson(jsonDecode(resp.body) as Map<String, dynamic>);
  }

  /// Raw rule/bestiary lookup (no LLM).
  Future<List<RuleHit>> searchRules(
      String query, {
        String edition = 'both',
        int limit = 10,
      }) async {
    final resp = await _http.get(
      config.httpUri('/rules/search', {'q': query, 'edition': edition, 'limit': limit}),
    );
    _ensureOk(resp);
    final body = jsonDecode(resp.body) as Map<String, dynamic>;
    return (body['results'] as List<dynamic>)
        .map((e) => RuleHit.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// Campaign export — full DB dump for backup (hub online only).
  Future<Map<String, dynamic>> exportCampaign(int campaignId) async {
    final resp = await _http.get(config.httpUri('/campaign/export', {'campaign_id': campaignId}));
    _ensureOk(resp);
    return jsonDecode(resp.body) as Map<String, dynamic>;
  }

  /// Campaign import — restores from backup (merges by id/name).
  Future<void> importCampaign(Map<String, dynamic> payload) async {
    final resp = await _http.post(
      config.httpUri('/campaign/import'),
      headers: const {'Content-Type': 'application/json'},
      body: jsonEncode(payload),
    );
    _ensureOk(resp);
  }

  /// Live token stream. Yields [StreamEvent]s (start → chunk… → end).
  ///
  /// Auto-reconnects on abnormal drops (device sleep, Wi-Fi switch, hub
  /// restart) up to [maxRetries] times with exponential backoff. The hub
  /// regenerates the answer after a mid-stream reconnect, so a `retrying`
  /// frame is emitted first — listeners should clear any partial text.
  /// Emits an `error` frame (instead of throwing) when retries are exhausted.
  /// Creates a WS channel with 15 s pingInterval to survive Doze/LAN roam.
  /// On Android/iOS uses IOWebSocketChannel with native ping; on web falls back.
  WebSocketChannel _connectWs(Uri uri) {
    if (!kIsWeb && (Platform.isAndroid || Platform.isIOS || Platform.isMacOS || Platform.isLinux || Platform.isWindows)) {
      try {
        return IOWebSocketChannel.connect(
          uri,
          pingInterval: const Duration(seconds: 15),
          headers: {'Origin': 'http://localhost'},
        );
      } catch (_) {
        // Fallback if platform channel fails
      }
    }
    return WebSocketChannel.connect(uri);
  }

  Stream<StreamEvent> stream(
    String query, {
    String edition = 'both',
    String? mode,
    List<List<String>> history = const [],
    int maxRetries = 3,
  }) async* {
    var attempt = 0;
    // Preserve history across reconnects so hub can reconstruct context window
    // (Guide chatbot previously kept this only in-memory StreamController).
    final effectiveHistory = List<List<String>>.from(history);
    while (true) {
      WebSocketChannel? channel;
      try {
        channel = _connectWs(config.wsUri('/stream'));
        await channel.ready;
        channel.sink.add(jsonEncode({
          'query': query,
          'edition': edition,
          'mode': mode,
          'history': effectiveHistory,
        }));

        var sawTerminalFrame = false;
        await for (final raw in channel.stream) {
          final event = StreamEvent.fromJson(
            jsonDecode(raw as String) as Map<String, dynamic>,
          );
          yield event;
          if (event.type == 'end' || event.type == 'error') {
            sawTerminalFrame = true;
            await channel.sink.close();
            break;
          }
        }
        if (sawTerminalFrame) return;
      } catch (e) {
        debugPrint('HubClient.stream attempt $attempt failed: $e');
        // Connection refused / reset / ready failed → retry below.
      } finally {
        try {
          await channel?.sink.close();
        } catch (_) {/* already closed */}
      }

      if (attempt >= maxRetries) {
        yield StreamEvent(
          type: 'error',
          message: 'Connection lost after ${attempt + 1} attempts. '
              'Check the hub is running at ${config.baseUrl}.',
        );
        return;
      }
      attempt += 1;
      yield StreamEvent(
        type: 'retrying',
        message: 'Connection lost — reconnecting (attempt $attempt of $maxRetries)…',
      );
      await Future<void>.delayed(Duration(milliseconds: 400 * (1 << (attempt - 1))));
    }
  }

  /// On-demand fetch: ask the hub to scrape one missing term into the
  /// database permanently. Throws [HubException] (404) when not fetchable —
  /// the query is then queued for the chunked backfill instead.
  Future<RuleHit> fetchRule(
    String query, {
    String edition = 'both',
  }) async {
    final resp = await _http.post(
      config.httpUri('/rules/fetch'),
      headers: const {'Content-Type': 'application/json'},
      body: jsonEncode({'q': query, 'edition': edition}),
    );
    _ensureOk(resp);
    return RuleHit.fromJson(jsonDecode(resp.body) as Map<String, dynamic>);
  }

  /// Drain the offline miss queue into the hub's backfill list.
  /// Returns the number the hub accepted.
  Future<int> reportMisses(List<Map<String, String>> queries) async {
    final resp = await _http.post(
      config.httpUri('/rules/missed'),
      headers: const {'Content-Type': 'application/json'},
      body: jsonEncode({
        'queries':
            queries.map((m) => {'q': m['q'] ?? '', 'edition': m['edition'] ?? 'both'}).toList(),
      }),
    );
    _ensureOk(resp);
    return (jsonDecode(resp.body) as Map<String, dynamic>)['queued'] as int? ?? 0;
  }

  /// Build a character via LLM + Rules Lawyer validation.
  /// Returns the validated character JSON or errors.
  Future<Map<String, dynamic>> buildCharacter(String prompt) async {
    final resp = await _http.post(
      config.httpUri('/generate/character'),
      headers: const {'Content-Type': 'application/json'},
      body: jsonEncode({'prompt': prompt}),
    );
    _ensureOk(resp);
    return jsonDecode(resp.body) as Map<String, dynamic>;
  }

  /// Resolve a strike via deterministic PF2e math.
  Future<Map<String, dynamic>> resolveStrike({
    required int attackRoll,
    required int targetAc,
    required int damageRoll,
    required int targetHp,
    int targetTempHp = 0,
  }) async {
    final resp = await _http.post(
      config.httpUri('/combat/resolve-strike'),
      headers: const {'Content-Type': 'application/json'},
      body: jsonEncode({
        'attack_roll': attackRoll,
        'target_ac': targetAc,
        'damage_roll': damageRoll,
        'target_hp': targetHp,
        'target_temp_hp': targetTempHp,
      }),
    );
    _ensureOk(resp);
    return jsonDecode(resp.body) as Map<String, dynamic>;
  }

  /// Process end-of-turn condition updates.
  Future<List<Map<String, dynamic>>> endTurnConditions(
      List<Map<String, dynamic>> conditions) async {
    final resp = await _http.post(
      config.httpUri('/combat/end-turn'),
      headers: const {'Content-Type': 'application/json'},
      body: jsonEncode({'conditions': conditions}),
    );
    _ensureOk(resp);
    final body = jsonDecode(resp.body) as Map<String, dynamic>;
    return (body['conditions'] as List<dynamic>)
        .map((e) => e as Map<String, dynamic>)
        .toList();
  }

  void _ensureOk(http.Response resp) {
    if (resp.statusCode < 200 || resp.statusCode >= 300) {
      throw HubException('Hub returned ${resp.statusCode}: ${resp.body}');
    }
  }

  void close() => _http.close();
}

class HubException implements Exception {
  final String message;
  HubException(this.message);
  @override
  String toString() => message;
}