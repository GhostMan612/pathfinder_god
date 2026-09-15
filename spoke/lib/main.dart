// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_gemma/flutter_gemma.dart';
import 'package:path_provider/path_provider.dart';

import 'api/hub_client.dart';
import 'config/hub_config.dart';
import 'screens/home_screen.dart';
import 'services/audio_service.dart';
import 'services/haptics_service.dart';
import 'storage/character_store.dart';
import 'theme/app_theme.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await _reclaimPartialDownloads();
  try {
    await FlutterGemma.initialize();
  } catch (_) {}
  final config = await HubConfig.load();
  await AudioService.instance.init();
  await HapticsService.init();
  runApp(PathfinderSpokeApp(config: config));
}

Future<void> _reclaimPartialDownloads() async {
  try {
    final dir = await getApplicationDocumentsDirectory();
    var freed = 0;
    await for (final e in dir.list(recursive: true, followLinks: false)) {
      try {
        if (e is! File) continue;
        final p = e.path.toLowerCase();
        if (!p.endsWith('.temp') && !p.endsWith('.part')) continue;
        freed += await e.length();
        await e.delete();
      } catch (_) {}
    }
    if (freed > 0) debugPrint('Startup: reclaimed $freed partial bytes');
  } catch (_) {}
}

class PathfinderSpokeApp extends StatelessWidget {
  final HubConfig config;
  const PathfinderSpokeApp({super.key, required this.config});

  @override
  Widget build(BuildContext context) {
    final client = HubClient(config);
    final characters = CharacterStore();
    return MaterialApp(
      title: 'Pathfinder God',
      debugShowCheckedModeBanner: false,
      theme: PathfinderTheme.light(),
      darkTheme: PathfinderTheme.dark(),
      home: HomeScreen(client: client, characters: characters),
    );
  }
}
