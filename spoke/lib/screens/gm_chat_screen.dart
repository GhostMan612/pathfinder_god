// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

import 'package:flutter/material.dart';
import 'package:flutter_markdown_plus/flutter_markdown_plus.dart';

import '../api/hub_client.dart';
import '../theme/app_theme.dart';

class _Message {
  final bool fromUser;
  String text;
  String? backend;
  List<Map<String, dynamic>> sources;
  _Message({required this.fromUser, required this.text, this.backend, List<Map<String, dynamic>>? sources}) : sources = sources ?? const [];
}

/// Live chat with the Pathfinder God, streaming tokens over the WebSocket.
class GmChatScreen extends StatefulWidget {
  final HubClient client;
  const GmChatScreen({super.key, required this.client});

  @override
  State<GmChatScreen> createState() => _GmChatScreenState();
}

class _GmChatScreenState extends State<GmChatScreen> {
  final _input = TextEditingController();
  final _scroll = ScrollController();
  final _messages = <_Message>[];
  String _edition = 'both';
  bool _busy = false;

  List<List<String>> _buildHistory() {
    // Last 8 turns (16 messages) as [[role, text]] for continuity after WS drop
    final hist = <List<String>>[];
    for (final m in _messages) {
      if (m.text.isEmpty || m.text == '…') continue;
      hist.add([m.fromUser ? 'user' : 'assistant', m.text]);
    }
    // Keep context window small (hub rag_limit=4, num_predict=700)
    if (hist.length > 12) return hist.sublist(hist.length - 12);
    return hist;
  }

  Future<void> _send() async {
    final text = _input.text.trim();
    if (text.isEmpty || _busy) return;
    _input.clear();

    // Capture history *before* adding current turn
    final history = _buildHistory();

    setState(() {
      _messages.add(_Message(fromUser: true, text: text));
      _messages.add(_Message(fromUser: false, text: '', backend: '…'));
      _busy = true;
    });
    _scrollToEnd();

    final reply = _messages.last;
    try {
        await for (final event in widget.client.stream(text, edition: _edition, history: history)) {
        setState(() {
          switch (event.type) {
            case 'start':
              reply.backend = event.backend;
              break;
            case 'chunk':
              reply.text += event.text ?? '';
              break;
            case 'end':
              reply.sources = (event.sources.isNotEmpty
                  ? event.sources.map((s) => {'name': s.name, 'source_book': s.sourceBook}).toList()
                  : const []);
              break;
            case 'retrying':
              reply.text = '';
              reply.sources = const [];
              reply.backend = '⟳ ${event.message ?? "reconnecting…"}';
              break;
            case 'error':
              reply.text += '\n\n_(hub error: ${event.message})_';
              break;
          }
        });
        _scrollToEnd();
      }
    } catch (e) {
      setState(() => reply.text = reply.text.isEmpty
          ? "Couldn't reach the God at ${widget.client.config.baseUrl}.\n\n$e"
          : reply.text);
    } finally {
      setState(() => _busy = false);
    }
  }

  void _scrollToEnd() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scroll.hasClients) {
        _scroll.animateTo(_scroll.position.maxScrollExtent,
            duration: const Duration(milliseconds: 200), curve: Curves.easeOut);
      }
    });
  }

  @override
  void dispose() {
    _input.dispose();
    _scroll.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('The God'),
        actions: [
          PopupMenuButton<String>(
            initialValue: _edition,
            onSelected: (v) => setState(() => _edition = v),
            icon: Row(mainAxisSize: MainAxisSize.min, children: [
              Text(_edition.toUpperCase()),
              const Icon(Icons.arrow_drop_down),
            ]),
            itemBuilder: (_) => const [
              PopupMenuItem(value: 'both', child: Text('Both editions')),
              PopupMenuItem(value: '2e', child: Text('Pathfinder 2e')),
              PopupMenuItem(value: '1e', child: Text('Pathfinder 1e')),
            ],
          ),
        ],
      ),
      body: Column(
        children: [
          Expanded(
            child: _messages.isEmpty
                ? _emptyState(context)
                : ListView.builder(
                    controller: _scroll,
                    padding: const EdgeInsets.all(12),
                    itemCount: _messages.length,
                    itemBuilder: (context, i) => _bubble(_messages[i]),
                  ),
          ),
          _composer(),
        ],
      ),
    );
  }

  Widget _emptyState(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.auto_stories, size: 64, color: PathfinderTheme.gold),
            const SizedBox(height: 12),
            Text('Ask the Pathfinder God', style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 8),
            const Text(
              'e.g. "Build a cunning goblin alchemist boss with a full backstory" or '
              '"What are the rules for flanking?"',
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }

  Widget _bubble(_Message m) {
    final theme = Theme.of(context);
    final align = m.fromUser ? Alignment.centerRight : Alignment.centerLeft;
    final color = m.fromUser ? PathfinderTheme.crimson : theme.cardTheme.color;
    final textColor = m.fromUser ? PathfinderTheme.parchment : theme.textTheme.bodyMedium?.color;

    return Align(
      alignment: align,
      child: Container(
        constraints: const BoxConstraints(maxWidth: 340),
        margin: const EdgeInsets.symmetric(vertical: 4),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(
          color: color,
          borderRadius: BorderRadius.circular(14),
          border: m.fromUser ? null : Border.all(color: PathfinderTheme.gold.withValues(alpha: 0.4)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (!m.fromUser && m.backend != null && m.backend != '…')
              Padding(
                padding: const EdgeInsets.only(bottom: 4),
                child: Text('via ${m.backend}',
                    style: theme.textTheme.labelSmall?.copyWith(color: PathfinderTheme.gold)),
              ),
            if (m.fromUser)
              Text(m.text, style: TextStyle(color: textColor))
            else if (m.text.isEmpty)
              const SizedBox(
                height: 18, width: 18,
                child: CircularProgressIndicator(strokeWidth: 2),
              )
            else
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  MarkdownBody(data: m.text),
                  if (m.sources.isNotEmpty) ...[
                    const SizedBox(height: 8),
                    Wrap(
                      spacing: 6, runSpacing: 4,
                      children: [
                        for (final s in m.sources)
                          Chip(
                            label: Text(
                              '${s['name']} • ${s['source_book']}',
                              style: const TextStyle(fontSize: 11),
                            ),
                            backgroundColor: PathfinderTheme.gold.withValues(alpha: 0.15),
                            side: BorderSide(color: PathfinderTheme.gold.withValues(alpha: 0.35)),
                            materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                            visualDensity: VisualDensity.compact,
                          ),
                      ],
                    ),
                  ],
                ],
              ),
          ],
        ),
      ),
    );
  }

  Widget _composer() {
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(8),
        child: Row(
          children: [
            Expanded(
              child: TextField(
                controller: _input,
                minLines: 1,
                maxLines: 4,
                textInputAction: TextInputAction.send,
                onSubmitted: (_) => _send(),
                decoration: const InputDecoration(
                  hintText: 'Speak to the God…',
                  border: OutlineInputBorder(),
                  isDense: true,
                ),
              ),
            ),
            const SizedBox(width: 8),
            FloatingActionButton.small(
              onPressed: _busy ? null : _send,
              child: _busy
                  ? const SizedBox(height: 18, width: 18, child: CircularProgressIndicator(strokeWidth: 2))
                  : const Icon(Icons.send),
            ),
          ],
        ),
      ),
    );
  }
}
