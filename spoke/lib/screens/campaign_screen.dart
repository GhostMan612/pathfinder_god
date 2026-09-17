// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';

import '../api/hub_client.dart';
import '../models/campaign.dart';
import '../services/combat_store.dart' as combat;
import '../storage/campaign_store.dart';
import '../theme/app_theme.dart';
import '../widgets/rpg_panels.dart';

/// Campaign Hub — active campaign header, session journal, AI summaries.
class CampaignScreen extends StatefulWidget {
  final HubClient client;
  final combat.CombatStore combatStore;
  final CampaignStore store;

  const CampaignScreen({
    super.key,
    required this.client,
    required this.combatStore,
    required this.store,
  });

  @override
  State<CampaignScreen> createState() => _CampaignScreenState();
}

class _CampaignScreenState extends State<CampaignScreen> {
  CampaignModel? _campaign;
  bool _loading = true;
  bool _summarizing = false;
  final _nameController = TextEditingController();
  final _descriptionController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _reload();
  }

  @override
  void dispose() {
    _nameController.dispose();
    _descriptionController.dispose();
    super.dispose();
  }

  Future<void> _reload() async {
    setState(() => _loading = true);
    try {
      final campaign = await widget.store.getActiveCampaign();
      if (mounted) setState(() => _campaign = campaign);
    } catch (_) {
      if (mounted) setState(() => _campaign = null);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  List<String> _combatEvents() {
    final lines = <String>[];
    for (final c in widget.combatStore.combatants) {
      lines.add('${c.name} at ${c.currentHp}/${c.maxHp} HP (AC ${c.ac})');
      for (final cond in c.conditions) {
        lines.add('${c.name}: ${cond.name} ${cond.value}');
      }
    }
    return lines;
  }

  Future<void> _summarizeCombat() async {
    final campaign = _campaign;
    if (campaign == null || _summarizing) return;
    final events = _combatEvents();
    if (events.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('No combatants to chronicle yet.')),
      );
      return;
    }
    setState(() => _summarizing = true);
    try {
      final summary =
          await widget.client.summarizeSession(events, campaign.name);
      if (!mounted) return;
      if (summary.trim().isEmpty) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('The chronicler returned empty-handed.')),
        );
        return;
      }
      final updated = await widget.store.addSessionNote(summary);
      setState(() => _campaign = updated ?? campaign);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Chronicle failed: $e')),
        );
      }
    } finally {
      if (mounted) setState(() => _summarizing = false);
    }
  }

  Future<void> _showNewCampaignDialog() async {
    _nameController.clear();
    _descriptionController.clear();
    final created = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('New Campaign'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: _nameController,
              decoration: const InputDecoration(labelText: 'Name'),
            ),
            TextField(
              controller: _descriptionController,
              decoration: const InputDecoration(labelText: 'Description'),
              maxLines: 3,
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Create'),
          ),
        ],
      ),
    );
    if (created != true || !mounted) return;
    final name = _nameController.text.trim();
    if (name.isEmpty) return;
    final campaign = CampaignModel(
      id: 'campaign_${DateTime.now().millisecondsSinceEpoch}',
      name: name,
      description: _descriptionController.text.trim(),
      updatedAt: DateTime.now().toUtc(),
    );
    await widget.store.saveCampaign(campaign);
    if (mounted) setState(() => _campaign = campaign);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Campaign')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _campaign == null
              ? _buildEmpty()
              : _buildDashboard(_campaign!),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _showNewCampaignDialog,
        icon: const Icon(Icons.add),
        label: const Text('New Campaign'),
      ).animate().scale(duration: 120.ms, curve: Curves.elasticOut),
    );
  }

  Widget _buildEmpty() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.auto_stories, size: 64, color: PathfinderTheme.gold),
            const SizedBox(height: 16),
            Text(
              'No active campaign',
              style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                    color: PathfinderTheme.crimson,
                    fontWeight: FontWeight.bold,
                  ),
            ),
            const SizedBox(height: 8),
            Text(
              'Forge one to bind heroes, maps, and encounters under a single banner.',
              textAlign: TextAlign.center,
              style: TextStyle(color: Colors.grey[600]),
            ),
          ],
        ),
      ),
    ).animate().fadeIn(duration: 300.ms).slideY(begin: 0.2);
  }

  Widget _buildDashboard(CampaignModel campaign) {
    final notes = campaign.sessionNotes;
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        RpgPanels.gothicStone(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                campaign.name,
                style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                      color: PathfinderTheme.gold,
                      fontWeight: FontWeight.bold,
                    ),
              ),
              if (campaign.description.isNotEmpty) ...[
                const SizedBox(height: 4),
                Text(
                  campaign.description,
                  style: Theme.of(context)
                      .textTheme
                      .bodyLarge
                      ?.copyWith(color: PathfinderTheme.ink),
                ),
              ],
              const SizedBox(height: 8),
              Text(
                '${notes.length} entr${notes.length == 1 ? 'y' : 'ies'} in the journal',
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: PathfinderTheme.ink.withValues(alpha: 0.6),
                    ),
              ),
            ],
          ),
        ).animate().fadeIn(duration: 400.ms).slideY(begin: -0.1),
        const SizedBox(height: 16),
        FilledButton.icon(
          onPressed: _summarizing ? null : _summarizeCombat,
          icon: _summarizing
              ? const SizedBox(
                  height: 18,
                  width: 18,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Icon(Icons.auto_fix_high),
          label: Text(
              _summarizing ? 'Chronicling…' : 'Summarize Recent Combat'),
        ).animate().scale(duration: 120.ms, curve: Curves.elasticOut),
        const SizedBox(height: 16),
        Text(
          'Session Journal',
          style: Theme.of(context).textTheme.titleMedium?.copyWith(
                color: PathfinderTheme.gold,
                fontWeight: FontWeight.bold,
              ),
        ),
        const SizedBox(height: 8),
        if (notes.isEmpty)
          Text(
            'The journal is blank. Survive something worth writing down.',
            style: TextStyle(color: Colors.grey[600]),
          ),
        ...notes.asMap().entries.map(
              (entry) => Card(
                margin: const EdgeInsets.only(bottom: 8),
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Entry ${entry.key + 1}',
                        style: const TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.bold,
                          color: PathfinderTheme.gold,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(entry.value),
                    ],
                  ),
                ),
              )
                  .animate(delay: (entry.key * 50).ms)
                  .fadeIn(duration: 200.ms)
                  .slideX(begin: 0.2),
            ),
      ],
    );
  }
}
