// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

import 'dart:convert';

import 'package:path/path.dart' as p;
import 'package:sqflite/sqflite.dart';

import '../models/campaign.dart';

/// Offline campaign persistence for the Moto G.
class CampaignStore {
  Database? _db;

  static const _dbName = 'pathfinder_campaigns.db';
  static const _dbVersion = 1;

  Future<Database> _open() async {
    if (_db != null) return _db!;
    final dir = await getDatabasesPath();
    _db = await openDatabase(
      p.join(dir, _dbName),
      version: _dbVersion,
      onCreate: (db, version) async {
        await db.execute('''
          CREATE TABLE campaigns (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            session_notes TEXT NOT NULL DEFAULT '[]',
            updated_at TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 0
          )
        ''');
      },
    );
    return _db!;
  }

  Future<CampaignModel> saveCampaign(CampaignModel campaign) async {
    final db = await _open();
    await db.transaction((txn) async {
      await txn.update('campaigns', {'is_active': 0});
      await txn.insert(
        'campaigns',
        {
          'id': campaign.id,
          'name': campaign.name,
          'description': campaign.description,
          'session_notes': jsonEncode(campaign.sessionNotes),
          'updated_at': campaign.updatedAt.toIso8601String(),
          'is_active': 1,
        },
        conflictAlgorithm: ConflictAlgorithm.replace,
      );
    });
    return campaign;
  }

  Future<CampaignModel?> getActiveCampaign() async {
    final db = await _open();
    final rows = await db.query(
      'campaigns',
      where: 'is_active = 1',
      orderBy: 'updated_at DESC',
      limit: 1,
    );
    if (rows.isEmpty) return null;
    return _fromRow(rows.first);
  }

  Future<CampaignModel?> addSessionNote(String note) async {
    final active = await getActiveCampaign();
    if (active == null) return null;
    final updated = active.withNote(note);
    final db = await _open();
    await db.update(
      'campaigns',
      {
        'session_notes': jsonEncode(updated.sessionNotes),
        'updated_at': updated.updatedAt.toIso8601String(),
      },
      where: 'id = ?',
      whereArgs: [updated.id],
    );
    return updated;
  }

  CampaignModel _fromRow(Map<String, Object?> row) => CampaignModel(
        id: row['id'] as String,
        name: row['name'] as String? ?? 'Untitled Campaign',
        description: row['description'] as String? ?? '',
        sessionNotes: (jsonDecode(row['session_notes'] as String? ?? '[]')
                as List<dynamic>)
            .map((e) => e as String)
            .toList(),
        updatedAt:
            DateTime.tryParse(row['updated_at'] as String? ?? '') ??
                DateTime.fromMillisecondsSinceEpoch(0, isUtc: true),
      );
}
