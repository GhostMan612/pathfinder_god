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

/// Local cache for generated encounters.
class EncounterStore {
  static final EncounterStore instance = EncounterStore._();
  EncounterStore._();

  Database? _db;

  Future<Database> get _database async {
    if (_db != null) return _db!;
    final dir = await getApplicationDocumentsDirectory();
    final path = '$dir${separator}encounters_cache.db';
    _db = await openDatabase(
      path,
      version: 1,
      onCreate: _onCreate,
    );
    return _db!;
  }

  Future<void> _onCreate(Database db, int version) async {
    await db.execute('''
      CREATE TABLE encounters (
        id TEXT PRIMARY KEY,
        theme TEXT NOT NULL,
        threat TEXT NOT NULL,
        monsters_json TEXT NOT NULL,
        target_xp INTEGER NOT NULL,
        created_at TEXT NOT NULL
      )
    ''');
  }

  /// Save a generated encounter to the local cache.
  Future<void> saveEncounter({
    required String id,
    required String theme,
    required String threat,
    required List<EncounterMonster> monsters,
    required int targetXp,
    required int totalXp,
    required int partyLevel,
    required int partySize,
  }) async {
    final db = await _database;
    final monstersJson = jsonEncode(
      monsters.map((m) => m.toJson()).toList(),
    );
    await db.insert(
      'encounters',
      {
        'id': id,
        'theme': theme,
        'threat': threat,
        'monsters_json': jsonEncode(monsters.map((m) => m.toJson()).toList()),
        'target_xp': targetXp,
        'created_at': DateTime.now().toIso8601String(),
      },
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  /// Load all cached encounters, newest first.
  Future<List<CachedEncounter>> getEncounters() async {
    final db = await _database;
    final rows = await db.query(
      'encounters',
      orderBy: 'created_at DESC',
    );
    return rows.map((r) => CachedEncounter.fromMap(r)).toList();
  }

  /// Delete a cached encounter by ID.
  Future<void> deleteEncounter(String id) async {
    final db = await _database;
    await db.delete('encounters', where: 'id = ?', whereArgs: [id]);
  }

  Future<void> close() async {
    await _db?.close();
    _db = null;
  }
}

/// A cached encounter entry.
class CachedEncounter {
  final String id;
  final String theme;
  final String threat;
  final List<EncounterMonster> monsters;
  final int targetXp;
  final DateTime createdAt;

  const CachedEncounter({
    required this.id,
    required this.theme,
    required this.threat,
    required this.monsters,
    required this.targetXp,
    required this.createdAt,
  });

  factory CachedEncounter.fromMap(Map<String, dynamic> map) => CachedEncounter(
        id: map['id'] as String,
        theme: map['theme'] as String,
        threat: map['threat'] as String,
        monsters: (jsonDecode(map['monsters_json'] as String) as List<dynamic>)
            .map((m) => EncounterMonster.fromJson(m as Map<String, dynamic>))
            .toList(),
        targetXp: map['target_xp'] as int,
        createdAt: DateTime.parse(map['created_at'] as String),
      );

  Map<String, dynamic> toMap() => {
        'id': id,
        'theme': theme,
        'threat': threat,
        'monsters_json': jsonEncode(monsters.map((m) => m.toJson()).toList()),
        'target_xp': targetXp,
        'created_at': createdAt.toIso8601String(),
      };
}