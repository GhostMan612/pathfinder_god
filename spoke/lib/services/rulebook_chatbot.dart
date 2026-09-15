// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

/// Offline Rulebook Chatbot — Recovery Coach pattern for Pathfinder.
///
/// Layered architecture (from Recovery Coach debrief):
/// 1. Brain (default): Scripted engine — keyword list → intents → template replies.
/// 2. Retrieval: rules questions hit the bundled FTS5 rulebook via [RulebookProvider].
/// 3. Safety: unknown intents redirect to the help menu.
///
/// For Pathfinder God: Adapted as Tutorial Bot + Character Builder + Rules Reference.

library;

import 'dart:async';

import 'rulebook_db.dart';
import 'slm_guide.dart';

/// Intent types the bot understands.
enum BotIntent {
  greet,
  help,
  rulesLookup,
  characterBuild,
  npcCreate,
  encounterBuild,
  campaignStart,
  rulebookOpen,
  rulebookSearch,
  rulebookNavigate,
  tutorial,
  unknown,
}

/// A single chat message.
class ChatMessage {
  final String text;
  final bool fromUser;
  final DateTime timestamp;
  final BotIntent? intent;
  final Map<String, dynamic>? data;

  ChatMessage({
    required this.text,
    required this.fromUser,
    DateTime? timestamp,
    this.intent,
    this.data,
  }) : timestamp = timestamp ?? DateTime.now();
}

/// Scripted brain — zero-ML, works offline.
class RulebookBrain {
  // Intent keywords (token scoring)
  static const _intentKeywords = {
    BotIntent.greet: ['hello', 'hi', 'hey', 'greetings', 'hi there'],
    BotIntent.help: ['help', 'what can you do', 'commands', 'guide'],
    BotIntent.rulesLookup: ['rule', 'rules', 'lookup', 'find', 'search', 'what is', 'how does'],
    BotIntent.characterBuild: ['character', 'build', 'create character', 'make character', 'ancestry', 'class', 'background'],
    BotIntent.npcCreate: ['npc', 'create npc', 'make npc', 'villain', 'shopkeep', 'monster'],
    BotIntent.encounterBuild: ['encounter', 'battle', 'fight', 'combat', 'xp budget', 'difficulty'],
    BotIntent.campaignStart: ['campaign', 'start campaign', 'new campaign', 'session zero'],
    BotIntent.rulebookOpen: ['open rulebook', 'rulebook', 'book', 'open book'],
    BotIntent.rulebookSearch: ['search rulebook', 'find in book', 'look up'],
    BotIntent.rulebookNavigate: ['next chapter', 'previous chapter', 'table of contents', 'toc'],
    BotIntent.tutorial: ['tutorial', 'how to play', 'learn', 'teach me', 'beginner'],
  };

  /// Score input against intent keywords.
  BotIntent classify(String input) {
    final tokens = input.toLowerCase().split(RegExp(r'\W+')).where((t) => t.length > 2).toSet();
    BotIntent best = BotIntent.unknown;
    int bestScore = 0;

    for (final entry in _intentKeywords.entries) {
      int score = 0;
      for (final kw in entry.value) {
        if (tokens.contains(kw.toLowerCase())) {
          score += 2;
        } else if (input.toLowerCase().contains(kw.toLowerCase())) {
          score += 1;
        }
      }
      if (score > bestScore) {
        bestScore = score;
        best = entry.key;
      }
    }
    return best;
  }

  /// Generate scripted response for intent.
  String respond(BotIntent intent, {Map<String, dynamic>? context}) {
    switch (intent) {
      case BotIntent.greet:
        return _greeting();
      case BotIntent.help:
        return _help();
      case BotIntent.rulesLookup:
        return _rulesLookupPrompt();
      case BotIntent.characterBuild:
        return _characterBuildPrompt();
      case BotIntent.npcCreate:
        return _npcCreatePrompt();
      case BotIntent.encounterBuild:
        return _encounterBuildPrompt();
      case BotIntent.campaignStart:
        return _campaignStartPrompt();
      case BotIntent.rulebookOpen:
        return _rulebookOpenPrompt();
      case BotIntent.rulebookSearch:
        return _rulebookSearchPrompt();
      case BotIntent.rulebookNavigate:
        return _rulebookNavigatePrompt();
      case BotIntent.tutorial:
        return _tutorialPrompt();
      case BotIntent.unknown:
        return _unknownPrompt();
    }
  }

  String _greeting() =>
    "Hail, adventurer! I am your Pathfinder Guide. I can help you with:\n"
    "• 📖 **Rule Lookup** — \"How does flanking work?\"\n"
    "• 🧙 **Character Builder** — \"Build a goblin alchemist\"\n"
    "• 👹 **NPC Creator** — \"Make a cranky dwarf shopkeep\"\n"
    "• ⚔️ **Encounter Builder** — \"Level 3 forest ambush\"\n"
    "• 📜 **Rulebook** — Open, search, navigate the offline rulebook\n"
    "• 🎓 **Tutorial** — \"Teach me how to play\"\n\n"
    "What do you need, hero?";

  String _help() => _greeting();

  String _rulesLookupPrompt() =>
    "Ask me any rules question! Examples:\n"
    "• \"How does flanking work?\"\n"
    "• \"What are the dying rules?\"\n"
    "• \"Explain hero points\"\n"
    "• \"What's the DC for a level 5 task?\"\n\n"
    "I'll search the offline rulebook and cite sources.";

  String _characterBuildPrompt() =>
    "Let's forge a hero! Tell me:\n"
    "• Ancestry (human, elf, dwarf, goblin, etc.)\n"
    "• Class (fighter, wizard, rogue, alchemist, etc.)\n"
    "• Background (acolyte, criminal, scholar, etc.)\n"
    "• Level (1-20)\n"
    "• Any concept? \"Cunning goblin alchemist who hates fire\"\n\n"
    "I'll generate a complete PF2e character with ABCs, feats, and backstory.";

  String _npcCreatePrompt() =>
    "Need an NPC? Give me a concept:\n"
    "• \"Cranky level 5 dwarf alchemist shopkeep\"\n"
    "• \"Mysterious elf wizard villain\"\n"
    "• \"Friendly halfling innkeeper with a secret\"\n\n"
    "I'll output a legal PF2e stat block with personality, hooks, and Foundry-importable JSON.";

  String _encounterBuildPrompt() =>
    "Design a battle! Tell me:\n"
    "• Party level & size (e.g., \"4 level 3 PCs\")\n"
    "• Theme (forest, dungeon, urban, planar)\n"
    "• Difficulty (trivial, low, moderate, severe, extreme)\n"
    "• Any specific monsters?\n\n"
    "I'll balance XP budget, suggest terrain, tactics, and scaling.";

  String _campaignStartPrompt() =>
    "Starting a new saga! I'll help with:\n"
    "• Premise & hooks\n"
    "• Factions & NPCs\n"
    "• Session 0 questions\n"
    "• First session outline\n\n"
    "What's the elevator pitch? \"Horror investigation in Ustalav\"";

  String _rulebookOpenPrompt() =>
    "📖 Opening the **Pathfinder Rulebook** (offline, 34k+ entries).\n"
    "Tap a category to browse:\n"
    "• 📜 Feats (5,400+ 2E)\n"
    "• ⚔️ Equipment (5,000+ 2E)\n"
    "• ✨ Spells (1,700+ 2E)\n"
    "• 👹 Bestiary (3,000+ 2E)\n"
    "• ✨ Spells (3,000+ 1E)\n"
    "• 📖 Class Features (780+ 2E)\n\n"
    "Or search: \"flanking\", \"dying\", \"hero points\"";

  String _rulebookSearchPrompt() =>
    "What rule are you looking for? Type:\n"
    "• \"flanking\" — see all flanking rules\n"
    "• \"dying\" — dying/wounded rules\n"
    "• \"hero points\" — hero point rules\n"
    "• \"flat-footed\" — flat-footed condition\n\n"
    "I'll show matching entries with source book & page.";

  String _rulebookNavigatePrompt() =>
    "Rulebook navigation:\n"
    "• \"Next chapter\" / \"Previous chapter\"\n"
    "• \"Table of contents\" / \"TOC\"\n"
    "• \"Feats chapter\" / \"Spells chapter\"\n"
    "• \"Bookmarks\" — your saved entries";

  String _tutorialPrompt() =>
    "🎓 **Pathfinder 2e Tutorial**\n\n"
    "**Core Loop:**\n"
    "1. GM describes scene → 2. You describe action → 3. Roll d20 + modifier\n"
    "3. Compare to DC → 4. Degree of success (crit/success/fail/crit fail)\n\n"
    "**Key Concepts:**\n"
    "• **Actions** — Single ◆, Two ◆◆, Three ◆◆◆, Reaction ⬥, Free ✦\n"
    "• **Proficiency** — Untrained +0, Trained +level, Expert +level+2, Master +4, Legendary +6\n"
    "• **Degrees** — Crit Success (DC+10), Success, Fail, Crit Fail (DC-10)\n"
    "• **Hero Points** — Reroll, avoid death, 1/session\n\n"
    "Want a specific topic? \"Combat actions\", \"Spellcasting\", \"Crafting\"";

  String _unknownPrompt() =>
    "I'm not sure what you need. Try:\n"
    "• \"Help\" — see what I can do\n"
    "• \"How does flanking work?\" — rules lookup\n"
    "• \"Build a character\" — character builder\n"
    "• \"Open rulebook\" — browse offline book\n"
    "• \"Tutorial\" — learn to play";
}

/// Rulebook data provider backed by the bundled offline FTS5 database.
class RulebookProvider {
  final RulebookDb _db = RulebookDb();

  Future<void> load() async {
    try {
      await _db.open();
    } catch (_) {
      // Offline book unavailable on this device; scripted answers still work.
    }
  }

  bool get isReady => _db.isReady;

  Future<List<LocalRuleHit>> search(String query, {int limit = 3}) async {
    if (!_db.isReady) return const [];
    try {
      return await _db.search(query, edition: 'both', limit: limit);
    } catch (_) {
      return const [];
    }
  }
}

/// Main chatbot controller.
class RulebookChatbot {
  final RulebookBrain _brain = RulebookBrain();
  final RulebookProvider _provider = RulebookProvider();
  final StreamController<ChatMessage> _messagesController = StreamController.broadcast();
  bool _initialized = false;

  Stream<ChatMessage> get messages => _messagesController.stream;

  Future<void> initialize() async {
    if (_initialized) return;
    await _provider.load();
    _initialized = true;
    _addBotMessage(_brain._greeting());
  }

  Future<void> send(String text) async {
    _addUserMessage(text);

    if (_handleCommands(text)) return;

    final intent = _brain.classify(text);

    if ((intent == BotIntent.rulesLookup || intent == BotIntent.rulebookSearch) &&
        _provider.isReady) {
      final hits = await _provider.search(_extractQuery(text));
      if (hits.isNotEmpty) {
        // On-device SLM brain when downloaded+enabled; excerpts otherwise.
        final slmAnswer = await _askSlm(text, hits);
        if (slmAnswer != null) {
          _addBotMessage(slmAnswer, intent: intent);
        } else {
          _addBotMessage(_formatHits(hits), intent: intent);
        }
      } else {
        _addBotMessage(
          "I couldn't find that in the offline book. Try a shorter query like "
          "\"flanking\", \"dying\", or \"hero points\".",
          intent: intent,
        );
      }
      return;
    }

    _addBotMessage(_brain.respond(intent), intent: intent);
  }

  /// Returns the SLM answer, or null when the offline brain is off,
  /// missing, or errored (caller falls back to cited excerpts).
  Future<String?> _askSlm(String text, List<LocalRuleHit> hits) async {
    try {
      final slm = SlmGuideService.instance;
      if (!await slm.enabled) return null;
      if (!await slm.isInstalled()) return null;
      final buf = StringBuffer();
      await for (final token in slm.ask(text, hits)) {
        buf.write(token);
      }
      final answer = buf.toString().trim();
      if (answer.isEmpty) return null;
      return '$answer\n\n_(answered offline by the on-device brain)_';
    } catch (_) {
      return null;
    }
  }

  String _extractQuery(String text) {
    const stop = {
      'how', 'does', 'do', 'what', 'is', 'the', 'a', 'an', 'work', 'works',
      'search', 'find', 'look', 'up', 'rule', 'rules', 'for', 'of', 'explain',
      'me', 'tell', 'about', 'please', 'in', 'book', 'rulebook', 'and',
    };
    final tokens = text
        .toLowerCase()
        .split(RegExp(r'\W+'))
        .where((t) => t.isNotEmpty && !stop.contains(t))
        .toList();
    return tokens.join(' ');
  }

  String _formatHits(List<LocalRuleHit> hits) {
    final buf = StringBuffer('From your offline rulebook:\n');
    for (final h in hits) {
      final content = h.content.replaceAll('\n', ' ').trim();
      final snippet = content.length > 220 ? '${content.substring(0, 220)}…' : content;
      buf.write('\n**${h.name}**');
      final meta = [h.system, h.sourceBook].where((s) => s.isNotEmpty).join(' · ');
      if (meta.isNotEmpty) buf.write(' _($meta)_');
      buf.write('\n$snippet\n');
    }
    return buf.toString();
  }

  bool _handleCommands(String text) {
    final lower = text.toLowerCase().trim();
    if (lower == 'rulebook' || lower == 'open rulebook') {
      _addBotMessage(_brain._rulebookOpenPrompt());
      return true;
    }
    if (lower == 'tutorial') {
      _addBotMessage(_brain._tutorialPrompt());
      return true;
    }
    if (lower == 'help') {
      _addBotMessage(_brain._help());
      return true;
    }
    return false;
  }

  void _addUserMessage(String text) {
    _messagesController.add(ChatMessage(text: text, fromUser: true));
  }

  void _addBotMessage(String text, {BotIntent? intent, Map<String, dynamic>? data}) {
    _messagesController.add(ChatMessage(
      text: text,
      fromUser: false,
      intent: intent,
      data: data,
    ));
  }

  void dispose() {
    _messagesController.close();
  }
}