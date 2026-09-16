// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

import 'package:path/path.dart' as p;
import 'package:sqflite/sqflite.dart';

import '../models/character.dart';

/// Local SQLite storage for the player's own characters.
///
/// This is a *tiny* database on the phone — the 500MB+ rules DB stays on the
/// laptop hub and is queried over the network, never stored here.
class CharacterStore {
  Database? _db;

  static const _dbName = 'pathfinder_spoke.db';
  static const _dbVersion = 3;

  Future<Database> _open() async {
    if (_db != null) return _db!;
    final dir = await getDatabasesPath();
    _db = await openDatabase(
      p.join(dir, _dbName),
      version: _dbVersion,
      onCreate: (db, version) async {
        await _createTables(db);
      },
      onUpgrade: (db, oldVersion, newVersion) async {
        if (oldVersion < 2) {
          await _migrateToV2(db);
        }
        if (oldVersion < 3) {
          await _migrateToV3(db);
        }
      },
    );
    return _db!;
  }

  Future<void> _createTables(Database db) async {
    await db.execute('''
      CREATE TABLE characters (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        ancestry TEXT,
        heritage TEXT,
        background TEXT,
        character_class TEXT,
        subclass TEXT,
        level INTEGER DEFAULT 1,
        deity TEXT,
        alignment TEXT,
        size TEXT,
        gender TEXT,
        age INTEGER,
        eyes TEXT,
        hair TEXT,
        height TEXT,
        weight TEXT,
        languages TEXT,
        senses TEXT,
        speed TEXT,
        portrait_path TEXT,
        abilities TEXT,
        proficiencies TEXT,
        feats TEXT,
        spellcasting TEXT,
        equipment TEXT,
        derived TEXT,
        conditions TEXT,
        notes TEXT
      )
    ''');
  }

  Future<void> _migrateToV2(Database db) async {
    await db.execute('ALTER TABLE characters ADD COLUMN heritage TEXT');
    await db.execute('ALTER TABLE characters ADD COLUMN subclass TEXT');
    await db.execute('ALTER TABLE characters ADD COLUMN deity TEXT');
    await db.execute('ALTER TABLE characters ADD COLUMN alignment TEXT');
    await db.execute('ALTER TABLE characters ADD COLUMN size TEXT');
    await db.execute('ALTER TABLE characters ADD COLUMN gender TEXT');
    await db.execute('ALTER TABLE characters ADD COLUMN age INTEGER');
    await db.execute('ALTER TABLE characters ADD COLUMN eyes TEXT');
    await db.execute('ALTER TABLE characters ADD COLUMN hair TEXT');
    await db.execute('ALTER TABLE characters ADD COLUMN height TEXT');
    await db.execute('ALTER TABLE characters ADD COLUMN weight TEXT');
    await db.execute('ALTER TABLE characters ADD COLUMN languages TEXT');
    await db.execute('ALTER TABLE characters ADD COLUMN senses TEXT');
    await db.execute('ALTER TABLE characters ADD COLUMN speed TEXT');
    await db.execute('ALTER TABLE characters ADD COLUMN abilities TEXT');
    await db.execute('ALTER TABLE characters ADD COLUMN proficiencies TEXT');
    await db.execute('ALTER TABLE characters ADD COLUMN feats TEXT');
    await db.execute('ALTER TABLE characters ADD COLUMN spellcasting TEXT');
    await db.execute('ALTER TABLE characters ADD COLUMN equipment TEXT');
    await db.execute('ALTER TABLE characters ADD COLUMN derived TEXT');
    await db.execute('ALTER TABLE characters ADD COLUMN conditions TEXT');

    final rows = await db.query('characters');
    for (final row in rows) {
      final id = row['id'] as int;
      final updates = <String, dynamic>{};
      if (row['ancestry'] == null || (row['ancestry'] as String).isEmpty) {
        updates['ancestry'] = 'Human';
      }
      if (row['character_class'] == null || (row['character_class'] as String).isEmpty) {
        updates['character_class'] = 'Fighter';
      }
      if (row['level'] == null) {
        updates['level'] = 1;
      }
      if (row['abilities'] == null) {
        updates['abilities'] = AbilityScores().toJson();
      }
      if (row['proficiencies'] == null) {
        updates['proficiencies'] = Proficiencies().toJson();
      }
      if (row['feats'] == null) {
        updates['feats'] = '[]';
      }
      if (row['spellcasting'] == null) {
        updates['spellcasting'] = Spellcasting().toJson();
      }
      if (row['equipment'] == null) {
        updates['equipment'] = Equipment().toJson();
      }
      if (row['derived'] == null) {
        updates['derived'] = DerivedStats().toJson();
      }
      if (row['conditions'] == null) {
        updates['conditions'] = ConditionTrackers().toJson();
      }
      if (updates.isNotEmpty) {
        await db.update('characters', updates, where: 'id = ?', whereArgs: [id]);
      }
    }
  }

  Future<void> _migrateToV3(Database db) async {
    await db.execute('ALTER TABLE characters ADD COLUMN portrait_path TEXT');
  }

  Future<List<Character>> all() async {
    final db = await _open();
    final rows = await db.query('characters', orderBy: 'id DESC');
    return rows.map(Character.fromMap).toList();
  }

  Future<Character> upsert(Character c) async {
    final db = await _open();
    if (c.id == null) {
      final id = await db.insert('characters', c.toMap());
      return c.copyWith(id: id);
    }
    await db.update('characters', c.toMap(), where: 'id = ?', whereArgs: [c.id]);
    return c;
  }

  /// Native UPSERT (INSERT ... ON CONFLICT DO UPDATE) — avoids sqflite
  /// ConflictAlgorithm.replace which does DELETE+INSERT and would fire
  /// ON DELETE CASCADE on child FKs if we ever split feats/spells into tables.
  /// Currently entire sheet is a single JSON blob (no FKs), but this is
  /// future-proof and atomic for backup imports (Gemini §backup-2).
  Future<Character> upsertRaw(Character c) async {
    final db = await _open();
    final map = c.toMap();
    if (c.id == null) {
      map.remove('id');
      final id = await db.insert('characters', map);
      return c.copyWith(id: id);
    }
    // Build column lists for native UPSERT
    final cols = map.keys.toList();
    final placeholders = List.filled(cols.length, '?').join(', ');
    final updates = cols.where((k) => k != 'id').map((k) => '$k=excluded.$k').join(', ');
    final values = cols.map((k) => map[k]).toList();
    final sql = 'INSERT INTO characters (${cols.join(', ')}) VALUES ($placeholders) ON CONFLICT(id) DO UPDATE SET $updates';
    await db.rawInsert(sql, values);
    return c;
  }

  Future<void> delete(int id) async {
    final db = await _open();
    await db.delete('characters', where: 'id = ?', whereArgs: [id]);
  }
}