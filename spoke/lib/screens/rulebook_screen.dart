// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

// Offline Pathfinder Rulebook — 34k+ entries, fully local.
// Primary source: bundled FTS5 database extracted on first launch.
// Fallback: the laptop hub's /rules/search when local open fails.

import 'package:flutter/material.dart';
import 'package:flutter_markdown_plus/flutter_markdown_plus.dart';

import '../api/hub_client.dart';
import '../services/miss_queue.dart';
import '../services/rulebook_db.dart';
import '../theme/app_theme.dart';
import 'rulebook_chat_screen.dart';

class RuleEntry {
  final String name;
  final String category;
  final String content;
  final String sourceBook;
  final String system;

  const RuleEntry({
    required this.name,
    required this.category,
    required this.content,
    required this.sourceBook,
    required this.system,
  });

  factory RuleEntry.fromLocal(LocalRuleHit h) => RuleEntry(
        name: h.name,
        category: h.category,
        content: h.content,
        sourceBook: h.sourceBook,
        system: h.system,
      );
}

class RulebookScreen extends StatefulWidget {
  final HubClient client;
  const RulebookScreen({super.key, required this.client});

  @override
  State<RulebookScreen> createState() => _RulebookScreenState();
}

class _RulebookScreenState extends State<RulebookScreen>
    with SingleTickerProviderStateMixin {
  late final TabController _tabController;
  final _searchController = TextEditingController();
  final _rulebookDb = RulebookDb();

  String _edition = '2e';
  List<RuleEntry> _results = [];
  bool _loading = false;
  bool _fetching = false;
  String? _missQuery; // last query with zero hits anywhere — offers web fetch
  String? _status; // first-run extraction / offline status line
  bool get _offlineReady => _rulebookDb.isReady;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    // Defer heavy 50 MB decompression until after first frame so the
    // dice animation + Choreographer aren't blocked ("Skipped 227 frames!").
    WidgetsBinding.instance.addPostFrameCallback((_) => _prepareLocal());
  }

  Future<void> _prepareLocal() async {
    setState(() => _status = 'Extracting offline rulebook…');
    try {
      await _rulebookDb.open();
      if (mounted) setState(() => _status = null);
    } catch (e) {
      debugPrint('RulebookScreen: Offline DB failed to open: $e');
      if (mounted) {
        setState(() => _status = 'Offline book unavailable — using hub. ($e)');
      }
    }
  }

  @override
  void dispose() {
    _tabController.dispose();
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _search(String query) async {
    final q = query.trim();
    if (q.isEmpty) return;
    setState(() {
      _loading = true;
      _results = [];
      _missQuery = null;
    });

    // Tier 1: bundled offline database.
    if (_offlineReady) {
      try {
        final hits =
            await _rulebookDb.search(q, edition: _edition, limit: 25);
        if (hits.isNotEmpty && mounted) {
          setState(() {
            _results = hits.map(RuleEntry.fromLocal).toList();
            _loading = false;
          });
          return;
        }
      } catch (_) {/* fall through to hub */}
    }

    // Tier 2: laptop hub.
    try {
      final hits = await widget.client.searchRules(q, edition: _edition);
      if (!mounted) return;
      if (hits.isNotEmpty) {
        setState(() {
          _results = hits
              .map((h) => RuleEntry(
                    name: h.name,
                    category: h.category,
                    content: h.content,
                    sourceBook: h.sourceBook,
                    system: h.system,
                  ))
              .toList();
          _loading = false;
        });
        // Hub is reachable — drain any queued misses in the background.
        MissQueue.drain(widget.client);
        return;
      }
      // Empty everywhere: remember the miss and offer a live web fetch.
      await MissQueue.queue(q, edition: _edition);
      if (mounted) {
        setState(() {
          _missQuery = q;
          _loading = false;
        });
      }
    } catch (e) {
      if (!mounted) return;
      await MissQueue.queue(q, edition: _edition);
      if (mounted) {
        setState(() {
          _missQuery = q;
          _status = 'No results — hub unreachable and offline search failed.';
          _loading = false;
        });
      }
    }
  }

  /// Tier 3: ask the hub to scrape this exact term now and keep it forever.
  Future<void> _fetchMissing() async {
    final q = _missQuery;
    if (q == null || q.isEmpty || _fetching) return;
    setState(() {
      _fetching = true;
      _status = 'Asking the hub to fetch "$q" from the web…';
    });
    try {
      final hit = await widget.client.fetchRule(q, edition: _edition);
      if (!mounted) return;
      setState(() {
        _results = [
          RuleEntry(
            name: hit.name,
            category: hit.category,
            content: hit.content,
            sourceBook: hit.sourceBook,
            system: hit.system,
          ),
        ];
        _missQuery = null;
        _status = 'Fetched live and saved permanently — it will be here next time.';
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _status = 'Could not fetch "$q" right now — it stays queued for backfill. ($e)';
      });
    } finally {
      if (mounted) setState(() => _fetching = false);
    }
  }

  void _openEntry(RuleEntry entry) {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: PathfinderTheme.parchmentDeep,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (_) => DraggableScrollableSheet(
        expand: false,
        initialChildSize: 0.75,
        builder: (_, scroll) => Column(
          children: [
            Padding(
              padding: const EdgeInsets.all(16),
              child: Row(
                children: [
                  Icon(_categoryIcon(entry.category),
                      color: PathfinderTheme.gold),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      entry.name,
                      style: TextStyle(
                        fontSize: 20,
                        fontWeight: FontWeight.bold,
                        color: PathfinderTheme.crimson,
                      ),
                    ),
                  ),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Align(
                alignment: Alignment.centerLeft,
                child: Text(
                  '${entry.system.toUpperCase()} · ${entry.category}'
                  '${entry.sourceBook.isEmpty ? '' : ' · ${entry.sourceBook}'}',
                  style: TextStyle(color: PathfinderTheme.gold, fontSize: 12),
                ),
              ),
            ),
            const Divider(),
            Expanded(
              child: Markdown(
                data: entry.content,
                controller: scroll,
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
                styleSheet: MarkdownStyleSheet(
                  p: const TextStyle(color: PathfinderTheme.ink, height: 1.4),
                  h1: const TextStyle(
                      color: PathfinderTheme.ink, fontWeight: FontWeight.bold),
                  h2: const TextStyle(
                      color: PathfinderTheme.ink, fontWeight: FontWeight.bold),
                  h3: const TextStyle(
                      color: PathfinderTheme.ink, fontWeight: FontWeight.bold),
                  em: const TextStyle(
                      color: PathfinderTheme.ink, fontStyle: FontStyle.italic),
                  strong: const TextStyle(
                      color: PathfinderTheme.ink, fontWeight: FontWeight.bold),
                  del: const TextStyle(color: PathfinderTheme.ink),
                  blockquote: const TextStyle(color: PathfinderTheme.ink),
                  listBullet: const TextStyle(color: PathfinderTheme.ink),
                  a: const TextStyle(
                      color: PathfinderTheme.crimson,
                      decoration: TextDecoration.underline),
                  code: const TextStyle(
                      color: PathfinderTheme.ink,
                      backgroundColor: PathfinderTheme.parchment),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('📖 Pathfinder Rulebook'),
        bottom: TabBar(
          controller: _tabController,
          tabs: const [
            Tab(text: 'Search'),
            Tab(text: 'Browse'),
            Tab(text: 'Guide'),
          ],
        ),
        actions: [
          if (_offlineReady)
            Tooltip(
              message: 'Offline rulebook active',
              child: const Padding(
                padding: EdgeInsets.only(right: 8),
                child: Icon(Icons.offline_bolt, color: PathfinderTheme.gold),
              ),
            ),
          PopupMenuButton<String>(
            initialValue: _edition,
            onSelected: (v) => setState(() => _edition = v),
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
          if (_status != null)
            Material(
              color: PathfinderTheme.gold.withValues(alpha: 0.15),
              child: Padding(
                padding:
                    const EdgeInsets.symmetric(vertical: 6, horizontal: 16),
                child: Row(
                  children: [
                    const SizedBox(
                      height: 14,
                      width: 14,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        _status!,
                        style: TextStyle(fontSize: 12, color: Colors.grey[700]),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          Expanded(
            child: TabBarView(
              controller: _tabController,
              children: [
                _buildSearchTab(),
                _buildBrowseTab(),
                _buildGuideTab(),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSearchTab() {
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(12),
          child: TextField(
            controller: _searchController,
            textInputAction: TextInputAction.search,
            onSubmitted: _search,
            decoration: InputDecoration(
              hintText: 'Search rules, spells, feats, monsters…',
              prefixIcon: const Icon(Icons.search),
              border: const OutlineInputBorder(),
              suffixIcon: IconButton(
                icon: const Icon(Icons.arrow_forward),
                onPressed: () => _search(_searchController.text),
              ),
            ),
          ),
        ),
        Expanded(child: _buildResultList()),
      ],
    );
  }

  Widget _buildBrowseTab() {
    final chips = const [
      'Flanking',
      'Dying',
      'Hero Points',
      'Flat-Footed',
      'Fireball',
      'Goblin',
      'Trip',
      'Grapple',
      'Opportunity Attack',
      'Concealment',
    ];
    return ListView(
      padding: const EdgeInsets.all(12),
      children: [
        Text('Quick lookups',
            style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          runSpacing: 4,
          children: [
            for (final c in chips)
              ActionChip(label: Text(c), onPressed: () {
                _searchController.text = c;
                _search(c);
                _tabController.animateTo(0);
              }),
          ],
        ),
      ],
    );
  }

  Widget _buildGuideTab() {
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
              style: TextStyle(
                  fontSize: 28,
                  fontWeight: FontWeight.bold,
                  color: PathfinderTheme.crimson),
            ),
            const SizedBox(height: 12),
            Text(
              'Your AI companion for rules, character building, and campaign help.',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 16, color: Colors.grey[600]),
            ),
            const SizedBox(height: 24),
            const _FeatureRow(
                icon: Icons.auto_fix_high,
                text: 'Character Builder — "Build a goblin alchemist"'),
            const _FeatureRow(
                icon: Icons.person,
                text: 'NPC Creator — "Cranky dwarf shopkeep"'),
            const _FeatureRow(
                icon: Icons.casino,
                text: 'Encounter Builder — "Level 3 forest ambush"'),
            const _FeatureRow(
                icon: Icons.menu_book,
                text: 'Rulebook — Offline search & browse'),
            const _FeatureRow(
                icon: Icons.school, text: 'Tutorial — "Teach me to play"'),
            const SizedBox(height: 24),
            ElevatedButton.icon(
              icon: const Icon(Icons.chat),
              label: const Text('Open Chat'),
              style: ElevatedButton.styleFrom(
                padding:
                    const EdgeInsets.symmetric(horizontal: 32, vertical: 16),
                backgroundColor: PathfinderTheme.crimson,
                foregroundColor: Colors.white,
              ),
              onPressed: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const RulebookChatScreen()),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildResultList() {
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_results.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                _missQuery == null
                    ? (_offlineReady
                        ? 'Search your offline rulebook.'
                        : 'Search rules via the hub.')
                    : 'No entry for "$_missQuery" anywhere yet.',
                textAlign: TextAlign.center,
                style: TextStyle(color: Colors.grey[600]),
              ),
              if (_missQuery != null) ...[
                const SizedBox(height: 12),
                FilledButton.icon(
                  onPressed: _fetching ? null : _fetchMissing,
                  icon: _fetching
                      ? const SizedBox(
                          height: 18,
                          width: 18,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.cloud_download),
                  label: Text(_fetching ? 'Fetching…' : 'Fetch "$_missQuery" from the web'),
                ),
                const SizedBox(height: 8),
                Text(
                  'Saved permanently when found — even offline next time.',
                  style: TextStyle(fontSize: 12, color: Colors.grey[500]),
                ),
              ],
            ],
          ),
        ),
      );
    }
    return ListView.builder(
      padding: const EdgeInsets.all(12),
      itemCount: _results.length,
      itemBuilder: (_, i) {
        final e = _results[i];
        return Card(
          margin: const EdgeInsets.symmetric(vertical: 4),
          child: ListTile(
            leading: Icon(_categoryIcon(e.category), color: PathfinderTheme.gold),
            title: Text(e.name, style: const TextStyle(fontWeight: FontWeight.bold)),
            subtitle: Text(
              '${e.system.toUpperCase()} · ${e.category}'
              '${e.sourceBook.isEmpty ? '' : ' · ${e.sourceBook}'}',
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => _openEntry(e),
          ),
        );
      },
    );
  }
}

class _FeatureRow extends StatelessWidget {
  final IconData icon;
  final String text;

  const _FeatureRow({required this.icon, required this.text});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        children: [
          Icon(icon, color: PathfinderTheme.gold, size: 24),
          const SizedBox(width: 12),
          Expanded(child: Text(text, style: const TextStyle(fontSize: 16))),
        ],
      ),
    );
  }
}

IconData _categoryIcon(String category) {
  switch (category.toLowerCase()) {
    case 'feats':
    case 'feat effects':
      return Icons.auto_fix_high;
    case 'spells':
    case 'spell effects':
    case 'rituals':
      return Icons.auto_awesome;
    case 'equipment':
    case 'equipment effects':
    case 'weapons and ammo':
    case 'armors and shields':
      return Icons.inventory_2;
    case 'bestiary':
    case 'bestiary effects':
      return Icons.pets;
    case 'classfeatures':
    case 'class features':
      return Icons.person;
    case 'backgrounds':
      return Icons.history_edu;
    case 'deities':
      return Icons.church;
    case 'ancestries':
    case 'ancestryfeatures':
    case 'ancestry features':
      return Icons.groups;
    case 'conditions':
      return Icons.healing;
    case 'actions':
    case 'adventure specific actions':
      return Icons.flash_on;
    default:
      return Icons.menu_book;
  }
}