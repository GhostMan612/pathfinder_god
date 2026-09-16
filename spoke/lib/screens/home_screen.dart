// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

import 'package:flutter/material.dart';

import '../api/hub_client.dart';
import '../storage/character_store.dart';
import 'character_list_screen.dart';
import 'combat_tracker_screen.dart';
import 'dice_screen.dart';
import 'encounter_builder_screen.dart';
import 'gm_chat_screen.dart';
import 'rulebook_screen.dart';
import 'settings_screen.dart';
import '../services/combat_store.dart';

/// The app shell: a bottom navigation bar tying the five screens together.
class HomeScreen extends StatefulWidget {
  final HubClient client;
  final CharacterStore characters;
  const HomeScreen({super.key, required this.client, required this.characters});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int _index = 0;
  late final CombatStore _combatStore;
  late final List<Widget> _screens;

  @override
  void initState() {
    super.initState();
    _combatStore = CombatStore(widget.client);
    // Built once so each tab keeps its state (dice history, chat) across switches.
    _screens = [
      const DiceScreen(),
      GmChatScreen(client: widget.client),
      CharacterListScreen(client: widget.client, store: widget.characters),
      RulebookScreen(client: widget.client),
      CombatTrackerScreen(client: widget.client, store: _combatStore),
      EncounterBuilderScreen(client: widget.client, store: _combatStore),
      SettingsScreen(client: widget.client, characters: widget.characters),
    ];
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
          NavigationDestination(icon: Icon(Icons.settings_outlined), selectedIcon: Icon(Icons.settings), label: 'Setup'),
        ],
      ),
    );
  }
}
