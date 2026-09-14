// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

library;

import 'package:flutter/material.dart';

import '../../services/rulebook_chatbot.dart';
import '../theme/app_theme.dart';

class RulebookChatScreen extends StatefulWidget {
  const RulebookChatScreen({super.key});

  @override
  State<RulebookChatScreen> createState() => _RulebookChatScreenState();
}

class _RulebookChatScreenState extends State<RulebookChatScreen> {
  final _chatbot = RulebookChatbot();
  final _controller = TextEditingController();
  final _scroll = ScrollController();
  final List<ChatMessage> _messages = [];

  @override
  void initState() {
    super.initState();
    _init();
  }

  Future<void> _init() async {
    await _chatbot.initialize();
    _chatbot.messages.listen((msg) {
      if (mounted) setState(() => _messages.add(msg));
      _scrollToBottom();
    });
  }

  void _send() {
    final text = _controller.text.trim();
    if (text.isEmpty) return;
    _controller.clear();
    _chatbot.send(text);
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scroll.hasClients) {
        _scroll.animateTo(_scroll.position.maxScrollExtent,
            duration: const Duration(milliseconds: 200), curve: Curves.easeOut);
      }
    });
  }

  @override
  void dispose() {
    _controller.dispose();
    _scroll.dispose();
    _chatbot.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Pathfinder Guide'),
        actions: [
          IconButton(
            icon: const Icon(Icons.help_outline),
            onPressed: () => _chatbot.send('help'),
            tooltip: 'Help',
          ),
          IconButton(
            icon: const Icon(Icons.menu_book),
            onPressed: () => _chatbot.send('open rulebook'),
            tooltip: 'Open Rulebook',
          ),
          IconButton(
            icon: const Icon(Icons.school),
            onPressed: () => _chatbot.send('tutorial'),
            tooltip: 'Tutorial',
          ),
        ],
      ),
      body: Column(
        children: [
          Expanded(
            child: _messages.isEmpty
                ? _buildWelcome()
                : ListView.builder(
                    controller: _scroll,
                    padding: const EdgeInsets.all(12),
                    itemCount: _messages.length,
                    itemBuilder: (_, i) => _buildBubble(_messages[i]),
                  ),
          ),
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.all(8),
              child: Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _controller,
                      onSubmitted: (_) => _send(),
                      decoration: const InputDecoration(
                        hintText: 'Ask me anything...',
                        border: OutlineInputBorder(),
                        isDense: true,
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  IconButton(
                    icon: const Icon(Icons.send),
                    onPressed: _send,
                    style: IconButton.styleFrom(
                      backgroundColor: PathfinderTheme.crimson,
                      foregroundColor: Colors.white,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildWelcome() {
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.auto_awesome, size: 80, color: PathfinderTheme.gold),
            const SizedBox(height: 16),
            Text(
              'Pathfinder Guide',
              style: TextStyle(fontSize: 28, fontWeight: FontWeight.bold, color: PathfinderTheme.crimson),
            ),
            const SizedBox(height: 12),
            Text(
              'Your AI companion for rules, character building, and campaign help.',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 16, color: Colors.grey[600]),
            ),
            const SizedBox(height: 24),
            Text(
              'Try saying:',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 12),
            _ExampleChip(label: 'How does flanking work?', onTap: () => _chatbot.send('How does flanking work?')),
            _ExampleChip(label: 'Build a goblin alchemist', onTap: () => _chatbot.send('Build a goblin alchemist')),
            _ExampleChip(label: 'Open rulebook', onTap: () => _chatbot.send('open rulebook')),
            _ExampleChip(label: 'Tutorial', onTap: () => _chatbot.send('tutorial')),
          ],
        ),
      ),
    );
  }

  Widget _buildBubble(ChatMessage msg) {
    final isUser = msg.fromUser;
    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 4),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        constraints: const BoxConstraints(maxWidth: 320),
        decoration: BoxDecoration(
          color: isUser ? PathfinderTheme.crimson : Colors.grey[850],
          borderRadius: BorderRadius.circular(16),
          border: !isUser ? Border.all(color: PathfinderTheme.gold.withValues(alpha: 0.4)) : null,
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            if (!isUser && msg.intent != null && msg.intent != BotIntent.unknown)
              Padding(
                padding: const EdgeInsets.only(bottom: 4),
                child: Text(
                  _intentLabel(msg.intent!),
                  style: TextStyle(fontSize: 11, color: PathfinderTheme.gold, fontStyle: FontStyle.italic),
                ),
              ),
            if (msg.text.isEmpty && !isUser)
              const SizedBox(height: 18, width: 18, child: CircularProgressIndicator(strokeWidth: 2))
            else
              Text(msg.text, style: const TextStyle(color: Colors.white, fontSize: 15)),
          ],
        ),
      ),
    );
  }

  String _intentLabel(BotIntent intent) {
    switch (intent) {
      case BotIntent.rulesLookup: return 'Rules Lookup';
      case BotIntent.characterBuild: return 'Character Builder';
      case BotIntent.npcCreate: return 'NPC Compiler';
      case BotIntent.encounterBuild: return 'Encounter Builder';
      case BotIntent.campaignStart: return 'Campaign Builder';
      case BotIntent.rulebookOpen: return 'Rulebook';
      case BotIntent.rulebookSearch: return 'Rulebook Search';
      case BotIntent.rulebookNavigate: return 'Rulebook Nav';
      case BotIntent.tutorial: return 'Tutorial';
      default: return 'Assistant';
    }
  }
}

class _ExampleChip extends StatelessWidget {
  final String label;
  final VoidCallback onTap;

  const _ExampleChip({required this.label, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      child: ActionChip(
        label: Text(label, style: const TextStyle(fontSize: 14)),
        onPressed: onTap,
        backgroundColor: PathfinderTheme.gold.withValues(alpha: 0.2),
        side: BorderSide(color: PathfinderTheme.gold),
      ),
    );
  }
}