// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

import 'dart:io';

import 'package:file_picker/file_picker.dart' as fp;
import 'package:flutter/material.dart';
import 'package:share_plus/share_plus.dart';

import '../api/hub_client.dart';
import '../models/character.dart';
import '../services/backup_service.dart';
import '../storage/character_store.dart';
import '../theme/app_theme.dart';
import 'character_sheet_screen.dart';

/// Lists the player's saved characters (stored locally on the phone).
class CharacterListScreen extends StatefulWidget {
  final HubClient client;
  final CharacterStore store;
  const CharacterListScreen({super.key, required this.client, required this.store});

  @override
  State<CharacterListScreen> createState() => _CharacterListScreenState();
}

class _CharacterListScreenState extends State<CharacterListScreen> {
  List<Character> _characters = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _reload();
  }

  Future<void> _reload() async {
    setState(() => _loading = true);
    final list = await widget.store.all();
    if (mounted) setState(() { _characters = list; _loading = false; });
  }

  Future<void> _open(Character? character) async {
    await Navigator.of(context).push(MaterialPageRoute(
      builder: (_) => CharacterSheetScreen(
        client: widget.client,
        store: widget.store,
        initial: character,
      ),
    ));
    _reload();
  }

  Future<void> _export() async {
    try {
      final svc = BackupService(widget.store, hub: widget.client);
      final file = await svc.exportCharacters();
      if (!mounted) return;
      await SharePlus.instance.share(ShareParams(files: [XFile(file.path)], text: 'My Heroes backup'));
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Exported ${file.path.split('/').last}')));
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Export failed: $e')));
    }
  }

  Future<void> _import() async {
    try {
      final files = await fp.FilePicker.pickFiles(type: fp.FileType.custom, allowedExtensions: ['json', 'jsonl']);
      if (files.isEmpty) return;
      final path = files.first.path;
      if (path == null) return;
      final file = File(path);
      final svc = BackupService(widget.store, hub: widget.client);
      final n = file.path.endsWith('.jsonl') ? await svc.importCharacters(file) : (await svc.importAll(file))['characters'] as int;
      await _reload();
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Imported $n heroes')));
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Import failed: $e')));
    } finally {
      try { await fp.FilePicker.clearTemporaryFiles(); } catch (_) {}
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('My Heroes'),
        actions: [
          IconButton(icon: const Icon(Icons.upload), tooltip: 'Export', onPressed: _export),
          IconButton(icon: const Icon(Icons.download), tooltip: 'Import', onPressed: _import),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        heroTag: null,
        onPressed: () => _open(null),
        icon: const Icon(Icons.add),
        label: const Text('New'),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _characters.isEmpty
              ? const Center(child: Text('No characters yet. Tap "New" to forge one.'))
              : ListView.separated(
                  itemCount: _characters.length,
                  separatorBuilder: (_, _) => const Divider(height: 1),
                  itemBuilder: (context, i) {
                    final c = _characters[i];
                    final d = c.recalculateDerived().derived;
                    final subtitle = [
                      if (c.ancestry.isNotEmpty) c.ancestry,
                      if (c.heritage.isNotEmpty) c.heritage,
                      if (c.characterClass.isNotEmpty) c.characterClass,
                      if (c.subclass.isNotEmpty) c.subclass,
                    ].join(' · ');
                    return ListTile(
                      leading: CircleAvatar(
                        backgroundColor: PathfinderTheme.crimson,
                        child: Text('${c.level}',
                            style: const TextStyle(color: PathfinderTheme.parchment, fontWeight: FontWeight.bold)),
                      ),
                      title: Text(c.name,
                          style: const TextStyle(fontWeight: FontWeight.bold)),
                      subtitle: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          if (subtitle.isNotEmpty)
                            Text(subtitle,
                                style: TextStyle(color: Colors.grey[600])),
                          Text('HP ${d.hp}/${d.maxHp} · AC ${d.ac} · Spd ${d.speed} ft',
                              style: TextStyle(fontSize: 12, color: Colors.grey[500])),
                        ],
                      ),
                      trailing: const Icon(Icons.chevron_right),
                      onTap: () => _open(c),
                    );
                  },
                ),
    );
  }
}