// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

import 'package:flutter/material.dart';

import '../api/hub_client.dart';
import '../storage/campaign_store.dart' as campaign_storage;
import '../storage/character_store.dart';
import 'campaign_screen.dart';
import 'character_list_screen.dart';
import 'combat_tracker_screen.dart';
import 'dice_screen.dart';
import 'encounter_builder_screen.dart';
import 'gm_chat_screen.dart';
import 'map_maker_screen.dart';
import 'rulebook_screen.dart';
import 'settings_screen.dart';
import '../services/combat_store.dart';

/// The app shell: a bottom navigation bar tying the five screens together.
class HomeScreen extends StatefulWidget {
  final HubClient client;
  final CharacterStore characters;
  final CombatStore? combatStore;
  const HomeScreen(
      {super.key,
      required this.client,
      required this.characters,
      this.combatStore});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int _index = 0;
  late final CombatStore _combatStore;
  late final bool _ownsCombatStore;
  late final campaign_storage.CampaignStore _campaigns;
  late final List<Widget> _screens;

  @override
  void initState() {
    super.initState();
    _combatStore = widget.combatStore ?? CombatStore(widget.client);
    _ownsCombatStore = widget.combatStore == null;
    _campaigns = campaign_storage.CampaignStore();
    // Built once so each tab keeps its state (dice history, chat) across switches.
    _screens = [
      const DiceScreen(),
      GmChatScreen(client: widget.client),
      CharacterListScreen(client: widget.client, store: widget.characters),
      RulebookScreen(client: widget.client),
      CombatTrackerScreen(client: widget.client, store: _combatStore),
      EncounterBuilderScreen(client: widget.client, store: _combatStore),
      MapMakerScreen(client: widget.client),
      CampaignScreen(
        client: widget.client,
        combatStore: _combatStore,
        store: _campaigns,
      ),
      SettingsScreen(client: widget.client, characters: widget.characters),
    ];
  }

  @override
  void dispose() {
    if (_ownsCombatStore) _combatStore.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(index: _index, children: _screens),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: (i) => setState(() => _index = i),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.casino_outlined), selectedIcon: Icon(Icons.casino), label: 'Dice'),
          NavigationDestination(icon: Icon(Icons.auto_stories_outlined), selectedIcon: Icon(Icons.auto_stories), label: 'God'),
          NavigationDestination(icon: Icon(Icons.person_outline), selectedIcon: Icon(Icons.person), label: 'Hero'),
          NavigationDestination(icon: Icon(Icons.menu_book_outlined), selectedIcon: Icon(Icons.menu_book), label: 'Rules'),
          NavigationDestination(icon: Icon(Icons.auto_fix_high_outlined), selectedIcon: Icon(Icons.auto_fix_high), label: 'Combat'),
          NavigationDestination(icon: Icon(Icons.auto_fix_high_outlined), selectedIcon: Icon(Icons.auto_fix_high), label: 'Encounter'),
          NavigationDestination(icon: Icon(Icons.map_outlined), selectedIcon: Icon(Icons.map), label: 'Map'),
          NavigationDestination(icon: Icon(Icons.campaign_outlined), selectedIcon: Icon(Icons.campaign), label: 'Campaign'),
          NavigationDestination(icon: Icon(Icons.settings_outlined), selectedIcon: Icon(Icons.settings), label: 'Setup'),
        ],
      ),
    );
  }
}
