// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';

import '../api/hub_client.dart';
import '../services/export_service.dart';
import '../storage/maps_cache_store.dart';
import '../theme/app_theme.dart';
import '../widgets/rpg_panel.dart';

/// Map Maker — LLM prompt → dual-layer Pillow PNG → PDF share or vault.
class MapMakerScreen extends StatefulWidget {
  final HubClient client;
  const MapMakerScreen({super.key, required this.client});

  @override
  State<MapMakerScreen> createState() => _MapMakerScreenState();
}

class _MapMakerScreenState extends State<MapMakerScreen> {
  final _promptController = TextEditingController(
    text: 'A ruined tavern 30x30 with a cellar trapdoor',
  );
  bool _building = false;
  bool _gridEnabled = true;
  bool _showGmLayer = true;
  String? _error;
  String? _gmBase64Png;
  String? _playerBase64Png;
  int? _width;
  int? _height;
  List<MapRoom> _rooms = [];
  List<MapSecret> _secrets = [];

  bool get _hasMap => _gmBase64Png != null && _playerBase64Png != null;
  String get _activeBase64 =>
      _showGmLayer ? _gmBase64Png! : _playerBase64Png!;

  @override
  void dispose() {
    _promptController.dispose();
    super.dispose();
  }

  Future<void> _generate() async {
    final prompt = _promptController.text.trim();
    if (prompt.isEmpty) {
      setState(() => _error = 'Prompt required');
      return;
    }

    setState(() {
      _building = true;
      _error = null;
      _gmBase64Png = null;
      _playerBase64Png = null;
    });

    try {
      final result = await widget.client.generateMap(
        prompt,
        gridEnabled: _gridEnabled,
      );
      final valid = result['valid'] as bool? ?? false;

      if (!valid) {
        setState(() {
          _building = false;
          _error = result['error'] as String? ?? 'Invalid map';
        });
        return;
      }

      final gmB64 = result['gm_base64_png'] as String?;
      final playerB64 = result['player_base64_png'] as String?;
      final width = result['width'] as int?;
      final height = result['height'] as int?;
      final roomsJson = result['rooms'] as List<dynamic>?;
      final secretsJson = result['secret_features'] as List<dynamic>?;

      if (gmB64 == null || playerB64 == null || width == null || height == null) {
        setState(() {
          _building = false;
          _error = 'Invalid response from hub';
        });
        return;
      }

      final rooms = (roomsJson ?? [])
          .map((r) => MapRoom(
                x: r['x'] as int? ?? 0,
                y: r['y'] as int? ?? 0,
                w: r['w'] as int? ?? 0,
                h: r['h'] as int? ?? 0,
                name: r['name'] as String? ?? '',
              ))
          .toList();
      final secrets = (secretsJson ?? [])
          .map((s) => MapSecret(
                x: s['x'] as int? ?? 0,
                y: s['y'] as int? ?? 0,
                w: s['w'] as int? ?? 0,
                h: s['h'] as int? ?? 0,
                type: s['type'] as String? ?? 'secret',
                name: s['name'] as String? ?? '',
              ))
          .toList();

      if (!mounted) return;
      setState(() {
        _building = false;
        _gmBase64Png = gmB64;
        _playerBase64Png = playerB64;
        _width = width;
        _height = height;
        _rooms = rooms;
        _secrets = secrets;
        _showGmLayer = true;
      });

      final mapId = 'map_${DateTime.now().millisecondsSinceEpoch}';
      await MapsCacheStore.instance.saveMap(
        id: mapId,
        prompt: _promptController.text.trim(),
        gmBase64Png: gmB64,
        playerBase64Png: playerB64,
        width: width,
        height: height,
      );
    } catch (e) {
      if (mounted) {
        setState(() {
          _building = false;
          _error = 'Generation failed: $e';
        });
      }
    }
  }

  Future<void> _sharePdf(bool gmLayer) async {
    final b64 = gmLayer ? _gmBase64Png : _playerBase64Png;
    if (b64 == null) return;
    final layer = gmLayer ? 'GM' : 'Player';
    try {
      await ExportService.shareMapPdf(
        b64,
        '${_promptController.text.trim()} $layer',
      );
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('PDF export failed: $e')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 2,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Map Maker'),
          bottom: const TabBar(
            tabs: [
              Tab(icon: Icon(Icons.auto_fix_high), text: 'Forge'),
              Tab(icon: Icon(Icons.security), text: 'Vault'),
            ],
          ),
          actions: [
            if (_hasMap)
              IconButton(
                icon: const Icon(Icons.refresh),
                tooltip: 'New Map',
                onPressed: () => setState(() {
                  _gmBase64Png = null;
                  _playerBase64Png = null;
                  _error = null;
                }),
              ),
          ],
        ),
        body: TabBarView(
          children: [
            SingleChildScrollView(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  if (!_hasMap) _buildForm() else _buildResult(),
                ],
              ),
            ),
            _buildVault(),
          ],
        ),
      ),
    );
  }

  Widget _buildForm() {
    return RpgPanels.gothicStone.build(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            'Forge a Battle Map',
            style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                  color: PathfinderTheme.gold,
                ),
          ),
          const SizedBox(height: 8),
          Text(
            'Describe the location. The God renders GM and Player layers with Pillow.',
            style: TextStyle(color: Colors.grey[700]),
          ),
          const SizedBox(height: 20),
          TextField(
            controller: _promptController,
            maxLines: 3,
            minLines: 2,
            decoration: const InputDecoration(
              labelText: 'Prompt',
              hintText: 'e.g., "A ruined tavern 30x30 with a cellar trapdoor"',
              border: OutlineInputBorder(),
              alignLabelWithHint: true,
            ),
          ),
          SwitchListTile(
            title: const Text('Enable Grid Overlay'),
            value: _gridEnabled,
            activeThumbColor: PathfinderTheme.gold,
            onChanged: (v) => setState(() => _gridEnabled = v),
            dense: true,
          ),
          if (_error != null) ...[
            const SizedBox(height: 12),
            Text(_error!, style: const TextStyle(color: PathfinderTheme.crimson)),
          ],
          const SizedBox(height: 20),
          FilledButton.icon(
            onPressed: _building ? null : _generate,
            icon: _building
                ? const SizedBox(
                    height: 20,
                    width: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.auto_fix_high),
            label: Text(_building ? 'Rendering…' : 'Render Map'),
            style: FilledButton.styleFrom(
              padding: const EdgeInsets.symmetric(vertical: 16),
              backgroundColor: PathfinderTheme.gold,
              foregroundColor: PathfinderTheme.ink,
            ),
          ).animate().scale(duration: 120.ms, curve: Curves.elasticOut),
        ],
      ),
    );
  }

  Widget _buildResult() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        RpgPanels.gothicStone.build(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  const Icon(Icons.map, color: PathfinderTheme.gold, size: 28),
                  const SizedBox(width: 8),
                  Text(
                    'Map Ready',
                    style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                          color: PathfinderTheme.gold,
                        ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  _statChip(label: 'Size', value: '$_width x $_height'),
                  const SizedBox(width: 8),
                  _statChip(label: 'Rooms', value: '${_rooms.length}'),
                  const SizedBox(width: 8),
                  _statChip(label: 'Secrets', value: '${_secrets.length}'),
                ],
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),
        SegmentedButton<bool>(
          segments: const [
            ButtonSegment(
              value: true,
              label: Text('GM Layer'),
              icon: Icon(Icons.visibility),
            ),
            ButtonSegment(
              value: false,
              label: Text('Player Layer'),
              icon: Icon(Icons.visibility_off),
            ),
          ],
          selected: {_showGmLayer},
          onSelectionChanged: (s) => setState(() => _showGmLayer = s.first),
        ),
        const SizedBox(height: 16),
        InteractiveViewer(
          minScale: 0.5,
          maxScale: 4.0,
          child: ClipRRect(
            borderRadius: BorderRadius.circular(12),
            child: Image.memory(
              base64Decode(_activeBase64),
              fit: BoxFit.contain,
            ),
          ),
        ),
        const SizedBox(height: 16),
        if (_rooms.isNotEmpty) ...[
          RpgPanels.gothicStone.build(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Rooms',
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                    color: PathfinderTheme.crimson,
                  ),
                ),
                const SizedBox(height: 8),
                for (final r in _rooms)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: Row(
                      children: [
                        Expanded(
                          child: Text(
                            '${r.name} (${r.w}x${r.h} @ ${r.x},${r.y})',
                            style: const TextStyle(fontSize: 14),
                          ),
                        ),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                          decoration: BoxDecoration(
                            color: PathfinderTheme.gold.withValues(alpha: 0.2),
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: Text(
                            '${r.w * r.h} sq',
                            style: const TextStyle(fontSize: 11, color: PathfinderTheme.gold),
                          ),
                        ),
                      ],
                    ),
                  ),
              ],
            ),
          ),
        ],
        if (_secrets.isNotEmpty && _showGmLayer) ...[
          const SizedBox(height: 16),
          RpgPanels.gothicStone.build(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Secrets (GM only)',
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                    color: PathfinderTheme.crimson,
                  ),
                ),
                const SizedBox(height: 8),
                for (final s in _secrets)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: Text(
                      '${s.type}: ${s.name} (${s.w}x${s.h} @ ${s.x},${s.y})',
                      style: const TextStyle(fontSize: 14),
                    ),
                  ),
              ],
            ),
          ),
        ],
        const SizedBox(height: 16),
        Row(
          children: [
            Expanded(
              child: FilledButton.icon(
                onPressed: () => _sharePdf(false),
                icon: const Icon(Icons.picture_as_pdf),
                label: const Text('Share Player Map (PDF)'),
                style: FilledButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  backgroundColor: PathfinderTheme.gold,
                  foregroundColor: PathfinderTheme.ink,
                ),
              ).animate().scale(duration: 120.ms, curve: Curves.elasticOut),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: FilledButton.icon(
                onPressed: () => _sharePdf(true),
                icon: const Icon(Icons.picture_as_pdf),
                label: const Text('Share GM Map (PDF)'),
                style: FilledButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  backgroundColor: PathfinderTheme.crimson,
                  foregroundColor: Colors.white,
                ),
              ).animate().scale(duration: 120.ms, curve: Curves.elasticOut),
            ),
          ],
        ),
        const SizedBox(height: 12),
        OutlinedButton.icon(
          onPressed: () => setState(() {
            _gmBase64Png = null;
            _playerBase64Png = null;
            _error = null;
          }),
          icon: const Icon(Icons.refresh),
          label: const Text('New Map'),
        ),
      ],
    );
  }

  Future<void> _loadVault() async {
    await MapsCacheStore.instance.getMaps();
    if (!mounted) return;
    setState(() {});
  }

  Future<void> _loadMap(CachedMap map) async {
    setState(() {
      _gmBase64Png = map.gmBase64Png;
      _playerBase64Png = map.playerBase64Png;
      _width = map.width;
      _height = map.height;
      _promptController.text = map.prompt;
      _rooms = [];
      _secrets = [];
      _showGmLayer = true;
    });
    DefaultTabController.of(context).animateTo(0);
  }

  Future<void> _deleteMap(String id) async {
    await MapsCacheStore.instance.deleteMap(id);
    await _loadVault();
  }

  Widget _buildVault() {
    return FutureBuilder<List<CachedMap>>(
      future: MapsCacheStore.instance.getMaps(),
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Center(child: CircularProgressIndicator());
        }
        final maps = snapshot.data ?? [];
        if (maps.isEmpty) {
          return Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(Icons.account_balance, size: 64, color: Colors.grey),
                const SizedBox(height: 16),
                Text(
                  'Vault is empty',
                  style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                        color: Colors.grey[600],
                      ),
                ),
                const SizedBox(height: 8),
                const Text(
                  'Generate a map to save it here',
                  style: TextStyle(color: Colors.grey),
                ),
              ],
            ),
          );
        }
        return ListView.builder(
          padding: const EdgeInsets.all(16),
          itemCount: maps.length,
          itemBuilder: (context, index) {
            final map = maps[index];
            return Card(
              margin: const EdgeInsets.only(bottom: 12),
              child: ListTile(
                leading: Container(
                  width: 48,
                  height: 48,
                  decoration: BoxDecoration(
                    border: Border.all(color: PathfinderTheme.gold),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(4),
                    child: Image.memory(
                      base64Decode(map.playerBase64Png),
                      fit: BoxFit.cover,
                    ),
                  ),
                ),
                title: Text(map.prompt, maxLines: 1, overflow: TextOverflow.ellipsis),
                subtitle: Text(
                    '${map.width}x${map.height} • ${map.createdAt.toLocal().toString().split('.')[0]}'),
                trailing: PopupMenuButton<String>(
                  onSelected: (value) {
                    if (value == 'load') {
                      _loadMap(map);
                    } else if (value == 'delete') {
                      _deleteMap(map.id);
                    }
                  },
                  itemBuilder: (context) => [
                    const PopupMenuItem(
                      value: 'load',
                      child: ListTile(
                        leading: Icon(Icons.map),
                        title: Text('Load Map'),
                      ),
                    ),
                    const PopupMenuItem(
                      value: 'delete',
                      child: ListTile(
                        leading: Icon(Icons.delete, color: Colors.red),
                        title: Text('Delete', style: TextStyle(color: Colors.red)),
                      ),
                    ),
                  ],
                ),
              ),
            );
          },
        );
      },
    );
  }

  Widget _statChip({required String label, required String value}) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 8),
        decoration: BoxDecoration(
          color: PathfinderTheme.gold.withValues(alpha: 0.15),
          border: Border.all(color: PathfinderTheme.gold),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Column(
          children: [
            Text(value, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
            Text(label, style: TextStyle(fontSize: 11, color: Colors.grey[700])),
          ],
        ),
      ),
    );
  }
}

class MapRoom {
  final int x;
  final int y;
  final int w;
  final int h;
  final String name;

  MapRoom({
    required this.x,
    required this.y,
    required this.w,
    required this.h,
    required this.name,
  });
}

class MapSecret {
  final int x;
  final int y;
  final int w;
  final int h;
  final String type;
  final String name;

  MapSecret({
    required this.x,
    required this.y,
    required this.w,
    required this.h,
    required this.type,
    required this.name,
  });
}
