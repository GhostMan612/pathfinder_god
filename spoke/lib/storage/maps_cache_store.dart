// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

import 'dart:async';
import 'dart:convert';

import 'package:path/path.dart';
import 'package:sqflite/sqflite.dart';
import 'package:path_provider/path_provider.dart';

import '../models/encounter.dart';

/// Local cache for generated maps.
class MapsCacheStore {
  static final MapsCacheStore instance = MapsCacheStore._();
  MapsCacheStore._();

  Database? _db;

  Future<Database> get _database async {
    if (_db != null) return _db!;
    final dir = await getApplicationDocumentsDirectory();
    final path = '$dir${separator}maps_cache.db';
    _db = await openDatabase(
      path,
      version: 1,
      onCreate: _onCreate,
    );
    return _db!;
  }

  Future<void> _onCreate(Database db, int version) async {
    await db.execute('''
      CREATE TABLE maps (
        id TEXT PRIMARY KEY,
        prompt TEXT NOT NULL,
        base64_png TEXT NOT NULL,
        width INTEGER NOT NULL,
        height INTEGER NOT NULL,
        created_at TEXT NOT NULL
      )
    ''');
  }

  /// Save a generated map to the local cache.
  Future<void> saveMap({
    required String id,
    required String prompt,
    required String base64Png,
    required int width,
    required int height,
  }) async {
    final db = await _database;
    await db.insert(
      'maps',
      {
        'id': id,
        'prompt': prompt,
        'base64_png': base64Png,
        'width': width,
        'height': height,
        'created_at': DateTime.now().toIso8601String(),
      },
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  /// Load all cached maps, newest first.
  Future<List<CachedMap>> getMaps() async {
    final db = await _database;
    final rows = await db.query(
      'maps',
      orderBy: 'created_at DESC',
    );
    return rows.map((r) => CachedMap.fromMap(r)).toList();
  }

  /// Delete a cached map by ID.
  Future<void> deleteMap(String id) async {
    final db = await _database;
    await db.delete('maps', where: 'id = ?', whereArgs: [id]);
  }

  Future<void> close() async {
    await _db?.close();
    _db = null;
  }
}

/// A cached map entry.
class CachedMap {
  final String id;
  final String prompt;
  final String base64Png;
  final int width;
  final int height;
  final DateTime createdAt;

  const CachedMap({
    required this.id,
    required this.prompt,
    required this.base64Png,
    required this.width,
    required this.height,
    required this.createdAt,
  });

  factory CachedMap.fromMap(Map<String, dynamic> map) => CachedMap(
        id: map['id'] as String,
        prompt: map['prompt'] as String,
        base64Png: map['base64_png'] as String,
        width: map['width'] as int,
        height: map['height'] as int,
        createdAt: DateTime.parse(map['created_at'] as String),
      );

  Map<String, dynamic> toMap() => {
        'id': id,
        'prompt': prompt,
        'base64_png': base64Png,
        'width': width,
        'height': height,
        'created_at': createdAt.toIso8601String(),
      };
}