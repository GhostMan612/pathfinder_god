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
import '../config/hub_config.dart';
import '../services/audio_service.dart';
import '../services/backup_service.dart';
import '../services/haptics_service.dart';
import '../services/hub_discovery.dart';
import '../services/slm_guide.dart';
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
  bool _discovering = false;
  List<DiscoveredHub> _discovered = [];
  String? _discoverMsg;
  bool _slmBusy = false;
  bool _slmEnabled = false;
  bool _slmInstalled = false;
  String? _slmStatus;
  double? _slmProgress;
  String? _slmVerify;
  String? _slmSidePath;
  String? _slmSideInfo;
  late final TextEditingController _hfToken;

  @override
  void initState() {
    super.initState();
    _url = TextEditingController(text: widget.client.config.baseUrl);
    _hfToken = TextEditingController();
    _refreshSlm();
  }

  @override
  void dispose() {
    _url.dispose();
    _hfToken.dispose();
    super.dispose();
  }

  Future<void> _refreshSlm({bool preserveStatus = false}) async {
    try {
      final slm = SlmGuideService.instance;
      final enabled = await slm.enabled;
      final installed = await slm.isInstalled();
      _hfToken.text = await slm.token ?? '';
      final sidePath = await slm.sideLoadExpectedPath();
      final sideCheck = await slm.validateSideLoad();
      if (!mounted) return;
      setState(() {
        _slmEnabled = enabled;
        _slmInstalled = installed;
        _slmSidePath = sidePath;
        _slmSideInfo = sideCheck.exists
            ? 'Side-load file: ${SlmGuideService.formatBytes(sideCheck.sizeBytes)}${sideCheck.looksValid ? '' : ' (too small — expected ~2GB)'}'
            : 'No side-load file yet.';
        if (!preserveStatus) {
          _slmStatus = installed
              ? 'Ready — Guide answers on-device, fully offline.'
              : 'Not downloaded (~2GB, Wi-Fi recommended). Guide uses excerpts until then.';
        }
      });
    } catch (_) {}
  }

  Future<void> _verifySlmUrl() async {
    setState(() => _slmVerify = 'Checking model URL…');
    try {
      final slm = SlmGuideService.instance;
      await slm.setToken(_hfToken.text);
      final check = await slm.verifyModelUrl();
      if (!mounted) return;
      setState(() => _slmVerify = check.label);
    } catch (e) {
      if (mounted) setState(() => _slmVerify = 'Verify failed: $e');
    }
  }

  Future<void> _downloadSlm() async {
    setState(() {
      _slmBusy = true;
      _slmProgress = 0;
      _slmStatus = 'Downloading brain… keep the app open on Wi-Fi.';
    });
    var ok = false;
    try {
      final slm = SlmGuideService.instance;
      await slm.setToken(_hfToken.text);
      if (await slm.installSideLoaded()) {
        if (!mounted) return;
        ok = true;
        setState(() => _slmStatus = 'Ready — installed from side-load, fully offline.');
        return;
      }
      await for (final p in slm.downloadWithProgress()) {
        if (!mounted) return;
        setState(() {
          _slmProgress = p / 100.0;
          _slmStatus = p >= 100
              ? 'Finalizing brain…'
              : 'Downloading brain… $p% — keep the app open.';
        });
      }
      if (!mounted) return;
      ok = true;
      setState(() => _slmStatus = 'Ready — Guide answers on-device, fully offline.');
    } catch (e) {
      if (mounted) setState(() => _slmStatus = '$e');
    } finally {
      if (mounted) {
        setState(() {
          _slmBusy = false;
          _slmProgress = null;
        });
        _refreshSlm(preserveStatus: !ok);
      }
    }
  }

  Future<void> _deleteSlm() async {
    setState(() => _slmBusy = true);
    try {
      await SlmGuideService.instance.deleteModel();
    } finally {
      if (mounted) {
        setState(() => _slmBusy = false);
        _refreshSlm();
      }
    }
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
          const SizedBox(height: 8),
          OutlinedButton.icon(
            onPressed: (_checking || _discovering) ? null : _discover,
            icon: _discovering
                ? const SizedBox(height: 18, width: 18, child: CircularProgressIndicator(strokeWidth: 2))
                : const Icon(Icons.radar),
            label: const Text('Find hub automatically'),
          ),
          const SizedBox(height: 4),
          const Text(
            'No typing needed: the laptop announces itself on Wi-Fi. '
            'Also tries the laptop-hotspot gateway automatically.',
            style: TextStyle(fontSize: 12, color: Colors.grey),
          ),
          if (_discoverMsg != null)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Text(_discoverMsg!, style: const TextStyle(fontSize: 13)),
            ),
          for (final hub in _discovered)
            Card(
              child: ListTile(
                leading: const Icon(Icons.dns, color: PathfinderTheme.gold),
                title: Text(hub.name, style: const TextStyle(fontWeight: FontWeight.bold)),
                subtitle: Text(hub.detail),
                trailing: const Icon(Icons.chevron_right),
                onTap: () {
                  _url.text = hub.baseUrl;
                  _saveAndCheck();
                },
              ),
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
            subtitle: const Text('Royalty-free loops, plays offline'),
            value: AudioService.instance.musicEnabled,
            onChanged: (v) {
              AudioService.instance.setMusicEnabled(v);
              setState(() {});
            },
          ),
          ListTile(
            leading: const Icon(Icons.queue_music),
            title: const Text('Music track'),
            trailing: DropdownButton<int>(
              value: AudioService.instance.musicTrack,
              items: [
                for (var i = 0; i < AudioService.tracks.length; i++)
                  DropdownMenuItem(value: i, child: Text(AudioService.tracks[i])),
              ],
              onChanged: (v) {
                if (v == null) return;
                AudioService.instance.setMusicTrack(v);
                setState(() {});
              },
            ),
          ),
          ListTile(
            leading: const Icon(Icons.attribution),
            title: const Text('Audio credits'),
            subtitle: const Text('Royalty-free artists (tap to view)'),
            onTap: () => showDialog<void>(
              context: context,
              builder: (_) => AlertDialog(
                title: const Text('Audio credits'),
                content: const SingleChildScrollView(child: Text(kAudioCredits)),
                actions: [
                  TextButton(
                    onPressed: () => Navigator.pop(context),
                    child: const Text('Close'),
                  ),
                ],
              ),
            ),
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
          Text('Offline brain (SLM)', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 4),
          const Text(
            'A small on-device model that turns rulebook excerpts into real answers — '
            'no network at all. One-time ~2GB download (HuggingFace gated repo: accept '
            'the Gemma license, paste a token). Or side-load guide_model.task into app files.',
          ),
          const SizedBox(height: 8),
          if (_slmStatus != null) Text(_slmStatus!, style: const TextStyle(fontSize: 13)),
          SwitchListTile(
            secondary: const Icon(Icons.psychology),
            title: const Text('Use offline brain'),
            subtitle: const Text('Falls back to excerpts when off or missing'),
            value: _slmEnabled,
            onChanged: (v) async {
              await SlmGuideService.instance.setEnabled(v);
              if (mounted) setState(() => _slmEnabled = v);
            },
          ),
          TextField(
            controller: _hfToken,
            obscureText: true,
            decoration: const InputDecoration(
              labelText: 'HuggingFace token (for download only)',
              border: OutlineInputBorder(),
              isDense: true,
            ),
          ),
          const SizedBox(height: 8),
          if (_slmSidePath != null)
            SelectableText(
              'Side-load here: $_slmSidePath',
              style: const TextStyle(fontSize: 11, color: Colors.grey),
            ),
          if (_slmSideInfo != null)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text(_slmSideInfo!, style: const TextStyle(fontSize: 12)),
            ),
          const SizedBox(height: 8),
          Row(children: [
            Expanded(
              child: FilledButton.icon(
                onPressed: _slmBusy ? null : _downloadSlm,
                icon: const Icon(Icons.download),
                label: Text(_slmInstalled ? 'Re-download' : 'Download brain'),
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: OutlinedButton.icon(
                onPressed: (_slmBusy || !_slmInstalled) ? null : _deleteSlm,
                icon: const Icon(Icons.delete_outline),
                label: const Text('Delete'),
              ),
            ),
          ]),
          const SizedBox(height: 8),
          OutlinedButton.icon(
            onPressed: _slmBusy ? null : _verifySlmUrl,
            icon: const Icon(Icons.link),
            label: const Text('Verify model URL first'),
          ),
          if (_slmVerify != null)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Text(_slmVerify!, style: const TextStyle(fontSize: 13)),
            ),
          if (_slmBusy)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: _slmProgress == null
                  ? const LinearProgressIndicator()
                  : Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        LinearProgressIndicator(value: _slmProgress),
                        const SizedBox(height: 4),
                        Text('${((_slmProgress ?? 0) * 100).round()}% — resumable, keep app open',
                            style: const TextStyle(fontSize: 12)),
                      ],
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

  Future<void> _discover() async {
    setState(() { _discovering = true; _discoverMsg = null; _discovered = []; });
    try {
      final discovery = HubDiscovery();
      final mdns = await discovery.discoverMdns();
      final candidates = [
        ...mdns,
        ...discovery.staticCandidates(savedBaseUrl: widget.client.config.baseUrl),
      ];
      // Dedupe by baseUrl, probe in parallel, keep reachable hubs.
      final seen = <String>{};
      final unique = candidates.where((h) => seen.add(h.baseUrl)).toList();
      final probed = await Future.wait(unique.map((hub) async {
        try {
          final client = HubClient(HubConfig(hub.baseUrl));
          try {
            final health = await client.health();
            return (hub: hub, health: health);
          } finally {
            client.close();
          }
        } catch (_) {
          return null;
        }
      }));
      final healthy = probed.whereType<({DiscoveredHub hub, HubHealth health})>().toList();
      if (!mounted) return;
      setState(() {
        _discovered = healthy
            .map((e) => DiscoveredHub(
                  name: e.hub.name,
                  host: e.hub.host,
                  port: e.hub.port,
                  version: e.health.version,
                  model: e.health.ollamaModel,
                  viaMdns: e.hub.viaMdns,
                ))
            .toList();
        _discoverMsg = healthy.isEmpty
            ? 'No hub found. Start the hub on the laptop (Command Center → Start Hub), join the same Wi-Fi or the laptop hotspot, then try again.'
            : 'Found ${healthy.length} hub(s) — tap one to connect.';
      });
    } catch (e) {
      if (mounted) setState(() => _discoverMsg = 'Discovery failed: $e');
    } finally {
      if (mounted) setState(() => _discovering = false);
    }
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
