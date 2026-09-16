// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';

import '../api/hub_client.dart';
import '../theme/app_theme.dart';
import '../widgets/rpg_panel.dart';

/// Map Maker — LLM prompt → Pillow-rendered PNG → share or save.
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
  String? _error;
  String? _base64Png;
  int? _width;
  int? _height;
  List<MapRoom> _rooms = [];

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
      _base64Png = null;
    });

    try {
      final result = await widget.client.generateMap(prompt);
      final valid = result['valid'] as bool? ?? false;

      if (!valid) {
        setState(() {
          _building = false;
          _error = result['error'] as String? ?? 'Invalid map';
        });
        return;
      }

      final b64 = result['base64_png'] as String?;
      final width = result['width'] as int?;
      final height = result['height'] as int?;
      final roomsJson = result['rooms'] as List<dynamic>?;

      if (b64 == null || width == null || height == null) {
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

      if (!mounted) return;
      setState(() {
        _building = false;
        _base64Png = b64;
        _width = width;
        _height = height;
        _rooms = _rooms;
      });
    } catch (e) {
      if (mounted) {
        setState(() {
          _building = false;
          _error = 'Generation failed: $e';
        });
      }
    }
  }

  Future<void> _saveMap() async {
    if (_base64Png == null) return;

    try {
      final bytes = base64Decode(_base64Png!);
      final dir = await getTemporaryDirectory();
      final file = File('${dir.path}/map.png');
      await file.writeAsBytes(bytes);

      if (!mounted) return;
      await SharePlus.instance.share(ShareParams(
        files: [XFile(file.path)],
        text: 'Pathfinder Map $_width x $_height',
      ));

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Map saved and shared')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Save failed: $e')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Map Maker'),
        actions: [
          if (_base64Png != null)
            IconButton(
              icon: const Icon(Icons.refresh),
              tooltip: 'New Map',
              onPressed: () => setState(() {
                _base64Png = null;
                _error = null;
              }),
            ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (_base64Png == null) _buildForm() else _buildResult(),
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
            'Describe the location. The God will design a grid map and render it with Pillow.',
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
          ),
        ],
      ),
    );
  }

  Widget _buildResult() {
    final b64 = _base64Png!;
    final bytes = base64Decode(b64);
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
                  _StatChip(label: 'Size', value: '${_width}x$_height'),
                  const SizedBox(width: 8),
                  _StatChip(label: 'Rooms', value: '${_rooms.length}'),
                  const SizedBox(width: 8),
                  _StatChip(label: 'Area', value: '${_width! * _height!} sq'),
                ],
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),
        // Map image with pinch-to-zoom
        InteractiveViewer(
          minScale: 0.5,
          maxScale: 4.0,
          child: ClipRRect(
            borderRadius: BorderRadius.circular(12),
            child: Image.memory(
              base64Decode(_base64Png!),
              fit: BoxFit.contain,
            ),
          ),
        ),
        const SizedBox(height: 16),
        // Room list
        if (_rooms.isNotEmpty) ...[
          RpgPanels.gothicStone.build(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
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
        const SizedBox(height: 16),
        Row(
          children: [
            Expanded(
              child: FilledButton.icon(
                onPressed: _saveMap,
                icon: const Icon(Icons.share),
                label: const Text('Save / Share Map'),
                style: FilledButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  backgroundColor: PathfinderTheme.crimson,
                  foregroundColor: Colors.white,
                ),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: OutlinedButton.icon(
                onPressed: () => setState(() {
                  _base64Png = null;
                  _error = null;
                }),
                icon: const Icon(Icons.refresh),
                label: const Text('New Map'),
              ),
            ),
          ],
        ),
      ],
    );
  }

  Widget _StatChip({required String label, required String value}) {
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