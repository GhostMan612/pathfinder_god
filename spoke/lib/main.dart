// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

import 'package:flutter/material.dart';
import 'package:flutter_gemma/flutter_gemma.dart';

import 'api/hub_client.dart';
import 'config/hub_config.dart';
import 'screens/home_screen.dart';
import 'services/audio_service.dart';
import 'services/haptics_service.dart';
import 'storage/character_store.dart';
import 'theme/app_theme.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  try {
    await FlutterGemma.initialize();
  } catch (_) {}
  final config = await HubConfig.load();
  await AudioService.instance.init();
  await HapticsService.init();
  runApp(PathfinderSpokeApp(config: config));
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
