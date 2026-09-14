// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

import 'package:flutter/material.dart';

import '../api/hub_client.dart';
import '../api/models.dart';
import '../services/rulebook_db.dart';
import '../theme/app_theme.dart';

/// Rules & bestiary browser — bundled offline FTS5 database first,
/// hub fallback when the local book isn't available.
class BestiaryScreen extends StatefulWidget {
  final HubClient client;
  const BestiaryScreen({super.key, required this.client});

  @override
  State<BestiaryScreen> createState() => _BestiaryScreenState();
}

class _BestiaryScreenState extends State<BestiaryScreen> {
  final _query = TextEditingController();
  final _rulebookDb = RulebookDb();
  String _edition = 'both';
  List<RuleHit> _results = [];
  bool _loading = false;
  String? _error;
  String? _status;
  bool get _offlineReady => _rulebookDb.isReady;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _prepareLocal());
  }

  Future<void> _prepareLocal() async {
    setState(() => _status = 'Extracting offline bestiary…');
    try {
      await _rulebookDb.open();
      if (mounted) setState(() => _status = null);
    } catch (_) {
      if (mounted) {
        setState(() => _status = 'Offline book unavailable — using hub.');
      }
    }
  }

  Future<void> _search() async {
    final q = _query.text.trim();
    if (q.isEmpty) return;
    setState(() {
      _loading = true;
      _error = null;
      _results = [];
    });

    // Tier 1: bundled offline database.
    if (_offlineReady) {
      try {
        final hits = await _rulebookDb.search(q, edition: _edition, limit: 25);
        if (mounted) {
          setState(() {
            _results = hits
                .map((h) => RuleHit(
                      name: h.name,
                      content: h.content,
                      system: h.system,
                      category: h.category,
                      sourceBook: h.sourceBook,
                    ))
                .toList();
            _loading = false;
          });
          return;
        }
      } catch (_) {/* fall through to hub */}
    }

    // Tier 2: laptop hub.
    try {
      final hits = await widget.client.searchRules(q, edition: _edition);
      if (mounted) setState(() => _results = hits);
    } catch (e) {
      if (mounted) {
        setState(() => _error =
            'No results — the hub is unreachable and the offline search failed.\n$e');
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  void dispose() {
    _query.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Rules & Bestiary'),
        actions: [
          if (_offlineReady)
            const Tooltip(
              message: 'Offline database active',
              child: Padding(
                padding: EdgeInsets.only(right: 4),
                child: Icon(Icons.offline_bolt, color: PathfinderTheme.gold),
              ),
            ),
          PopupMenuButton<String>(
            initialValue: _edition,
            onSelected: (v) => setState(() => _edition = v),
            icon: Row(mainAxisSize: MainAxisSize.min, children: [
              Text(_edition.toUpperCase()),
              const Icon(Icons.arrow_drop_down),
            ]),
            itemBuilder: (_) => const [
              PopupMenuItem(value: 'both', child: Text('Both')),
              PopupMenuItem(value: '2e', child: Text('2e')),
              PopupMenuItem(value: '1e', child: Text('1e')),
            ],
          ),
        ],
      ),
      body: Column(
        children: [
          if (_status != null)
            Material(
              color: PathfinderTheme.gold.withValues(alpha: 0.15),
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: 6, horizontal: 16),
                child: Row(
                  children: [
                    const SizedBox(
                      height: 14,
                      width: 14,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(_status!,
                          style: TextStyle(fontSize: 12, color: Colors.grey[700])),
                    ),
                  ],
                ),
              ),
            ),
          Padding(
            padding: const EdgeInsets.all(12),
            child: TextField(
              controller: _query,
              textInputAction: TextInputAction.search,
              onSubmitted: (_) => _search(),
              decoration: InputDecoration(
                hintText: 'Search rules, spells, monsters…',
                border: const OutlineInputBorder(),
                isDense: true,
                suffixIcon: IconButton(icon: const Icon(Icons.search), onPressed: _search),
              ),
            ),
          ),
          if (_loading) const LinearProgressIndicator(),
          if (_error != null)
            Padding(
              padding: const EdgeInsets.all(16),
              child: Text(_error!,
                  style: const TextStyle(color: PathfinderTheme.crimsonBright)),
            ),
          Expanded(child: _buildResults()),
        ],
      ),
    );
  }

  Widget _buildResults() {
    if (_results.isEmpty && !_loading) {
      return Center(
        child: Text(
          _offlineReady
              ? 'Search your offline bestiary.'
              : "Search the hub's rules databases.",
          style: TextStyle(color: Colors.grey[600]),
        ),
      );
    }
    return ListView.builder(
      itemCount: _results.length,
      itemBuilder: (context, i) {
        final r = _results[i];
        final tags = [
          if (r.system.isNotEmpty) r.system.toUpperCase(),
          if (r.category.isNotEmpty) r.category,
          if (r.sourceBook.isNotEmpty) r.sourceBook,
        ].join(' · ');
        return Card(
          margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
          child: ExpansionTile(
            title: Text(r.name, style: const TextStyle(fontWeight: FontWeight.bold)),
            subtitle: tags.isEmpty ? null : Text(tags),
            childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
            children: [Align(alignment: Alignment.centerLeft, child: SelectableText(r.content))],
          ),
        );
      },
    );
  }
}