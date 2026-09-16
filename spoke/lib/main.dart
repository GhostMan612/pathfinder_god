// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_gemma/flutter_gemma.dart';
import 'package:path_provider/path_provider.dart';
import 'package:provider/provider.dart';

import 'api/hub_client.dart';
import 'config/hub_config.dart';
import 'screens/home_screen.dart';
import 'services/audio_service.dart';
import 'services/combat_store.dart';
import 'services/haptics_service.dart';
import 'services/rulebook_db.dart';
import 'services/slm_guide.dart';
import 'storage/character_store.dart';
import 'theme/app_theme.dart';
import 'widgets/rpg_panels.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await SystemChrome.setEnabledSystemUIMode(SystemUiMode.immersiveSticky);
  await SystemChrome.setPreferredOrientations([DeviceOrientation.portraitUp]);
  runApp(const PathfinderBootApp());
}

class _BootData {
  final HubConfig config;
  final HubClient hubClient;
  final CharacterStore characters;
  final CombatStore combat;

  const _BootData({
    required this.config,
    required this.hubClient,
    required this.characters,
    required this.combat,
  });
}

Future<_BootData> _bootServices() async {
  await _reclaimPartialDownloads();
  try {
    await FlutterGemma.initialize();
  } catch (_) {}
  final config = await HubConfig.load();
  await AudioService.instance.init();
  await HapticsService.init();
  try {
    await RulebookDb().open();
  } catch (_) {}
  try {
    await SlmGuideService.instance.isInstalled();
  } catch (_) {}
  final hubClient = HubClient(config);
  final characters = CharacterStore();
  final combat = CombatStore(hubClient);
  return _BootData(
    config: config,
    hubClient: hubClient,
    characters: characters,
    combat: combat,
  );
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

class PathfinderBootApp extends StatefulWidget {
  const PathfinderBootApp({super.key});

  @override
  State<PathfinderBootApp> createState() => _PathfinderBootAppState();
}

class _PathfinderBootAppState extends State<PathfinderBootApp> {
  late final Future<_BootData> _bootFuture;

  @override
  void initState() {
    super.initState();
    _bootFuture = _bootServices();
  }

  @override
  void dispose() {
    _bootFuture.then((data) {
      try {
        data.combat.dispose();
        data.hubClient.dispose();
        AudioService.instance.dispose();
        SlmGuideService.instance.dispose();
      } catch (_) {}
    });
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<_BootData>(
      future: _bootFuture,
      builder: (context, snapshot) {
        if (snapshot.hasData) {
          final data = snapshot.data!;
          return ChangeNotifierProvider.value(
            value: data.combat,
            child: MaterialApp(
              title: 'Pathfinder God',
              debugShowCheckedModeBanner: false,
              theme: PathfinderTheme.light(),
              darkTheme: PathfinderTheme.dark(),
              home: HomeScreen(
                client: data.hubClient,
                characters: data.characters,
                combatStore: data.combat,
              ),
            ),
          );
        }
        if (snapshot.hasError) {
          return MaterialApp(
            debugShowCheckedModeBanner: false,
            theme: PathfinderTheme.light(),
            darkTheme: PathfinderTheme.dark(),
            home: Scaffold(
              backgroundColor: const Color(0xFF1E1B18),
              body: Center(
                child: RpgPanels.gothicStone(
                  margin: const EdgeInsets.all(32),
                  child: Text(
                    'Boot failed: ${snapshot.error}',
                    style: const TextStyle(color: PathfinderTheme.gold),
                  ),
                ),
              ),
            ),
          );
        }
        return MaterialApp(
          debugShowCheckedModeBanner: false,
          theme: PathfinderTheme.light(),
          darkTheme: PathfinderTheme.dark(),
          home: const _BootLoadingScreen(),
        );
      },
    );
  }
}

class _BootLoadingScreen extends StatelessWidget {
  const _BootLoadingScreen();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF1E1B18),
      body: Center(
        child: RpgPanels.gothicStone(
          margin: const EdgeInsets.all(32),
          child: const Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              CircularProgressIndicator(),
              SizedBox(height: 16),
              Text('Summoning the God...'),
            ],
          ),
        ),
      ),
    );
  }
}
