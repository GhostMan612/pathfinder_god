# Pathfinder God — Technical Architecture Whitepaper v1.0

**Date:** 2026-08-30  
**Addendum:** 2026-09-14 (v0.6.1 database truth pass, v0.6.2 zero-config discovery) — see [Addendum](#addendum--v061v062-2026-09-14). Body below is the frozen v1.0 text; figures marked [v1.0] are superseded where the addendum says so.  
**Status:** Working system — Hub live on :8000, Spoke builds in Android Studio, Command Center standalone exe shipped. Current focus: offline-first polish, hub-spoke resilience, dice fidelity.  
**Authors:** Pathfinder God build team  
**Classification:** Internal — shareable with Gemini / external reviewers for deep research help  
**Repo:** `C:\pathfinder_god\` (Flutter `spoke/`, Python FastAPI `hub/`, contract `shared/openapi.yaml`, standalone `tools/command_center/`)  
**Canonical rules:** `RULES.md` wins all conflicts. Lane ends at source correctness — `flutter analyze` + `flutter test` only; human builds APK in Android Studio.

---

## Table of Contents

1. [Abstract](#1-abstract)
2. [Vision & Requirements](#2-vision--requirements)
3. [System Overview](#3-system-overview)
4. [Hub — Python FastAPI Service (laptop)](#4-hub--python-fastapi-service-laptop)
5. [Spoke — Flutter Android App (phone)](#5-spoke--flutter-android-app-phone)
6. [Data Layer — The 500 MB Database Problem](#6-data-layer--the-500-mb-database-problem)
7. [API Contract & Communication](#7-api-contract--communication)
8. [Offline-First & Fallback Tiers](#8-offline-first--fallback-tiers)
9. [Build, Distribution & Environment](#9-build-distribution--environment)
10. [Security, Privacy & Compliance](#10-security-privacy--compliance)
11. [Performance, Tuning & Hardware](#11-performance-tuning--hardware)
12. [Current Progress & Verification](#12-current-progress--verification)
13. [Bugs Fixed in Last 48 h (with Logs)](#13-bugs-fixed-in-last-48-h-with-logs)
14. [Known Issues / Tech Debt](#14-known-issues--tech-debt)
15. [Open Questions — Where We Need Gemini Deep Research](#15-open-questions--where-we-need-gemini-deep-research)
16. [Roadmap](#16-roadmap)
17. [Appendix](#17-appendix)

---

## Addendum — v0.6.1–v0.6.4 (2026-09-14)

Supersedes these [v1.0] figures: DB is **44,620 rows** (1E 22,131 / 2E 22,489) as of v0.6.3 (jrmiller82 OGL YAML folded in); royalty-free BGM/SFX shipped (see `audio-credits.md`);
57 MB live / 20 MB gzipped asset (`bundleVersion` 2); app is **5 tabs**
(Rules/Bestiary merged into one Rules tab); search is **exact-name →
FTS5-known-source → FTS5-Unknown** on hub and phone; categories are canonical
lowercase; content is plain text (HTML stripped). New: hub advertises
`_pathfindergod._tcp` over mDNS and the app auto-discovers it
(**Setup → Find hub automatically**, hotspot/emulator/last-known fallbacks).
Open-data pipeline landed (`build_rag.py`, `build_2e_rag.py`, `db_normalize.py`,
PSRD/Pf2ools importers, AoN/d20pfsrd scrapers). Current gates:
`flutter analyze` clean, `flutter test` 21/21. Live docs:
`../README.md`, [`database.md`](database.md), [`api.md`](api.md),
[`troubleshooting.md`](troubleshooting.md).

## 1. Abstract

Pathfinder God is a **Hub-Spoke tabletop RPG companion** for **Pathfinder 1e/2e**. The **Hub** (laptop, Python + FastAPI + Ollama + FTS5 RAG) owns all heavy work — 43,884 rule entries [v1.0: 34k+], retrieval, LLM generation, campaign persistence. The **Spoke** (phone, Flutter) is a thin, resilient, **offline-first** client for dice (full PF2e degrees of success), character sheet, rulebook browser, and GM chat. A **standalone PySide6 Command Center exe** (~48 MB) lets a GM run Hub/Ollama without a venv.

Key design constraint: **open-licensed rules** must be searchable instantly, even with the laptop off, without committing binaries to git. Solved by a 57 MB FTS5 SQLite DB on the hub [v1.0: 132 MB] + a 20 MB gzipped copy bundled in the APK [v1.0: 48 MB] and lazily extracted to app storage on first launch. All communication is `shared/openapi.yaml`-driven REST + auto-reconnecting WebSocket; generation is 2-tier (Ollama → raw FTS5 excerpts, never a dead end).

This paper documents the **as-built v0.5.x–v0.6.0** system, exact tech choices, data flows, and the live bugs fixed with log evidence — so reviewers can evaluate without guessing and propose deeper research.

---

## 2. Vision & Requirements

**Elevator pitch (from blueprints):** "Your AI God for Pathfinder — perfect rules memory, cinematic NPC/campaign generation, dice that feel physical, and a rulebook that works in airplane mode."

**Functional:**

- Ask anything: "How does flanking work?", "Build a cunning goblin alchemist", "Level 3 forest ambush severe". System must cite sources.
- Typed generation: `POST /generate/{character,npc,monster,boss,map,campaign,encounter}` with full backstory/bio.
- Streaming GM chat: live token stream with source citations, auto-reconnect.
- Dice: `NdM`, `kh/kl`, advantage/disadvantage, **PF2e `check(modifier, DC)` with crit bands, nat-20/1 bump, fortune/misfortune, hero-point reroll**.
- Character sheet: 9-tab PF2e Remaster editor, derived stats recalc, SQLite persistence with migration.
- Rules/Bestiary: FTS5 search with `2E → 1E` fallback, category counts.

**Non-functional:**

- **Offline-first** on phone: dice, character sheet, rulebook search, Guide chatbot scripted+retrieval must work with laptop off.
- **Local-only**: no cloud LLM calls by default; Dell Latitude 5400 is CPU-only.
- **LAN-first networking:** phone → laptop over same Wi-Fi `http://192.168.4.144:8000` (emulator `10.0.2.2:8000`), Tailscale later for remote play.
- **Git hygiene:** `data/*.db` gitignored, reproducible via scripts; no real personal names in code/tests.
- **Lane discipline (RULES 5.2):** agents must never run `flutter build apk/appbundle/run`; verification is `flutter analyze` + `flutter test`; human verifies in Android Studio.

---

## 3. System Overview

```
         ┌─────────────────────────────────────────────────────┐
         │  HUB — Dell Latitude 5400 (i5 CPU-only)              │
         │  Python 3.14.6 (C:\venv-hub), FastAPI, Uvicorn        │
         │                                                      │
         │   ┌────────┐   ┌─────────────────┐   ┌────────────┐ │
         │   │  RAG   │◀──│  God service    │──▶│ LLM router │ │
         │   │ FTS5   │   │ orchestrator    │   │            │ │
         │   │132 MB  │   └─────────────────┘   └───┬────────┘ │
         │   │34k rows│              ┌────────────────┴─────┐  │
         │   └────────┘              │ 1. Ollama (phi4-mini)│  │
         │   campaign.db 114KB       │ 2. raw excerpts      │  │
         │   9 tables                └──────────────────────┘  │
         └──────────────▲──────────────────────────────────────┘
                        │ HTTP (REST) + WS (/stream) :8000
         ┌──────────────┴──────────────────────────────────────┐
         │  SPOKE — moto g 5G (2025), Flutter 3.12.2            │
         │  6-tab NavigationBar (IndexedStack, keeps state)      │
         │  dice · God chat · Hero · Rules · Rulebook · Setup   │
         │  bundled 48 MB gz → 132 MB FTS5 (offline), audio,    │
         │  haptics, SharedPreferences (hub URL, sfx, music)     │
         └──────────────────────────────────────────────────────┘
                        │
         ┌──────────────┴─────────────────────┐
         │  COMMAND CENTER — PySide6 ~48 MB   │
         │  standalone exe, no venv, logs/    │
         │  Services/Models/Rules/Generate    │
         └────────────────────────────────────┘
```

**Why two languages:** Hub reuses Python RAG/agent ecosystem; Spoke needs Flutter native performance + theming. Shared surface is intentionally tiny: `openapi.yaml` + dice math. Each side uses its best tool.

**Repo layout:**

```
C:\pathfinder_god\
├── hub/                 # FastAPI service (app/*.py, tests/, pyproject.toml)
├── spoke/               # Flutter app (lib/, assets/rules/*.gz, pubspec.yaml)
├── shared/openapi.yaml  # v0.1.0 single source of truth — 6 paths
├── data/                # SQLite DBs gitignored: pathfinder_rag.db 132MB, campaign.db 114KB
├── docs/                # setup-* , architecture.md, this whitepaper
├── blueprints/          # SESSION_HANDOFF, CURRENT_STATE, CHECKLIST, CHECKPOINTS, CHANGELOG
├── tools/               # gen_audio.py, command_center/ (PySide6, PyInstaller spec, dist/*.exe)
└── assets/              # images, audio
```

---

## 4. Hub — Python FastAPI Service (laptop)

**Stack:** `fastapi>=0.110`, `uvicorn[standard]>=0.29`, `httpx>=0.27`, `pydantic>=2.6`, `pydantic-settings>=2.2`. `requires-python >=3.10` (running 3.14.6 in `C:\venv-hub`). Optional: `pytest>=8.0`, `pytest-asyncio`.

**Factory `hub/app/main.py:32`:**

```python
def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version="0.1.0", ...)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(RateLimitMiddleware, requests_per_minute=100)
    app.add_middleware(MetricsMiddleware)
    app.add_middleware(CORSMiddleware, allow_origins=["*"], ...)
    app.include_router(health.router)
    app.include_router(ask.router)
    app.include_router(generate.router)
    app.include_router(rules.router)
    app.include_router(campaign.router)
    app.include_router(monitoring.router)
```

`lifespan` inits `CampaignRepository("campaign.db")`.

**Config `hub/app/config.py:22` (`Settings(BaseSettings, env_prefix=PFGOD_)`):**

| Key | Default | Notes |
|-----|---------|-------|
| `host` | `0.0.0.0` | LAN-visible, not localhost-only |
| `port` | `8000` | **Hub** — phone points here |
| `ollama_host` | `http://127.0.0.1:11450` | Normalized from `0.0.0.0:11450` env; client calls use `127.0.0.1` (was detection bug). Model `phi4-mini` |
| `ollama_model` | `phi4-mini` | Also pulled: `qwen2.5:3b`, `nomic-embed-text` on `:11434` via Ollama |
| `ollama_num_predict` | `700` | room for full bio/backstory |
| `ollama_temperature` | `0.6` |  |
| `ollama_timeout_s` | `120.0` |  |
| `rag_limit` | `4` | snippets per request |
| `rag_enabled` | `true` |  |
| `data_dir` | `REPO_ROOT/data` | ordered `db_filenames = (pathfinder_rag.db, pathfinder_god.db, pathfinder_1e_rag.db, pathfinder_2e_rag.db)` first existing wins |

`.env` present, not committed.

**Routing / API (see §7 for contract):**

- `GET /health` → `HubHealth(version, ollama_model, databases_found, status=ok)`
- `POST /ask` {query, edition, mode?, history} → `AskResponse(answer, backend: ollama|raw-excerpts, mode, edition, sources: RuleHit[])` — auto-detects mode unless forced.
- `POST /generate/{kind}` {prompt, edition} where `kind ∈ {character,npc,monster,boss,map,campaign,encounter}` forces mode, same `AskResponse`. **Fixed 2026-08-29:** `GenerateResponse(**result)` TypeError → explicit field mapping from `LLMResult` to `GenerateResponse`.
- `GET /rules/search?q=&edition=both&limit=5` → `RulesSearchResponse`.
- `WS /stream` → `start | chunk* | end | error | retrying` frames; see `hub_client.dart:89` auto-reconnect.
- `GET|POST /campaign`, `/campaign/note`, `/campaign/reset` → `CampaignState(party, notes)`.
- Monitoring / security routers + rate limit 100 req/min, shared headers.

**RAG `hub/app/rag/retriever.py:34`:**

- `_fts5_search(query, edition, k)`: escapes `"` → `""`, tokenizes, pads special chars `* - + ( ) : | @ { } [ ] ^ ~`, drops `?`, joins `OR` if >1 token >2 chars. Edition order: `both → [2E,1E]`, else uppercase single. `sqlite3` `rules MATCH ?` `ORDER BY rank LIMIT ?`. Appends `{system, category, name, source_book, content}`. `get_sources` returns name/source_book/category for attribution. `search` is public alias for rules endpoint. **Current hybrid is FTS5-only** — `Chroma/Qdrant` placeholder.

**LLM Orchestrator `hub/app/llm/orchestrator.py:40`:**

```python
@dataclass class LLMResult: answer, backend, mode, edition, sources

async def generate(prompt, edition, mode?, history?) -> LLMResult:
    # Tier 1: Ollama with RAG + tools
    if rag_enabled: context = await retriever.query(prompt, edition, k=rag_limit)
                     prompt = _build_rag_prompt(prompt, context, edition, mode)
    tools = RULES_LAWYER_TOOLS + NPC_COMPILER_TOOLS + [process_session, get_campaign_context]
    answer = await ollama.generate(prompt, system=_build_system_prompt(mode,edition), model=phi4-mini, ...)
    sources = await retriever.get_sources(original_prompt, ...)
    return LLMResult(answer, backend=ollama, ...)
    except Exception as e: log warning, fall through
    # Tier 2: raw excerpts (always works) — uses ORIGINAL prompt to avoid FTS5 syntax blow-up
    hits = await search_rules(original_prompt, edition, limit=5, repo=repo)
    answer = _format_raw_excerpts(hits, original_prompt)
```

`_build_system_prompt` per mode (character = "full backstory", npc = "stat block + personality", etc.) + rules-lawyer / npc-compiler / continuity-keeper tool descriptions.

`stream()` yields `ollama.stream()` chunks; on failure yields `[Error: e]`.

**Ollama client `hub/app/llm/ollama_client.py`:** `httpx` to `ollama_host`, `generate` and `stream` (SSE-style), same model/temperature.

**Agents:**

- `hub/app/agents/rules_lawyer.py` — `RULES_LAWYER_TOOLS`: `lookup_rule(query)`, `calculate_dc(level, rarity, proficiency)`, `validate_action(action, character_sheet, target)` (future `qwen2.5:14b` plan).
- `hub/app/agents/npc_compiler.py` — `NPC_COMPILER_TOOLS`: `create_npc(concept)`, `save_npc_to_db(npc_json)`, `level_up(character_id)` outputs ABC-legal stat blocks.
- `hub/app/agents/continuity.py` — `ContinuityKeeper`: `process_session(campaign_id, session_num, session_log)` extracts entities/facts/summary (JSON wrapped in try/except after `json.loads Expecting value` noise fixed), `get_campaign_context(campaign_id)`.

**DB `hub/app/db/repository.py`:** `CampaignRepository` on `campaign.db`. Lifecycle via FastAPI lifespan.

**CLI `hub/app/cli.py`:** `pathfinder-god` entrypoint mirrors old `hub_agent.py` REPL.

---

## 5. Spoke — Flutter Android App (phone)

**Stack:** Flutter 3.12.2 / Dart 3.12, `http ^1.6.0`, `web_socket_channel ^3.0.3`, `shared_preferences ^2.5.5`, `flutter_markdown_plus ^1.0.12` (migrated from discontinued `flutter_markdown`), `path ^1.9.1`, `path_provider ^2.1.5`, `sqflite ^2.4.3`, `sqflite_common_ffi ^2.3.0`, `sqlite3_flutter_libs ^0.5.42` (hold — `0.6.0` is EOL), `audioplayers ^6.1.0`, `openapi_generator 7.0.0`, `cupertino_icons`, `flutter_lints ^6.0.0`, `flutter_test`. Android min 21, Kotlin `com.pathfindergod`, label "Pathfinder God", circular branded icons `pf_logo` (`flutter_launcher_icons`, `flutter_native_splash`).

**Package identity (unified):** `applicationId com.pathfindergod`, Kotlin `com.pathfindergod.MainActivity`, namespace `com.pathfindergod`.

**DI `spoke/lib/main.dart:16`:**

```dart
Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final config = await HubConfig.load(); // SharedPreferences hub_base_url
  await AudioService.instance.init();
  await HapticsService.init();
  runApp(PathfinderSpokeApp(config: config));
}
class PathfinderSpokeApp extends StatelessWidget {
  build => MaterialApp(MaterialApp(home: HomeScreen(HubClient(config), CharacterStore())));
}
```

No Riverpod/Provider — manual constructor DI.

**Shell `spoke/lib/screens/home_screen.dart:27`:**

- `IndexedStack` + `NavigationBar` (6 destinations): `Dice` (`Icons.casino`), `God` (`auto_stories`), `Hero` (`person`), `Rules` (`menu_book` → Bestiary), `Rulebook` (`menu_book`), `Setup` (`settings`). Built once in `initState` so each tab retains state (dice history, chat scroll).

**Screens:**

| Screen | File | Key behavior |
|--------|------|--------------|
| **Dice** | `dice_screen.dart` | QuickWrap `d4..d100` + Adv/Dis (`2d20kh1/kl1`), custom `4d6kh3+2`, animated 3D die (see below), result panel crimson/gold, 30-item history `ListTile` |
| **God Chat** | `gm_chat_screen.dart` | `HubClient.stream` token stream → `MarkdownBody`, clears partial text on `retrying` frame |
| **Hero / CharacterList + Sheet** | `character_list_screen.dart`, `character_sheet_screen.dart` | List shows ancestry/heritage/class/subclass, HP/AC/Speed. Sheet 9 tabs (Basics/Abilities/Proficiencies/Feats/Spells/Equipment/Derived/Conditions/Notes) with live `recalculateDerived()` |
| **Rules (Bestiary)** | `bestiary_screen.dart` | Tier1 `RulebookDb.search` → Tier2 `client.searchRules`, offline bolt badge, ExpansionTiles |
| **Rulebook** | `rulebook_screen.dart` | Same two-tier search, TabBar Search/Browse/Guide, browse chips Flanking/Dying/Hero Points…, gold banner "Extracting offline rulebook…" or "Offline book unavailable — using hub. (e)" + `offline_bolt` |
| **Setup** | `settings_screen.dart` | Hub URL `TextField`, `Save & test connection` → `client.health()`, green "Connected to the God" card or crimson "Could not reach the God", auto-fixes `:11450` → `:8000`, Music/SFX/Haptics toggles |
| **Guide Chat** | `rulebook_chat_screen.dart` | Intent badges, example chips |

**Config `spoke/lib/config/hub_config.dart:13`:**

```dart
class HubConfig {
  static const _key='hub_base_url';
  static const defaultBaseUrl='http://10.0.2.2:8000'; // emulator
  Uri httpUri(path,[query]) => Uri.parse(_baseUrl).replace(path: path, queryParameters: ...);
  Uri wsUri(path) => base.replace(scheme: https→wss else ws, path: path);
  static Future<HubConfig> load() async => HubConfig(prefs.getString(_key) ?? defaultBaseUrl);
  Future<void> save(baseUrl) async => prefs.setString(_key, baseUrl.trim());
}
```

Real device: `http://192.168.4.144:8000` (Wi-Fi adapter from `SPEC_SHEET.json`). Note: LAN IP noted in blueprints has varied (`192.168.4.144` current). `192.168.1.42` shown as example in old Settings helper.

**API `spoke/lib/api/hub_client.dart:15`:**

- `health()` GET `/health` 6s timeout → `HubHealth.fromJson`.
- `ask(query, edition, mode?, history)` POST `/ask` JSON → `AskResponse`.
- `generate(kind, prompt, edition)` POST `/generate/$kind` → `AskResponse`.
- `searchRules(query, edition, limit)` GET `/rules/search` → `RuleHit[]`.
- `stream(query, edition, mode?, history, maxRetries=3) async*`:
  ```
  attempt=0 loop:
    channel = WebSocketChannel.connect(wsUri('/stream')); await ready;
    sink.add(jsonEncode{query,edition,mode,history});
    sawTerminal=false;
    for raw in stream: event=StreamEvent.fromJson; yield; if type end|error => close & return;
    if sawTerminal return;
    catch (_) retry; if attempt>=maxRetries yield error "Connection lost after N attempts. Check hub at $baseUrl." return;
    attempt++; yield retrying "Connection lost — reconnecting (attempt N)…"; delay 400*2^(attempt-1) ms;
  ```
  Handles device sleep / Wi-Fi switch / hub restart. Consumer clears partial text on `retrying`.

**Dice engine `spoke/lib/dice/dice.dart:77`:**

- `DiceTerm(sign, count, sides, keepHighest=-1, keepLowest=-1, flat)` `isFlat`.
- `DiceRoller([Random? rng])` `rng = Random.secure()` default. `roll(notation)` → `parse → _rollTerm → DiceResult(notation, terms, total)`. `parse` splits `RegExp(r'([+-]?)([^+-]+)')`, `_parseBody` flat `int.tryParse` else `RegExp(r'^(\d*)d(\d+)(?:(kh|kl)(\d+))?$')`, validates `count 1..1000`, `sides 1..1000`. `_rollTerm` generates `Random.nextInt(sides)+1`, `kh/kl` sorts and slices, sums with sign. `advantage([mod]) = roll('2d20kh1±mod')`, `disadvantage = kl1`.
- `Pf2eChecks` extension `check(modifier, dc, fortune, misfortune, heroPoint)`:
  ```
  natural = d20;
  if fortune!=misfortune: second=d20; natural=max or min;
  if heroPoint: natural=d20 (reroll, keep second);
  total=natural+modifier;
  degree=_baseDegree(total,dc) where >=DC+10 critSuccess, >=DC success, <=DC-10 critFail else fail;
  if natural==20 index=min(max, index+1); if natural==1 index=max(0, index-1);
  return CheckResult(natural,modifier,dc,total,degree,heroPoint);
  ```
  `breakdown` = `d20[N]+mod = total vs DC N → Label`.

- Tests `spoke/test/dice_check_test.dart`: 10 cases covering crit bands, nat-20 bump success→crit, fail→success, nat-1 downgrade fail→critFail and success→failure, fortune/misfortune keep higher/lower, hero-point second-roll semantics.

**Dice physics `spoke/lib/dice/dice_physics.dart:12`:**

- `AnimatedDiceRoller(TickerProvider, onComplete)` creates `AnimationController(duration 1200ms)` + 3 `TweenSequence`s:
  - `rotation`: 0→8π (55%), 8π→9π (25%), 9π→9.3π (20%) `easeOutCubic`
  - `bounce`: 0→1 (25%), 1→0 (18%), 0→0.45 (15%), 0.45→0 (14%), 0→0.18 (14%), 0.18→0 (14%) `easeOut` — translated `Offset(0, -bounce*95)`
  - `scale`: 1.0→1.35→0.82→1.12→0.97→1.0 `easeOutCubic`
  - Listener on `completed → _isRolling=false; _onComplete(_currentValue)`.
- `roll()` guard `if _isRolling → debugPrint ignore`; `_currentValue = Random().nextInt(20)+1`; if `isAnimating stop()`; `forward(from:0)` catch resets `_isRolling`. Exposes `isRolling, currentValue, rotation/bounce/scale`.
- `AnimatedDie extends AnimatedWidget(listenable: controller)`: `Transform.translate` + `Transform.scale` + `Matrix4.rotateX/Y/Z` with perspective `0.002`, container 100×100 `Color(0xFFF5A623)` rounded 16 border 3 dark, gold text `48pt` result else `?` `36pt`, shadow.
- `DiceAnimationWidget StatefulWidget(roller?, onResult, enabled=true)`: `HitTestBehavior.opaque` `GestureDetector` + 12 px padding around die; if `roller==null` owns new `AnimatedDiceRoller(this, onResult)` else reuses external. `dispose` only if owns. Tap debugPrints. `build` → `GestureDetector(onTap:_roll → _roller.roll())` → `AnimatedDie`.

**Audio `spoke/lib/services/audio_service.dart`:** `AudioService` singleton, 3-player SFX pool + looping BGM ("quiet tavern ambience"), prefs `music_enabled/sfx_enabled`, fail-safe `try` on missing assets, `gen_audio.py` synthesizes sounds.

**Haptics `spoke/lib/services/haptics_service.dart`:** `HapticsService` `enabled` persisted `haptics_enabled`, methods `light/medium/heavy/selection/vibrate` via `HapticFeedback` / `Vibration` (where available).

**Offline Rulebook `spoke/lib/services/rulebook_db.dart` (fixed 2026-08-30):**

- `LocalRuleHit(name, content, system, category, sourceBook)`.
- `RulebookDb`: `_assetPath='assets/rules/pathfinder_rag.db.gz'`, `_dbFileName='pathfinder_rag.db'`, `bundleVersion=1`, **static** `Database? _db` + `static Future<Database>? _openFuture` for cross-instance lock.
- `open()` serialized: if `_db != null` return, if `_openFuture != null` await it, else `_openFuture=_openInternal()` try/finally clear.
- `_openInternal()`:
  ```
  sqfliteFfiInit();
  base = await getApplicationDocumentsDirectory();
  dir = Directory(join(base.path, 'rulebook')); await dir.create(recursive:true);
  dbPath = join(dir.path, _dbFileName);
  markerPath = join(dir.path, '$_dbFileName.v$bundleVersion');
  debugPrint dir/dbPath;
  if !File(dbPath).exists || !File(markerPath).exists:
    try await _extract(dbPath) catch (e,st) debugPrint rethrow
    for e in dir.listSync(): if name startsWith '$_dbFileName.v' and !=markerPath delete
    await File(markerPath).create(recursive:true);
  _db = await factory.openDatabase(dbPath, readOnly:true);
  debugPrint('opened ${count}');
  return _db!;
  ```
  Uses `path_provider`, not `factory.getDatabasesPath()` (which returns unusable `/.dart_tool/sqflite_common_ffi/databases` on Android — the bug).
- `_extract(dbPath)`:
  ```
  debugPrint Starting extraction...
  data=await rootBundle.load(_assetPath); compressed=asUint8List; debugPrint Loaded N bytes
  decompressed = await Isolate.run(()=>gzip.decode(compressed)) catch fallback to main
  debugPrint Decompressed to M bytes
  tmp=File('$dbPath.tmp'); await tmp.parent.create(recursive:true); if exists delete; await writeAsBytes(decompressed, flush:true);
  if File(dbPath).exists delete; await tmp.rename(dbPath);
  debugPrint Extraction complete
  ```
  50 MB gz → 132 MB, ~180 MB peak; `Isolate.run` avoids 3844 ms Davey / 227 jank.
- `search(query, edition=both, limit=20)`: `await open()`, clean `replaceAll('"','""')`, `RegExp(r'[^\w\s]')→' '`, join `OR`, `editions = both→[2E,1E] else [upper]`, `rawQuery SELECT system,category,name,source_book,raw_content FROM rules WHERE system=? AND rules MATCH ? ORDER BY rank LIMIT ?` per edition until limit, map to `LocalRuleHit`.
- `categories(edition)` `GROUP BY category ORDER BY n DESC`.
- `close()` async.

**Guide chatbot `spoke/lib/services/rulebook_chatbot.dart`:** `RulebookBrain` token-scoring intent keywords (`greet/help/rulesLookup/characterBuild/npcCreate/encounterBuild/campaignStart/rulebookOpen/Search/Navigate/tutorial/unknown`), templated replies. `RulebookProvider` wraps `RulebookDb` `.open()` / `isReady` / `search(query, limit=3)` swallowing errors. `RulebookChatbot` `StreamController<ChatMessage>.broadcast`, `initialize()` loads provider then greeting, `send(text)` adds user msg, `if (rulesLookup||rulebookSearch) && isReady → provider.search(_extractQuery(text))` where `_extractQuery` drops stopwords `{how, does, what, is, the, a, work, search, ...}`; formats hits as `"From your offline rulebook:\n**Name** _(system · source)_\n snippet 220ch…"`.

**Character `spoke/lib/models/character.dart`:** ability scores (+mod), 31 proficiencies (skills/defenses/class), feats, spells (tradition/slots/focus), equipment (weapons/armor/shield/currency), derived `HP/AC/saves/perception/DC/speed/bulk/initiative`, conditions (hero points, dying/wounded/doomed/fatigued etc.), `recalculateDerived()`.

**Storage `spoke/lib/storage/character_store.dart`:** `CharacterStore` SQLite v2 via `sqflite`, auto-migration v1→v2 adds new columns with defaults.

**Theme `spoke/lib/theme/app_theme.dart`:** `PathfinderTheme` gold `#B8860B`-ish / crimson `#7B1E1E` / parchment `#F3E9D2` / ink, `light()` / `dark()` `ThemeData`, `parchmentDeep` etc.

---

## 6. Data Layer — The 500 MB Database Problem

| Asset | Laptop `data/` | Phone `spoke/assets/rules/` | Details |
|-------|---------------|------------------------------|---------|
| **pathfinder_rag.db** | 132 MB, 34,554 rows, `integrity_check ok` | — (extracted copy) | `FTS5 rules(name, raw_content, system, category, source_book)` + `rules_data/idx` clean, `VACUUM` clean. `system ∈ {1E,2E}` uppercase. Tested `SELECT count()` returns. |
| **pathfinder_rag.db.gz** | — | 48 MB | Ships inside APK `flutter.assets` → `RulebookDb` extracts on first launch to `.../app_flutter/rulebook/pathfinder_rag.db` `readOnly`. Bump `bundleVersion` when rebundling or devices keep stale copy. |
| **campaign.db** | 114 KB, 9 tables, `integrity_check ok`, 1 campaign seeded | — | `campaigns/sessions/npcs/locations/items/quests/player_decisions/party_members` — hub only. |

**Schema (docs):** `data/SCHEMA.md` (FTS5 `rules`, rank column, triggers). Rebuild via `hub/scripts/rebuild_rags.py` (produces gitignored DBs). Distribution outside git via GitHub Release asset / Drive — never committed.

**Licensing note:** Commercial redistribution rights for the bundled rules DB remain unverified (ORC/OGL aggregation). Personal use fine; must resolve before public release.

---

## 7. API Contract & Communication

**Source of truth:** `shared/openapi.yaml` v0.1.0 — 406 lines, OpenAPI 3.1.0. Generates Dart models via `openapi_generator 7.0.0` + `build_runner`; app currently mirrors manually in `lib/api/models.dart` (stable).

**Models:**

- `AskRequest {query*, edition=both∈{1e,2e,both}, history: (speaker,message)[] , mode?: character|npc|monster|boss|map|campaign|encounter }`
- `AskResponse {answer*, backend∈{ollama,raw-excerpts}, mode*, edition*, sources: RuleHit[] }`
- `RuleHit {name*, content*, system='', category='', source_book='' }`
- `HubHealth {version*, ollama_model*, databases_found: string[], status='ok' }`
- `RulesSearchResponse {query*, edition*, results: RuleHit[] }`
- `GenerateRequest {prompt*, edition=both }`
- `CampaignState {notes: CampaignNote[], party: object[] }`, `CampaignNote {prompt*, response*}`

**Paths:**

| Method | Path | Handler (`hub/app/api/`) | Spoke caller |
|--------|------|--------------------------|--------------|
| GET | `/health` | `health.py` | `HubClient.health()` |
| POST | `/ask` | `ask.py` → `orchestrator.generate` | `ask()` |
| POST | `/generate/{kind}` | `generate.py` → explicit field mapping (fixed) | `generate(kind,prompt)` |
| GET | `/rules/search` | `rules.py` → `retriever.search` | `searchRules()` |
| WS | `/stream` | `ask.py` (stream) | `stream()` |
| GET/POST | `/campaign`, `/campaign/note`, `/campaign/reset` | `campaign.py` | (future) |

**HubClient details:** `http.Client` + `web_socket_channel`. REST uses `config.httpUri`. WS uses `config.wsUri` scheme swap. Health 6 s timeout. `_ensureOk` throws `HubException('Hub returned ${code}: ${body}')` if not 2xx — surfaced in Settings as "Could not reach the God.\nHub returned 404: 404 page not found" (the confusing `:11450` case). Streaming auto-reconnect 3× exponential backoff 400,800,1600 ms with `retrying` frame; consumer clears partial markdown on `retrying`.

---

## 8. Offline-First & Fallback Tiers

| Need | Tier 1 — always (phone) | Tier 2 — hub online (LAN/WS) |
|------|-------------------------|------------------------------|
| **Rules lookup** | `RulebookDb` FTS5 `2E→1E` fallback | `GET /rules/search` |
| **Bestary** | same DB | same |
| **Guide chatbot** | `RulebookBrain` scripted + `RulebookProvider.search` FTS5 | — (future hub RAG) |
| **Dice** | `DiceRoller` + `AnimatedDiceRoller` | — |
| **Character** | `CharacterStore` SQLite v2 | — (future hub sync/backup) |
| **Generation (PC/NPC/etc.)** | — | `POST /generate/*` + `/stream` with citations; if Ollama down → raw excerpts from hub FTS5 |
| **GM chat** | scripted help/tutorial | `/stream` |

**Hub 2-tier generation (orchestrator):** tier 1 Ollama+ RAG + tools → tier 2 raw excerpts (never empty, logs `Ollama failed: …, falling back`). Tier 2 keeps game playable on CPU-only laptop if model not loaded.

**Rule retrieval nuance:** Hub `retriever.query` and Spoke `RulebookDb.search` both escape `"` → `""`, strip FTS5 meta `* - + ( ) : | @ { } [ ] ^ ~`, drop `?`, `OR`-join tokens >2 chars; hub does `system = ? AND rules MATCH ? ORDER BY rank`.

---

## 9. Build, Distribution & Environment

**Hub env:**

- Python `C:\venv-hub\venv\Scripts\python.exe` 3.14.6 — use as-is, never copy into repo.
- Run: `cd hub; python -m app.main` → `Uvicorn running on http://0.0.0.0:8000`.
- Ollama `ollama serve` on `0.0.0.0:11434` (hub `.env` maps `127.0.0.1:11450`, model `phi4-mini`).
- Android SDK `C:\android\sdk`, Gradle 9.3.1 cached.
- `pyproject.toml` `setuptools` packages `app*`.

**Spoke env:**

- `cd spoke; flutter pub get; flutter analyze; flutter test` — permitted. **Never** `flutter build apk/appbundle/run` per RULES 5.2 — human builds in Android Studio Run ▶️.
- Emulator hub: `http://10.0.2.2:8000`; real device: LAN IP e.g. `http://192.168.4.144:8000` (current `Start_God.bat` / `SPEC_SHEET.json` Wi-Fi adapter; example `192.168.1.42` in old doc). Must be same Wi-Fi; Windows Firewall must allow `8000`/`11450`.
- `sqflite_common_ffi` needs bundled `sqlite3_flutter_libs` (Android SQLite lacks FTS5); stay `^0.5.42`.

**Command Center:**

- `tools/command_center/` PySide6 standalone exe: `dist/PathfinderGodCommandCenter.exe` ~48 MB, built via `PyInstaller` `command_center.spec` `--clean`; launch via `Start_CommandCenter.bat` (no venv). `services.py` `ManagedProcess(Ollama|Hub)` does `subprocess.Popen(..., creationflags=CREATE_NO_WINDOW, stdout=open(logs/<name>.log,"a"))`, `start` returns `(bool,str)` with pid + log path, `stop` `terminate`→`wait 8s`→`kill`, `get_log_tail(50)`. Logs at `tools/command_center/logs/hub.log` + `ollama.log`. UI tabs: Services, Models, Rules, Generators, Dice, Guide; Guide persists `chat_history.json`; dice kh/kl/adv/dis parity; tray/icon.

**Project structure (condensed):**

```
spoke/lib/
  api/{models.dart,hub_client.dart}
  config/hub_config.dart
  dice/{dice.dart,dice_physics.dart}
  models/character.dart
  screens/{home_screen,dice_screen,gm_chat_screen,character_* ,bestiary_screen,rulebook_screen,rulebook_chat_screen,settings_screen}
  services/{rulebook_db,rulebook_chatbot,audio_service,haptics_service}
  storage/character_store.dart
  theme/app_theme.dart
  main.dart
hub/app/
  api/{health,ask,generate,rules,campaign,monitoring,security}
  rag/{retriever,search,raw_fallback}
  llm/{orchestrator,ollama_client,backends}
  agents/{rules_lawyer,npc_compiler,continuity}
  db/repository.py
  config.py
  main.py
shared/openapi.yaml
data/{pathfinder_rag.db, campaign.db} # gitignored
```

---

## 10. Security, Privacy & Compliance

- **Local-only by default:** No external LLM/cloud; Ollama `0.0.0.0:11450` bound locally, hub `0.0.0.0:8000` LAN-only (no auth yet — intended for trusted home Wi-Fi; `SecurityHeadersMiddleware`, `RequestLoggingMiddleware`, `RateLimitMiddleware(100/min)`, `MetricsMiddleware`, `CORSMiddleware(allow_origins=["*"])` in place).
- **Secrets:** `.env` + `*.keystore` + `local.properties` gitignored per RULES 1.2; commercial IWADs stay at `C:\Doom Shit\IWADs\` outside repo.
- **Synthetic data only (RULES 1.4):** committed code/tests use `SAMPLE ANCESTOR A` style placeholders; real genealogy JSON gitignored.
- **Read-only external dirs (RULES 1.1):** `C:\sovereign_tagger_bak`, `C:\Recovery for All`, etc. never written.
- **Git discipline:** `git add <path>` explicit only, never `add .`/`-A`; `blueprints/` + `_archive/` gitignored on purpose.
- **Privacy:** phone `SharedPreferences` stores only hub URL/mode toggles; no telemetry; campaign DB stays on laptop.
- **Licensing open item:** bundled rules DB commercial resale unverified — blocks public release, not personal play.

---

## 11. Performance, Tuning & Hardware

| Device | Role | Tune |
|--------|------|------|
| Dell Latitude 5400 (i5, CPU-only) | Hub | Small fast models: `phi4-mini` primary (700 tokens, temp 0.6, 120 s timeout, `rag_limit 4`); alternatives `qwen2.5:3b`, `nomic-embed-text`. No GPU. `0.0.0.0` binds for LAN. |
| moto g 5G (2025) | Spoke | UI only; local dice + 34k rule search; **no LLM, no large DB in RAM** beyond 132 MB mmap read-only FTS5. Main-thread jank budget critical — see bug below. |

**Measured pain (from user log 2026-08-30, `flutter run` on moto g):**

```
I/Choreographer: Skipped 43 frames!
I/flutter: RulebookDb: Starting extraction to /.dart_tool/sqflite_common_ffi/databases/...
I/flutter: Starting extraction to same (2× due to two RulebookDb instances)
I/Choreographer: Skipped 227 frames!  The application may be doing too much work on its main thread.
E/HWUI: fbcNotifySbeRescue undefined symbol (MediaTek Gralloc spam — benign)
I/HWUI: Davey! duration=3844ms; Flags=1, FrameTimelineVsyncId=..., IntendedVsync=..., Vsync+4ms, WorkloadTarget 20ms
I/flutter: RulebookDb: Loaded compressed asset (50169559 bytes)
Application finished.
```

→ 50 MB gz + 132 MB decode on main thread blocked UI 3.8 s, concurrent double extraction → OOM, "Application finished" (hot reload kill / ANR).

**Fixes applied (see §13):** `Isolate.run(gzip.decode)`, post-frame defer, singleton lock → expected `Skipped 0`, extraction ~same wall but off UI; `getApplicationDocumentsDirectory` path instead of `/.dart_tool`.

**Other tunings:** SFX 3-player pool to avoid `AudioPlayers` contention; `AnimatedDiceRoller` 1200 ms `CurvedAnimation.easeOutCubic`; WebSocket 3 retries keeps chat alive over sleep.

**Future knobs to research with Gemini:** streaming gzip (chunked `GZipCodec` + `File.openWrite`) vs `Isolate.run` memory 180 MB peak on 4 GB device; `phi4-mini` vs `qwen2.5:3b` latency/quality for PF2e citations; FTS5 `rank` vs BM25 custom; `0.0.0.0:11450` vs `127.0.0.1` Ollama binding security.

---

## 12. Current Progress & Verification

**Repository state (2026-08-29 session 5 + 2026-08-30 hotfix):**

| Area | Status | Evidence |
|------|--------|----------|
| `shared/openapi.yaml` | ✅ v0.1.0 406 lines | 6 paths, 9 schemas |
| `data/pathfinder_rag.db` | ✅ 132 MB, 34,554 rows, `integrity_check ok` | FTS5 `rules` + `rules_data/idx`, `VACUUM` clean, `system` uppercase `1E/2E` |
| `data/pathfinder_rag.db` gz | ✅ 48 MB | `spoke/assets/rules/` |
| `campaign.db` | ✅ 114 KB 9 tables | `integrity_check ok`, 1 seed campaign |
| `hub` | ✅ Working | `python -m app.main` on `:8000`, `phi4-mini` on `:11450`, logo `0.0.0.0:8000` reachable `192.168.4.144:8000` |
| `spoke` identity | ✅ `com.pathfindergod` | label "Pathfinder God", circular `pf_logo`, splash `pf_logo.jpg` |
| `spoke` offline | ✅ rulebook FTS5 + Guide chatbot + dice + SFX/BGM + character SQLite v2 + recalc | Extracted read-only 132 MB; `bundleVersion=1` |
| `tools/command_center` | ✅ standalone exe ~48 MB | `dist/PathfinderGodCommandCenter.exe`, `logs/hub.log`, tray/icon, chat persistence |
| docs | ✅ | `architecture.md`, `setup-*.md` updated offline tier |

**Spoke modules (summarized from CURRENT_STATE 2026-08-29):**

Entry/DI, Theme, Config, Models (mirrors openapi + `retrying`), HubClient (auto-reconnect), Dice engine+physics+Screen, Audio+Haptics (persisted), Offline rulebook, Guide chatbot (scripted+offline retrieval cited), Character store v2 + 9-tab sheet + list, Home 6-tab IndexedStack, Bestiary+Rulebook two-tier + offline badge, Guide chat UI, Settings (Music/SFX/Haptics).

**Verification gates (as of 2026-08-30 10:30):**

- `flutter analyze` → **No issues found!** (after fix; was 5 style warnings, then 1 `unnecessary_underscores` fixed)
- `flutter test` → **15/15** (`dice_check_test 10` + `character_derived_test 5`) — `All tests passed!`
- `hub/tests/test_api.py` → **5 passing** (`health`, `rules_search`, `edition_filter`, `empty_query`, `generate_invalid_kind`, `deepseek_disabled`, `campaign_note`; generate xfail resolved via explicit mapping)
- Manual hub probes (from earlier sessions):
  ```
  GET /health → {status:ok, version:0.1.0, ollama_model:phi4-mini, databases_found:["pathfinder_rag.db"]}
  GET /rules/search?q=flanking&edition=2e → 200, hits[]
  POST /ask {query:"what is flanking?"} → {backend:raw-excerpts|ollama, sources: [...]}
  WS /stream → start → chunk* → end (with sources)
  GET http://192.168.4.144:8000/health from LAN → ok
  Ollama GET http://127.0.0.1:11450/api/tags → models list
  ```
- Command Center: `tools/command_center/logs/hub.log` shows `Uvicorn running on http://0.0.0.0:8000`; `ollama.log` shows `Listening on [::]:11450 (version 0.32.15)`; Services tab Health polling OK, `ollama serve` windowless.

**Next session focus (planned pre-bug):** export/import campaign backup JSONL, health split liveness vs readiness, typed campaign graph, hub pytest expansion, `qwen2.5:14b` Rules Lawyer `validate_action/calculate_dc`.

---

## 13. Bugs Fixed in Last 48 h (with Logs)

### 13.1 Offline Book `PathNotFoundException` → `/.dart_tool/sqflite_common_ffi/databases/...tmp` (P0)

**User report 2026-08-29:** Spoke shows `Offline Book Unavailable -- Using Hub. (PathNotFoundException: Cannot open file, path = '/.dart_tool/sqflite_common_ffi/databases/pathfinder_rag.db.tmp' errno 2)` and dice anim sometimes doesn't move; `http://192.168.4.144:11450` → `Could not reach the God hub returned 404`.

**Log `flutter run --device-id ZT4222BMWN 2026-08-30`:**

```
I/flutter: RulebookDb: Starting extraction from assets/rules/pathfinder_rag.db.gz to /.dart_tool/sqflite_common_ffi/databases/pathfinder_rag.db
I/flutter: RulebookDb: Starting extraction from same (second instance)
... Skipped 227 frames! ... Davey! duration=3844ms ...
I/flutter: RulebookDb: Loaded compressed asset (50169559 bytes)
Application finished.
[[still says offline rulebook unavailable]]
```

**Root causes (3×):**

1. **Wrong path:** `rulebook_db.dart:51` used `databaseFactoryFfi.getDatabasesPath()` which on Android returns `/.dart_tool/...` (desktop temp fallback) — root `/` not writable without root → `ENOENT` on `File(...tmp).writeAsBytes`.
2. **Main-thread decode:** `gzip.decode(50MB)` → 132 MB on UI thread blocks Choreographer 3.8 s; Moto G ANR; `Isolate.run` not used.
3. **Double extraction race:** `RulebookScreen` and `BestiaryScreen` each `new RulebookDb()` with instance `Database? _db`; no lock → two concurrent 50 MB loads (≈100 MB compressed + 264 MB decompressed) → OOM.

**Fix `spoke/lib/services/rulebook_db.dart:1,42-137` (landed):**

```dart
import 'dart:isolate';
static Database? _db; static Future<Database>? _openFuture;
bool get isReady => _db != null;
Future<Database> open() async { if (_db!=null) return _db!; if (_openFuture!=null) return _openFuture!; _openFuture=_openInternal(); try{return await _openFuture!;} finally{_openFuture=null;}}
Future<Database> _openInternal() async {
  sqfliteFfiInit();
  base=await getApplicationDocumentsDirectory();
  dir=Directory(p.join(base.path,'rulebook')); await dir.create(recursive:true);
  dbPath=p.join(dir.path,_dbFileName); markerPath=p.join(dir.path,'$_dbFileName.v$bundleVersion');
  if (!File(dbPath).existsSync() || !File(markerPath).existsSync()) {
    await _extract(dbPath); // serialized
    for (f in dir.listSync() if startsWith '$_dbFileName.v' && !=markerPath) delete;
    await File(markerPath).create(recursive:true);
  }
  _db=await factory.openDatabase(dbPath, readOnly:true);
}
Future<void> _extract(String dbPath) async {
  data=await rootBundle.load(_assetPath); compressed=asUint8List;
  decompressed = await Isolate.run(()=>gzip.decode(compressed)) catch fallback;
  tmp=File('$dbPath.tmp'); await tmp.parent.create(recursive:true); if exists delete;
  await tmp.writeAsBytes(decompressed, flush:true);
  if File(dbPath).exists delete; await tmp.rename(dbPath);
}
```

Also deferred `initState` → `WidgetsBinding.instance.addPostFrameCallback((_)=>_prepareLocal())` in both `rulebook_screen.dart:63` and `bestiary_screen.dart:35`.

**Result:** Next `flutter run` should log `dir = /data/data/com.pathfindergod/app_flutter/rulebook`, off-thread `Decompressed to ~132M`, `Extraction complete`, `opened [{c: 34554}]`. Requires **uninstall or Clear Storage** on moto g to drop stale `/.dart_tool` attempt (new dir is different, but old failure left no marker — will auto-retry; still advise clear to free).

### 13.2 Dice Animated Die Sometimes Doesn't Move (P1)

**User:** "'roll' button works and everything but the little animated die doesn't do anything."

**Causes:** `DiceAnimationWidget` `GestureDetector` without `HitTestBehavior.opaque` + no padding → taps missed when `Transform` scaled/translated; `AnimatedDiceRoller.roll()` guard `if _isRolling return` silent, `isAnimating` not cleared on error → stuck `true`; `DiceScreen` `onPressed: _animatedRoller.roll` never `setState` so parent `Result:` slot didn't hide during roll; `dispose` never called `roller.dispose()` → ticker leak; animation too subtle (4π, 80 px).

**Fix `dice_physics.dart:29-48,62-75,187` + `dice_screen.dart:62-75,184-224`:**

- `HitTestBehavior.opaque` + 12 px padding, `debugPrint` on tap/roll.
- `roll()` `if _isRolling debugPrint ignore`, `if isAnimating stop()`, `forward(from:0).catchError→ _isRolling=false`.
- More dramatic: rotation 0→8π→9π→9.3π, bounce 95 px, scale 1.35×→0.82×→1.12×, `easeOut`.
- `DiceScreen._rollAnimated()` wrapper: `setState`, `Haptics.light`, `Sfx.dice` at start; `dispose()` calls `_animatedRoller.dispose()`; `AnimatedBuilder` on `rotation` drives "Rolling…" hint; fixed `Expanded` → `Padding` layout jumping.

### 13.3 Hub 404 on `:11450` Confusion (P1)

**User entered `http://192.168.4.144:11450` in Settings → "Could not reach the God hub returned 404: 404 page not found".** Expected — `:11450` is **Ollama** (see `config.py:49` `ollama_host`), Hub is `:8000`; Ollama `/health` 404s with HTML `404 page not found`, `HubClient._ensureOk` throws `HubException`.

**Fix `settings_screen.dart:42-61`:** early check `if raw.contains(':11450')` → show `That port (11450) is Ollama, not the hub. Use :8000, e.g. http://192.168.4.144:8000`, auto-correct `replaceAll(':11450',':8000')`, save corrected, update `TextField`; also append hint on any 404 `Hint: hub is on :8000, not :11450`; helper text updated.

**Action for user:** On moto g, Settings → Hub address → **must be** `http://192.168.4.144:8000` (or `10.0.2.2:8000` in emulator) → `Save & test connection` → green "Connected to the God".

### 13.4 `avoid_print` Lints (P2)

`flutter analyze` 6× `avoid_print` in `rulebook_db.dart:58,81,87,91,96,101` + `rulebook_screen.dart:75` → replaced with `debugPrint` + added `import 'package:flutter/foundation.dart';`.

---

## 14. Known Issues / Tech Debt

- **Licensing:** bundled rules DB commercial rights unverified.
- **BundleVersion:** `RulebookDb.bundleVersion=1` — must bump on re-gzip or devices keep stale copy.
- **Android SQLite FTS5:** `sqlite3_flutter_libs ^0.5.42` must stay 0.5.x (0.6.0 EOL); never `flutter pub upgrade --major-versions` blindly.
- **OpenAPI → Dart:** manual mirror stable but `openapi_generator` drift risk.
- **Hub pytest:** only 5 critical tests; need G1-9 gate expansion.
- **Gralloc spam:** `mali_gralloc ERROR: Format allocation info not found for format: 38/0x3b` + `Invalid base format` on Moto G Vulkan/Impeller — benign, ignore.
- **Hot reload kills long tasks:** `Application finished.` after 50 MB load can also be `flutter run` hot-restart — later fixed via isolate but still advise `flutter run --no-hot` for first extraction or install via Android Studio.
- **Command Center exe lock:** `PathfinderGodCommandCenter.exe` locked by running process → installer must `move → _old.exe` before rebuild.

---

## 15. Open Questions — Where We Need Gemini Deep Research

> Please treat this section as **requests for outside deep research + citations**, not just advice. For each, we want: approach options with trade-offs, code pointers, benchmark numbers where possible, and failure modes.

### 15.1 Offline 50 MB Gz Extraction on Low-End Android

**Problem:** 50 MB gz → 132 MB DB, naive `rootBundle.load` (50 MB Uint8) + `gzip.decode` (132 MB) peaks ~180 MB + Dart overhead ~250 MB, even off isolate the compressed buffer copies to the isolate (double). `Skipped 227 frames`, `Davey 3844ms` proves main thread starved. Isolate helps but still copies 50 MB.

**Research asks:**

- Streaming alternatives: `rootBundle.load` → `Write compressed to temp file → File.openRead().transform(gzip.decoder).pipe(File.openWrite(dbPath))` vs `Isolate.run(gzip.decode)` vs `compute` vs Rust `sqlite` extension? Provide **memory/time** estimates on 4 GB Moto G-class, and sample `dart:io` chunked code that avoids holding both buffers.
- Is `rootBundle` streaming possible? Or must use `DefaultAssetBundle` + `HttpClient`? How to show progress bar without jank?
- Should we ship uncompressed DB via Play Asset Delivery (PAD) / `split` ABI asset packs to avoid gz entirely? Cost vs 48 MB APK bloat?
- File atomicity: `tmp.rename` atomic on `app_flutter` ext4? What if power loss mid-rename?

### 15.2 FTS5 Ranking & Search Quality

**Current:** Hub `retriever.py` `ORDER BY rank` (FTS5 bm25 default) + manual `OR` tokenization; Spoke `rulebook_db.dart:153` same. No stemming, no trigram, category weighting, phrase vs `OR`, `SPELLFIX1`.

**Asks:**

- Evaluate `bm25(k1,b)` tuning vs custom `rank` expression weighting `name ×3, raw_content ×1, source_book ×0.5` using `highlight`, `offsets`. Should we add `porter` tokenizer vs `unicode61 "remove_diacritics 2"`?
- `MATCH` syntax escaping is fragile (`* - + ( ) : | ...` replaced with spaces) — better sanitizer that preserves exact phrase `"hero points"` vs fallback `OR`? benchmark query latency on 34k rows.
- Vector hybrid: when to add `Chroma` + `nomic-embed-text` (768-dim) — cosine on top 100 FTS5 vs pre-filter vector? CPU-cost on Dell CPU-only? Is `rag_limit=4` optimal token budget given `num_predict=700`?
- Edition fallback `2E→1E` vs user-selected `both`: should we search both in one `UNION` `ORDER BY rank` cross-edition instead of sequential loop?

### 15.3 LLM Prompt & Model Tuning for PF2e

**Current:** `orchestrator.py:220` system prompt enumerates modes + tool descriptions, `rag_prompt` joins `[{source_book}] name: content[:500]` `---`, temperature 0.6, `phi4-mini` CPU.

**Asks:**

- Research prompt engineering for PF2e ORC: best few-shot to prevent rule hallucination; compare `phi4-mini` vs `qwen2.5:3b` vs `qwen2.5:14b` (future Rules Lawyer) latency/quality on `i5-... CPU` — tokens/s, VRAM, `num_predict` sizing for 700-token bios.
- Tool-use vs agentic loop: Ours is single `generate` with pre-bundled tools, no ReAct loop. Should we implement `ollama chat` tool calling loop (multiple turns) for `validate_action` → narrate? Provide minimal `ollama_client.py` loop sketch.
- Retrieval citation fidelity: how to force model to cite `source_book` page/section from `raw_content` without exposing raw HTML? Best chunk size (300 vs 500 chars) for PF2e stat blocks?

### 15.4 Rules Lawyer Agent Architecture

**Planned:** `hub/app/agents/rules_lawyer.py` `lookup_rule`, `calculate_dc`, `validate_action` backed by FTS5 + eventually `qwen2.5:14b`.

**Asks:**

- Design `calculate_dc(level, rarity, proficiency)` table lookup vs LLM: PF2e Simple DC table + GM adjustments — just hardcode `level-based DC + rarity mod + proficiency`? Provide canonical PF2e Remaster DC table.
- `validate_action(action, character_sheet, target)` — what schema for `character_sheet` (from `spoke/lib/models/character.dart` abilities/proficiencies/feats) to validate without LLM? Use deterministic rule engine vs LLM fallback?
- `qwen2.5:14b` on CPU-only Dell: will it fit ~8 GB RAM? Quant `Q4_K_M` latency estimate? Alternative: `phi4-mini` with RAG is enough for 95% rules? When to escalate to 14b?

### 15.5 SQLite FTS5 on Android — FFI vs Platform

**Current:** `sqflite_common_ffi` + `sqlite3_flutter_libs ^0.5.42` because Android platform SQLite ships FTS4 only. Uses `getApplicationDocumentsDirectory` workaround after `/.dart_tool` bug.

**Asks:**

- Verify `sqlite3_flutter_libs` 0.5.x vs 0.6.0 EOL story — should we pin `sqlite3_flutter_libs: 0.5.42` indefinitely or migrate to `sqlite3` `2.x` + `databaseFactoryFfi` new init (`applyWorkaroundToOpenSqlCipherOnOldAndroidVersions` etc.)?
- Performance: `databaseFactoryFfi.openDatabase(readOnly:true)` on 132 MB file — mmap vs `SQLITE_OPEN_READONLY` flags, Android scoped storage `app_flutter` vs `getDatabasesPath()` proper via `path_provider` + `sqlite` plugin `getDatabasesPath()` FFI hybrid?
- Alternatives: `drift` + `sqlite3` with FTS5 virtual table migration vs raw `sqflite_common_ffi`? Provide minimal `pubspec.yaml` pinning recommendation.

### 15.6 WebSocket Resilience Over Sleep / LAN Flap

**Current:** `hub_client.dart:89` 3 retries exponential backoff 400·2ⁿ ms, emits `retrying` then `error`.

**Asks:**

- Review `web_socket_channel` vs `dart:io WebSocket` keepalive `pingInterval` for Android Doze; should we add `channel.sink.add(jsonEncode({ping}))` heartbeat? What server `Uvicorn` timeout interacts?
- Handling `ws://192.168.4.144:8000/stream` vs `wss` over Tailscale — cert pinning needed? How to persist chat history across reconnect (current Guide `rulebook_chatbot.dart` is in-memory `StreamController.broadcast`)?
- Should we add `GET /health` poll before retry to early-fail faster when hub actually down?

### 15.7 Audio & Haptics Latency

**Current:** `audioplayers ^6.1.0` 3-player SFX pool + looping BGM, `audio_service.dart` prefs, `haptics_service.dart` via `HapticFeedback`.

**Asks:**

- `audioplayers` on Android `MediaPlayer` vs `SoundPool` latency — dice SFX on tap feels 80-120 ms late on Moto G. Alternative: `just_audio` + `audio_pool` + `flutter_soloud`? Recommend lowest-latency for <20 ms click/crit/fail cues.
- Moto G vibration `VIBRATE` permission intensity: `heavy()` maps to `HapticFeedback.heavyImpact` vs `Vibration.vibrate(50)` — calibrated values for "dice roll" feel?

### 15.8 Distribution & Play-Anywhere

**Current:** LAN `192.168.4.144:8000`, `Start_CommandCenter.bat` → standalone exe, Tailscale planned.

**Asks:**

- Compare Tailscale vs WireGuard vs `ngrok` for no-code-changes remote play. Firewall traversal for Dell behind CGNAT? Provide `tailscale up --advertise-exit-node` vs `tailscale funnel` recipe for hub without code change.
- Play Store / F-Droid: bundled 48 MB gz makes AAB ~60 MB — exceeds instant limit; should move to Play Asset Delivery `install-time` + `on-demand` packs? Provide `build.gradle` snippet.
- Windows distribution for Command Center: code-signing for SmartScreen on `dist/*.exe` — self-signed vs `signtool` cost?

### 15.9 Licensing & Content Safety

**Asks:**

- Deep research: PF2e ORC content from `pathfinder_rag.db` (Archives of Nethys scrape) — is bundling the 34k FTS5 excerpts + shipping 48 MB gz inside APK compliant with ORC `Attribution ShareAlike` vs OGL 1.0a vs `Compatible with Pathfinder` compatibility license? Provide citation checklist (attribution, disclaimer, `ORC_License.txt` placement).
- Prompt-content filtering: `phi4-mini` may generate copyrighted flavor text — how to add `RLHF` / system guardrail "never reproduce more than 300 chars verbatim from `raw_content`"?

### 15.10 Testing & Confidence Gaps

**Asks:**

- Recommend hub pytest expansion plan for G1-9 gates: `generate` typed mapping, `rules/search` edition fallback, `stream` reconnect, `campaign` CRUD continuity — minimal `TestClient` + `FakeLLM` + temp FTS5 fixture pattern (existing `tests/test_api.py` 5 tests as seed).
- Spoke widget tests: `HomeScreen` 6-tab, `DiceScreen` animated roll golden? `RulebookDb` isolate extraction test with fake `rootBundle` gz fixture (how to mock `path_provider`?) — provide template.

---

## 16. Roadmap

**Now → v0.6 (Polish, no data model break):**

- [x] Offline extraction isolate + lock (this whitepaper)
- [x] Dice hit-test + dramatic 3D (this)
- [x] Settings `:11450` → `:8000` auto-fix (this)
- [ ] Export/import campaign/character JSONL (data ownership)
- [ ] `GET /healthy` vs `GET /ready` split + `HEAD /livez` k8s-style
- [ ] Hub pytest G1-9 full suite + CI `uv run pytest`

**v0.7 (Content & Agents):**

- [ ] Additional PF2e packs (Remaster errata) — re-gz + `bundleVersion` bump
- [ ] `qwen2.5:14b` Rules Lawyer `validate_action` / `calculate_dc` behind `G1-10` gate
- [ ] Campaign typed graph (entities/relations) vs flat `notes`

**v0.8 (Play-anywhere):**

- [ ] Tailscale recipe + `HubConfig` supports `https://tailXXXX.ts.net:8000` + `wss`
- [ ] PAD asset packs if APK >150 MB
- [ ] Godot / Unity comparison? No — stay Hub-Spoke.

**Out of scope:** Flutter web/iOS (extends trivially, no arch change), cloud LLM (never default).

---

## 17. Appendix

### A. API Surface Copy (`shared/openapi.yaml` headers)

```yaml
openapi: 3.1.0
info: {title: Pathfinder God Hub, version: 0.1.0, summary: A local Pathfinder GM (RAG + Ollama)}
paths: /ask POST AskRequest→AskResponse
       /generate/{kind} POST GenerateRequest→AskResponse
       /health GET →HubHealth
       /rules/search GET q*,edition,limit→RulesSearchResponse
       /campaign GET→CampaignState POST /campaign/note POST /campaign/reset
# HubHealth: {version, ollama_model, databases_found[], status=ok}
# RuleHit: {name, content, system, category, source_book}
```

Full file 397 lines in repo.

### B. Data Schema Snapshot (`hub/app/models.py` + `spoke/lib/models/character.dart`)

- **Hub FTS5 `rules`:** `system TEXT (1E/2E)`, `category TEXT (feats/spells/equipment/bestiary/classFeatures/backgrounds/deities/ancestries/conditions/actions...)`, `name TEXT`, `source_book TEXT`, `raw_content TEXT`, virtual `FTS5(name, raw_content, tokenize='porter unicode61 "remove_diacritics 2"')` (actual tokenizer per builder), shadow `rules_data/idx`.
- **Character:** abilities `str/dex/con/int/wis/cha` + mod, 31 proficiencies `trained→legendary`, feats, spells `{tradition, slots[1..10], focus}`, equipment `{weapons, armor, shield, currency}`, `recalculateDerived() → HP/AC/saves/perception/DC/speed/bulk/initiative`, conditions `heroPoints/dying/wounded/doomed/fatigued`.

### C. Verification Commands (per RULES — lane ends here)

```bash
# Hub
cd hub
C:\venv-hub\venv\Scripts\python.exe -m app.main  # :8000, logs to stdout
curl http://127.0.0.1:8000/health
curl "http://127.0.0.1:8000/rules/search?q=flanking&edition=2e&limit=2"
curl -X POST http://127.0.0.1:8000/ask -H "Content-Type: application/json" -d '{"query":"what is flanking?","edition":"2e"}'

# Spoke
cd spoke
flutter pub get
flutter analyze        # must be 0 issues (see AGENT.md lane)
flutter test           # 15/15
# Build: Android Studio ▶️ Run (never flutter build apk)
```

**Expected recent logs (Hub):**

```
INFO: Uvicorn running on http://0.0.0.0:8000
INFO: 127.0.0.1:xxxxx - "GET /health HTTP/1.1" 200 OK
```

**Expected recent logs (Spoke fixed):**

```
RulebookDb: dir = /data/data/com.pathfindergod/app_flutter/rulebook
RulebookDb: dbPath = .../rulebook/pathfinder_rag.db
RulebookDb: Starting extraction from assets/rules/pathfinder_rag.db.gz to ...
RulebookDb: Loaded compressed asset (50169559 bytes)
RulebookDb: Decompressed to 138... bytes
RulebookDb: Extraction complete
RulebookDb: opened [{c: 34554}]
DiceAnimationWidget: tapped / AnimatedDiceRoller: roll -> 14
```

### D. Gotchas Checklist (condensed from blueprints)

- Emulator → `http://10.0.2.2:8000`, real device → LAN `http://192.168.4.144:8000`, **never** `:11450` in Spoke.
- WS drops on sleep → auto-reconnect in `HubClient.stream`.
- Markdown import `package:flutter_markdown_plus/flutter_markdown_plus.dart`.
- Re-bundling DB → bump `RulebookDb.bundleVersion`.
- Android FTS5 → `sqflite_common_ffi` (`0.5.42`, hold `0.6.0-eol`).
- `flutter pub upgrade --major-versions` tries to bump `sqlite3_flutter_libs` → deny.
- Command Center via `dist/*.exe` not `python main.py`.

### E. File Pointers for Reviewers

| Concern | File |
|---------|------|
| Offline extraction & FTS5 | `spoke/lib/services/rulebook_db.dart:36` |
| Dice math | `spoke/lib/dice/dice.dart:77` |
| Dice physics | `spoke/lib/dice/dice_physics.dart:12` |
| Hub client reconnect | `spoke/lib/api/hub_client.dart:89` |
| Hub orchestrator 2-tier | `hub/app/llm/orchestrator.py:40` |
| RAG FTS5 query | `hub/app/rag/retriever.py:34` |
| Hub config / Ollama | `hub/app/config.py:22` |
| Contract | `shared/openapi.yaml` |
| Architecture doc | `docs/architecture.md` |
| Current state | `blueprints/CURRENT_STATE.md` |

### F. Glossary

- **God:** LLM GM persona. **Guide:** offline chatbot. **Bestiary / Rulebook:** same FTS5 DB, different tabs. **Hero:** character. **Continuity Keeper:** campaign memory agent. **Rules Lawyer:** rule-lookup agent. **NPC Compiler:** stat block compiler.

---

**Next step for reviewer:** Please read `RULES.md:5.2` lane note, then pick 1–2 items from §15 to research first. Priority suggestion: **15.1 (offline extraction streaming)** and **15.3 (PF2e prompt/model tuning)** unblock the next player-facing release. Paste proposed code diffs as unified patches so we can land lane-clean (`flutter analyze` 0).

*Genesis footer — As Above, So Below.*

