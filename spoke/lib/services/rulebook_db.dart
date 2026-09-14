// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

import 'dart:io';
import 'dart:isolate';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart' show MethodChannel, rootBundle;
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

/// One offline rules-search hit (mirrors the hub's RuleHit wire model).
class LocalRuleHit {
  final String name;
  final String content;
  final String system; // "1E" | "2E" as stored in the DB
  final String category;
  final String sourceBook;

  const LocalRuleHit({
    required this.name,
    required this.content,
    this.system = '',
    this.category = '',
    this.sourceBook = '',
  });
}

/// Offline Pathfinder rulebook backed by the bundled FTS5 database.
///
/// First launch: loads the gzip asset (~48MB) out of the APK and
/// decompresses it into app storage (~58MB). Every launch after that
/// opens the extracted file read-only — zero network, zero hub.
class RulebookDb {
  static const _assetPath = 'assets/rules/pathfinder_rag.db.gz';
  static const _dbFileName = 'pathfinder_rag.db';
  // Bump when you re-bundle a newer .gz so clients re-extract.
  static const int bundleVersion = 2;

  static const _channel = MethodChannel('com.pathfindergod/rulebook');

  static Database? _db;
  static Future<Database>? _openFuture;

  bool get isReady => _db != null;

  /// Open (extracting on first run) and return the database handle.
  /// Serialized so concurrent callers (e.g. Rulebook + Bestiary) don't
  /// trigger two 50 MB decompressions at once (OOM on moto g).
  Future<Database> open() async {
    if (_db != null) return _db!;
    if (_openFuture != null) return _openFuture!;
    _openFuture = _openInternal();
    try {
      return await _openFuture!;
    } finally {
      _openFuture = null;
    }
  }

  Future<Database> _openInternal() async {
    sqfliteFfiInit();
    final factory = databaseFactoryFfi;

    // Use app documents directory so sqflite_common_ffi gets a real
    // writable path on Android (its default getDatabasesPath() returns
    // a relative /.dart_tool/... path that the OS rejects – see log
    // "to /.dart_tool/sqflite_common_ffi/databases/...").
    final base = await getApplicationDocumentsDirectory();
    final dir = Directory(p.join(base.path, 'rulebook'));
    await dir.create(recursive: true);
    final dbPath = p.join(dir.path, _dbFileName);
    final markerPath = p.join(dir.path, '$_dbFileName.v$bundleVersion');
    debugPrint('RulebookDb: dir = ${dir.path}');
    debugPrint('RulebookDb: dbPath = $dbPath');

    if (!File(dbPath).existsSync() || !File(markerPath).existsSync()) {
      try {
        await _extract(dbPath);
      } catch (e, st) {
        debugPrint('RulebookDb: Extraction failed: $e\n$st');
        rethrow;
      }
      // Remove stale version markers from previous bundles.
      for (final e in dir.listSync()) {
        final name = p.basename(e.path);
        if (name.startsWith('$_dbFileName.v') && e.path != markerPath) {
          try {
            e.deleteSync();
          } catch (_) {/* best-effort cleanup */}
        }
      }
      await File(markerPath).create(recursive: true);
    }

    // Read-only: never mutate the shipped corpus on-device.
    try {
      _db = await factory.openDatabase(
        dbPath,
        options: OpenDatabaseOptions(readOnly: true),
      );
      debugPrint('RulebookDb: opened ${await _db!.rawQuery('SELECT count(*) as c FROM rules')}');
      return _db!;
    } catch (e, st) {
      debugPrint('RulebookDb: Failed to open database: $e\n$st');
      rethrow;
    }
  }

  Future<void> _extract(String dbPath) async {
    // Tier 0: Kotlin MethodChannel streaming (8 KB buffer, zero copy).
    // Bypasses rootBundle → ByteData → Isolate copy entirely.
    // Falls back to Dart+Isolate if native channel unavailable (tests, iOS, etc.).
    if (!kIsWeb && Platform.isAndroid) {
      try {
        debugPrint('RulebookDb: Trying MethodChannel streaming for $_assetPath -> $dbPath');
        final bytes = await _channel.invokeMethod<int>('extractGzAsset', {
          'assetPath': _assetPath,
          'destPath': dbPath,
        });
        debugPrint('RulebookDb: MethodChannel extraction complete ($bytes bytes)');
        return;
      } catch (e, st) {
        debugPrint('RulebookDb: MethodChannel failed, falling back to Dart+Isolate: $e\n$st');
      }
    }
    debugPrint('RulebookDb: Starting Dart extraction from $_assetPath to $dbPath');
    final data = await rootBundle.load(_assetPath);
    final compressed =
        data.buffer.asUint8List(data.offsetInBytes, data.lengthInBytes);
    debugPrint('RulebookDb: Loaded compressed asset (${compressed.length} bytes)');

    // Decompress off the UI thread – 50 MB → 132 MB on main thread
    // blocks the Choreographer for >3 s ("Skipped 227 frames!").
    List<int> decompressed;
    try {
      decompressed = await Isolate.run(() => gzip.decode(compressed));
    } catch (e) {
      debugPrint('RulebookDb: Isolate decode failed, fallback on main: $e');
      decompressed = gzip.decode(compressed);
    }
    debugPrint('RulebookDb: Decompressed to ${decompressed.length} bytes');

    final tmp = File('$dbPath.tmp');
    // Ensure parent exists (getApplicationDocumentsDirectory is recreated
    // after app clear-data).
    await tmp.parent.create(recursive: true);
    if (await tmp.exists()) await tmp.delete();
    await tmp.writeAsBytes(decompressed, flush: true);
    // Atomic move into place – avoids half-written DB on crash.
    if (await File(dbPath).exists()) await File(dbPath).delete();
    await tmp.rename(dbPath);
    debugPrint('RulebookDb: Dart extraction complete');
  }

  /// Full-text search mirroring the hub's edition fallback (2e first).
  Future<List<LocalRuleHit>> search(
    String query, {
    String edition = 'both',
    int limit = 20,
  }) async {
    final db = await open();

    final cleaned = query
        .replaceAll('"', '""')
        .replaceAll(RegExp(r'[^\w\s]'), ' ')
        .trim();
    if (cleaned.isEmpty) return const [];
    final match = cleaned.split(RegExp(r'\s+')).join(' OR ');

    final editions =
        edition == 'both' ? ['2E', '1E'] : [edition.toUpperCase()];

    final hits = <LocalRuleHit>[];
    final seen = <String>{};
    void take(List<Map<String, Object?>> rows) {
      for (final r in rows) {
        final key = ((r['name'] as String?) ?? '').trim().toLowerCase();
        if (key.isNotEmpty && seen.contains(key)) continue;
        if (key.isNotEmpty) seen.add(key);
        hits.add(LocalRuleHit(
          name: (r['name'] as String?) ?? '',
          content: (r['raw_content'] as String?) ?? '',
          system: (r['system'] as String?) ?? '',
          category: (r['category'] as String?) ?? '',
          sourceBook: (r['source_book'] as String?) ?? '',
        ));
      }
    }

    for (final ed in editions) {
      if (hits.length >= limit) break;
      // Tier 0: exact name match — "Flanking" returns Flanking first.
      take(await db.rawQuery(
        'SELECT system, category, name, source_book, raw_content '
        'FROM rules WHERE system = ? AND name = ? COLLATE NOCASE LIMIT ?',
        [ed, query.trim(), limit - hits.length],
      ));
      if (hits.length >= limit) break;
      // Tier 1: FTS5 over known-source rows.
      take(await db.rawQuery(
        'SELECT system, category, name, source_book, raw_content '
        'FROM rules WHERE system = ? AND rules MATCH ? '
        "AND source_book != 'Unknown Source' "
        'ORDER BY rank LIMIT ?',
        [ed, match, limit - hits.length],
      ));
      if (hits.length >= limit) break;
      // Tier 2: legacy Unknown Source rows.
      take(await db.rawQuery(
        'SELECT system, category, name, source_book, raw_content '
        'FROM rules WHERE system = ? AND rules MATCH ? '
        "AND source_book = 'Unknown Source' "
        'ORDER BY rank LIMIT ?',
        [ed, match, limit - hits.length],
      ));
    }
    return hits;
  }

  /// Category counts for the browse tab.
  Future<List<Map<String, dynamic>>> categories({String edition = '2e'}) async {
    final db = await open();
    final rows = await db.rawQuery(
      'SELECT category, COUNT(*) AS n FROM rules WHERE system = ? '
      'GROUP BY category ORDER BY n DESC',
      [edition.toUpperCase()],
    );
    return rows
        .map((r) => {'category': r['category'], 'count': r['n']})
        .toList();
  }

  Future<void> close() async {
    await _db?.close();
    _db = null;
  }
}