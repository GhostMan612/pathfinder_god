// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';

import '../api/hub_client.dart';
import '../models/character.dart';
import '../storage/character_store.dart';

/// Backup spec v1 — JSON (single object) and JSONL (line-delimited) both accepted.
///
/// {
///   "version": 1,
///   "exported_at": "2026-08-30T12:00:00.000Z",
///   "app": "pathfinder_god",
///   "characters": [ Character.toMap(), ... ],
///   "campaign": { hub /campaign/export payload | null }
/// }
///
/// Campaign payload (hub):
/// {
///   "campaigns": [{id,name,edition,created_at,updated_at}],
///   "sessions": [{... facts_json ...}],
///   "npcs": [...], "locations": [...], "items": [...],
///   "quests": [...], "player_decisions": [...], "party_members": [...]
/// }
///
/// JSONL variant: file extension .jsonl → each line is one Character.toMap() JSON object.
/// Hub campaign JSONL not used — campaign always JSON.
class BackupService {
  final CharacterStore store;
  final HubClient? hub;
  static const int version = 1;

  BackupService(this.store, {this.hub});

  // ── Characters ──────────────────────────────────────────────

  Future<List<Character>> _allCharacters() => store.all();

  Map<String, dynamic> _bundle({
    required List<Character> chars,
    Map<String, dynamic>? campaign,
  }) {
    return {
      'version': version,
      'exported_at': DateTime.now().toUtc().toIso8601String(),
      'app': 'pathfinder_god',
      'platform': 'spoke',
      'characters': chars.map((c) => c.toMap()).toList(),
      'campaign': campaign,
    };
  }

  Future<File> _writeJson(Map<String, dynamic> bundle, String name) async {
    final dir = await getTemporaryDirectory();
    final file = File(p.join(dir.path, name));
    await file.writeAsString(jsonEncode(bundle), flush: true);
    return file;
  }

  Future<File> _writeJsonl(List<Character> chars, String name) async {
    final dir = await getTemporaryDirectory();
    final file = File(p.join(dir.path, name));
    final sink = file.openWrite();
    for (final c in chars) {
      sink.writeln(jsonEncode(c.toMap()));
    }
    await sink.close();
    return file;
  }

  /// Export only characters to JSON. Returns temp file handle.
  Future<File> exportCharacters({bool jsonl = false}) async {
    final chars = await _allCharacters();
    final stamp = DateTime.now().toUtc().toIso8601String().replaceAll(':', '-').split('.').first;
    if (jsonl) {
      debugPrint('BackupService: exporting ${chars.length} chars → JSONL');
      return _writeJsonl(chars, 'pathfinder_chars_$stamp.jsonl');
    }
    debugPrint('BackupService: exporting ${chars.length} chars → JSON');
    return _writeJson(_bundle(chars: chars), 'pathfinder_chars_$stamp.json');
  }

  /// Import characters from a JSON or JSONL file. Returns count imported.
  /// Non-destructive: upserts by id (if id present) else inserts.
  /// JSONL path uses streaming LineSplitter (8KB chunks, constant RAM) for large files.
  Future<int> importCharacters(File file) async {
    if (file.path.endsWith('.jsonl')) {
      var count = 0;
      // Streaming — never loads whole file (Gemini §backup-1)
      final stream = file.openRead().transform(utf8.decoder).transform(const LineSplitter());
      await for (final line in stream) {
        if (line.trim().isEmpty) continue;
        final decoded = jsonDecode(line);
        if (decoded is! Map) continue;
        final map = Map<String, Object?>.from(decoded as Map<String, dynamic>);
        final c = Character.fromMap(map);
        // Use native UPSERT to avoid DELETE+INSERT cascade if FKs ever added (Gemini §backup-2)
        await store.upsertRaw(c);
        count++;
      }
      debugPrint('BackupService: streamed $count characters from ${file.path}');
      return count;
    }
    final text = await file.readAsString();
    List<dynamic> rawList;
    final decoded = jsonDecode(text);
    if (decoded is List) {
      rawList = decoded;
    } else if (decoded is Map<String, dynamic>) {
      // bundle form
      final chars = decoded['characters'];
      if (chars is List) {
        rawList = chars;
      } else {
        throw FormatException('Bundle missing characters array');
      }
    } else {
      throw FormatException('Unknown JSON top-level ${decoded.runtimeType}');
    }
    var count = 0;
    for (final raw in rawList) {
      if (raw is! Map) continue;
      final map = Map<String, Object?>.from(raw as Map<String, dynamic>);
      final c = Character.fromMap(map);
      await store.upsertRaw(c);
      count++;
    }
    debugPrint('BackupService: imported $count characters from ${file.path}');
    return count;
  }

  // ── Full backup (characters + hub campaign if reachable) ──────

  Future<File> exportAll({int campaignId = 1, bool jsonl = false}) async {
    final chars = await _allCharacters();
    Map<String, dynamic>? campaign;
    if (hub != null) {
      try {
        campaign = await hub!.exportCampaign(campaignId);
        debugPrint('BackupService: hub campaign exported ${campaign.keys}');
      } catch (e) {
        debugPrint('BackupService: hub campaign export failed (offline?) $e');
        campaign = null;
      }
    }
    final stamp = DateTime.now().toUtc().toIso8601String().replaceAll(':', '-').split('.').first;
    if (jsonl && campaign == null) {
      return _writeJsonl(chars, 'pathfinder_backup_${stamp}_chars.jsonl');
    }
    return _writeJson(_bundle(chars: chars, campaign: campaign), 'pathfinder_backup_$stamp.json');
  }

  /// Import full backup (characters always, campaign if present + hub reachable).
  /// Returns {'characters': n, 'campaign': bool}
  Future<Map<String, dynamic>> importAll(File file) async {
    final text = await file.readAsString();
    final decoded = jsonDecode(text) as Map<String, dynamic>;
    final ver = decoded['version'] as int? ?? 1;
    if (ver != version) {
      debugPrint('BackupService: version mismatch $ver vs $version — attempting anyway');
    }
    var charCount = 0;
    final chars = decoded['characters'];
    if (chars is List) {
      for (final raw in chars) {
        if (raw is! Map) continue;
        final c = Character.fromMap(Map<String, Object?>.from(raw as Map<String, dynamic>));
        await store.upsert(c);
        charCount++;
      }
    }
    var campaignOk = false;
    final campaign = decoded['campaign'];
    if (campaign is Map<String, dynamic> && hub != null) {
      try {
        await hub!.importCampaign(campaign);
        campaignOk = true;
      } catch (e) {
        debugPrint('BackupService: hub campaign import failed $e');
      }
    }
    debugPrint('BackupService: importAll chars=$charCount campaignOk=$campaignOk');
    return {'characters': charCount, 'campaign': campaignOk, 'version': ver};
  }
}
