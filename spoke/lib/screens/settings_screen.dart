// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

import 'dart:io';

import 'package:file_picker/file_picker.dart' as fp;
import 'package:flutter/material.dart';
import 'package:share_plus/share_plus.dart';

import '../api/hub_client.dart';
import '../api/models.dart';
import '../services/audio_service.dart';
import '../services/backup_service.dart';
import '../services/haptics_service.dart';
import '../storage/character_store.dart';
import '../theme/app_theme.dart';

/// Configure the hub address and check the connection.
class SettingsScreen extends StatefulWidget {
  final HubClient client;
  final CharacterStore characters;
  const SettingsScreen({super.key, required this.client, required this.characters});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  late final TextEditingController _url;
  HubHealth? _health;
  String? _error;
  bool _checking = false;
  bool _backupBusy = false;
  String? _backupMsg;

  @override
  void initState() {
    super.initState();
    _url = TextEditingController(text: widget.client.config.baseUrl);
  }

  @override
  void dispose() {
    _url.dispose();
    super.dispose();
  }

  Future<void> _saveAndCheck() async {
    final raw = _url.text.trim();
    // Common mistake: typing Ollama's port (11450) instead of the hub (8000).
    // Ollama's /health doesn't exist → 404 page not found. Hint early.
    if (raw.contains(':11450')) {
      setState(() {
        _checking = false;
        _health = null;
        _error =
            'That port (11450) is Ollama, not the hub.\nUse the hub port 8000, e.g. http://192.168.4.144:8000.\nHub returned 404: 404 page not found';
      });
      await widget.client.config.save(raw.replaceAll(':11450', ':8000'));
      _url.text = raw.replaceAll(':11450', ':8000');
      return;
    }
    await widget.client.config.save(raw);
    setState(() { _checking = true; _error = null; _health = null; });
    try {
      final h = await widget.client.health();
      if (mounted) setState(() => _health = h);
    } catch (e) {
      var msg = '$e';
      if (msg.contains('404')) {
        msg += '\n\nHint: hub is on :8000, not :11450 (Ollama). Try http://192.168.4.144:8000';
      }
      if (mounted) setState(() => _error = msg);
    } finally {
      if (mounted) setState(() => _checking = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Setup')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text('Hub address', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 4),
          const Text(
            'Your laptop\'s address on the same Wi-Fi, e.g. http://192.168.4.144:8000. '
            '(Android emulator: http://10.0.2.2:8000.)\n'
            'Hub = :8000. Ollama is :11450 — don\'t put 11450 here.',
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _url,
            keyboardType: TextInputType.url,
            decoration: const InputDecoration(
              labelText: 'Base URL',
              border: OutlineInputBorder(),
              isDense: true,
            ),
          ),
          const SizedBox(height: 12),
          FilledButton.icon(
            onPressed: _checking ? null : _saveAndCheck,
            icon: _checking
                ? const SizedBox(height: 18, width: 18, child: CircularProgressIndicator(strokeWidth: 2))
                : const Icon(Icons.wifi_tethering),
            label: const Text('Save & test connection'),
          ),
          const SizedBox(height: 20),
          if (_error != null)
            Card(
              color: PathfinderTheme.crimson,
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Text('Could not reach the God.\n\n$_error',
                    style: const TextStyle(color: PathfinderTheme.parchment)),
              ),
            ),
          if (_health != null) _healthCard(_health!),
          const SizedBox(height: 24),
          const Divider(),
          Text('Sound', style: Theme.of(context).textTheme.titleMedium),
          SwitchListTile(
            secondary: const Icon(Icons.music_note),
            title: const Text('Background music'),
            subtitle: const Text('Quiet tavern ambience, loops offline'),
            value: AudioService.instance.musicEnabled,
            onChanged: (v) {
              AudioService.instance.setMusicEnabled(v);
              setState(() {});
            },
          ),
          SwitchListTile(
            secondary: const Icon(Icons.volume_up),
            title: const Text('Sound effects'),
            subtitle: const Text('Dice, crits, and UI clicks'),
            value: AudioService.instance.sfxEnabled,
            onChanged: (v) {
              AudioService.instance.setSfxEnabled(v);
              setState(() {});
            },
          ),
          SwitchListTile(
            secondary: const Icon(Icons.vibration),
            title: const Text('Haptic feedback'),
            subtitle: const Text('Vibration on dice rolls and UI interactions'),
            value: HapticsService.enabled,
            onChanged: (v) {
              HapticsService.setEnabled(v);
              setState(() {});
            },
          ),
          const Divider(),
          Text('Backup & Restore', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 4),
          const Text('Export your characters + campaign. JSON bundle or JSONL characters. Works offline; full backup includes hub campaign when online.'),
          const SizedBox(height: 12),
          Wrap(spacing: 8, runSpacing: 8, children: [
            FilledButton.icon(
              icon: const Icon(Icons.upload),
              label: const Text('Export Characters'),
              onPressed: _backupBusy ? null : () => _doExport(jsonl: false, all: false),
            ),
            OutlinedButton.icon(
              icon: const Icon(Icons.archive),
              label: const Text('Export All'),
              onPressed: _backupBusy ? null : () => _doExport(jsonl: false, all: true),
            ),
            OutlinedButton.icon(
              icon: const Icon(Icons.list_alt),
              label: const Text('Export JSONL'),
              onPressed: _backupBusy ? null : () => _doExport(jsonl: true, all: false),
            ),
            FilledButton.icon(
              icon: const Icon(Icons.download),
              label: const Text('Import'),
              onPressed: _backupBusy ? null : _doImport,
            ),
          ]),
          if (_backupBusy) const Padding(padding: EdgeInsets.only(top: 12), child: LinearProgressIndicator()),
          if (_backupMsg != null)
            Padding(
              padding: const EdgeInsets.only(top: 12),
              child: Card(
                color: _backupMsg!.startsWith('✅') ? Colors.green.shade50 : PathfinderTheme.parchmentDeep,
                child: Padding(padding: const EdgeInsets.all(12), child: Text(_backupMsg!, style: const TextStyle(fontSize: 13))),
              ),
            ),
          const SizedBox(height: 12),
          const Divider(),
          const ListTile(
            leading: Icon(Icons.info_outline),
            title: Text('Pathfinder God'),
            subtitle: Text('The companion app (spoke). The laptop hub does the heavy lifting.'),
          ),
        ],
      ),
    );
  }

  Widget _healthCard(HubHealth h) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(children: const [
              Icon(Icons.check_circle, color: Colors.green),
              SizedBox(width: 8),
              Text('Connected to the God', style: TextStyle(fontWeight: FontWeight.bold)),
            ]),
            const SizedBox(height: 8),
            Text('Hub version: ${h.version}'),
            Text('Local model: ${h.ollamaModel}'),
            Text('Databases found: ${h.databasesFound.isEmpty ? "none!" : h.databasesFound.join(", ")}'),
          ],
        ),
      ),
    );
  }

  Future<void> _doExport({required bool jsonl, required bool all}) async {
    setState(() { _backupBusy = true; _backupMsg = null; });
    try {
      final svc = BackupService(widget.characters, hub: widget.client);
      final File file = all ? await svc.exportAll(jsonl: jsonl) : await svc.exportCharacters(jsonl: jsonl);
      if (!mounted) return;
      final len = await file.length();
      // Share via system sheet (user can Save to Downloads, Drive, etc.)
      await SharePlus.instance.share(ShareParams(files: [XFile(file.path)], text: 'Pathfinder God backup ${file.path.split('/').last}'));
      if (!mounted) return;
      setState(() => _backupMsg = '✅ Exported ${file.path.split('/').last} ($len bytes) — share sheet opened. File also at ${file.path}');
    } catch (e) {
      if (mounted) setState(() => _backupMsg = '❌ Export failed: $e');
    } finally {
      if (mounted) setState(() => _backupBusy = false);
    }
  }

  Future<void> _doImport() async {
    setState(() { _backupBusy = true; _backupMsg = null; });
    try {
      final files = await fp.FilePicker.pickFiles(
        type: fp.FileType.custom,
        allowedExtensions: ['json', 'jsonl'],
      );
      if (files.isEmpty) {
        setState(() => _backupBusy = false);
        return;
      }
      final path = files.first.path;
      if (path == null) {
        setState(() => _backupBusy = false);
        return;
      }
      final file = File(path);
      final svc = BackupService(widget.characters, hub: widget.client);
      final isJsonl = file.path.endsWith('.jsonl');
      Map<String, dynamic> res;
      if (isJsonl) {
        final n = await svc.importCharacters(file);
        res = {'characters': n, 'campaign': false};
      } else {
        // Try full bundle first, fallback to chars-only
        try {
          res = await svc.importAll(file);
          if ((res['characters'] as int) == 0) {
            final n = await svc.importCharacters(file);
            res = {'characters': n, 'campaign': false};
          }
        } catch (_) {
          final n = await svc.importCharacters(file);
          res = {'characters': n, 'campaign': false};
        }
      }
      if (!mounted) return;
      setState(() => _backupMsg = '✅ Imported ${res['characters']} characters${(res['campaign'] as bool) ? ' + campaign' : ''} from ${file.path.split('/').last}');
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Imported ${res['characters']} characters')));
    } catch (e) {
      if (mounted) setState(() => _backupMsg = '❌ Import failed: $e');
    } finally {
      try { await fp.FilePicker.clearTemporaryFiles(); } catch (_) {}
      if (mounted) setState(() => _backupBusy = false);
    }
  }
}
