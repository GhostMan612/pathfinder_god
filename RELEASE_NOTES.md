# Pathfinder God — Release Notes

## v0.6.4 "Self-Improving Library + Offline Brain" — 2026-09-14

### Highlights
- **Ask → scraped → permanent**: empty rulebook searches offer "Fetch from the web"
  (`POST /rules/fetch` scrapes the exact 1e term live via the polite fleet and stores
  it); misses queue offline and drain to the hub (`POST /rules/missed` →
  `data/misses.jsonl`) for chunked backfill. Every miss makes the DB better.
- **On-device SLM Guide** (opt-in): Gemma 3n via MediaPipe answers from offline
  excerpts with zero network. One-time ~2GB model download in
  **Setup → Offline brain** (HuggingFace token needed, gated repo) or side-load
  `guide_model.task`. Scripted excerpts remain the fallback.
- **Polite fleet**: rotating user-agents, probed limits (0.5s interval, ≤4 rps —
  measured, no throttling seen), Retry-After backoff, checkpoints + chunked
  `--offset/--limit/--resume` runs across all three scrapers.

### Spoke
- `MissQueue`, `SlmGuideService`, Guide-chat SLM tier, `HubClient.fetchRule`.
- `flutter analyze`: clean · `flutter test`: 25/25.

---

## v0.6.3 "Real Audio + Fuller Library" — 2026-09-14

### Highlights
- **Royalty-free audio**: real tavern/inn ambient loops (CC0 + CC-BY) replace the
  synth BGM, with a track picker in Settings; real dice/coin/UI SFX replace the
  synth blips. Full credits in-app (**Setup → Audio credits**) and
  `docs/audio-credits.md`. Command Center dice/Guide replies play sounds too.
- **44,620 rules** (was 43,884): +736/+110 from jrmiller82's OGL 2e YAML
  (spells, feats, monsters with `Core Rulebook p.X` citations); APG 1e confirmed
  in-tree (1,853 rows). Phone bundle re-generated (20MB, `bundleVersion` 2).

### Spoke
- `AudioService` track preference (`music_track`); `flutter analyze` clean,
  `flutter test` 21/21.

---

## v0.6.2 "Zero-Config" — 2026-09-14

### Highlights
- **Hub auto-discovery** — the laptop announces `_pathfindergod._tcp` over mDNS; the
  app's **Setup → Find hub automatically** lists reachable hubs, tap to connect. Falls
  back to laptop-hotspot gateway (`192.168.137.1:8000`), emulator (`10.0.2.2:8000`),
  and last-known URL. No IP typing, no SSH involved.
- **One Rules tab** — the duplicate Rules/Bestiary tabs are merged; `RulebookScreen`
  (search + browse chips + Guide) owns Rules. App is 5 tabs now.
- Commit author is GhostMan612; the 20MB offline-rulebook asset moved to Git LFS
  (`git lfs install` before cloning).

### Hub
- mDNS advertisement on startup (`hub/app/discovery.py`, `zeroconf` dep, silent
  no-op if missing); TXT carries version + model.

### Spoke
- `HubDiscovery` service (`multicast_dns`) + parallel `/health` probing in Settings.
- `flutter analyze`: clean · `flutter test`: 21/21 (new discovery tests).

---

## v0.6.1 "Database Truth Pass" — 2026-09-14

### Highlights
- **43,884 rules** (was 34,554): 1e 9,899 → **22,131** from official Paizo PRD JSON;
  2e +127 sourced rows (backgrounds/conditions/skills, Player's Guides).
- **Exact-match ranking everywhere** (hub + phone): `flanking` → *Flanking · Core
  Rulebook*, `fireball` → *Fireball · Core Rulebook*. Known sources outrank
  `Unknown Source` (16,295 → 8,926).
- Categories canonicalized (92 messy → clean set; `Waterskin x36` 1e dupes collapsed);
  raw HTML stripped to plain text.
- Phone bundle 50MB → **20MB** (`bundleVersion` 2 forces re-extract).
- Reproducible builders: `hub/scripts/{build_rag,build_2e_rag,db_normalize}.py`,
  3 importers (PSRD-Parser data, Pf2ools, pfsqlite-YAML), 3 rate-limited scrapers
  (AoN 2e/1e, d20pfsrd). `rebuild_rags.py` validates, keeps `.bak`, swaps, vacuums.

---

## v0.6.0 "Deep Research" — 2026-08-30

- Native 8KB rulebook streaming on Android (Kotlin `AssetManager→GZIP`), isolate
  fallback, static open-lock — Moto G OOM/`Skipped 227 frames` fixed.
- ReAct agentic tool loop for `qwen2.5:3b`; deterministic Rules Lawyer
  (`LEVEL_DC`/`ACTION_SKILL`, never LLM); citation fidelity
  (`[Source Book - Rule Name]`, ≤3 sentences).
- WebSocket heartbeat (15s ping) + chat-history rehydration across reconnects.
- Export/import: characters + campaign as JSON/JSONL via system share sheet.

---

## v0.5.1 "Command Center Standalone" — 2026-08-29

- Standalone `PathfinderGodCommandCenter.exe` (~48MB, PyInstaller, no venv):
  Services, Models, Rules, Generators, Dice, Guide tabs; system tray + icon.
  Launch with `Start_CommandCenter.bat`.

---

## v0.5.0 "Full PF2e Character & Offline Spoke" — 2026-08-24

- **Spoke**: 9-tab PF2e character sheet with derived-stat recalc; dice engine
  (NdM±mod, kh/kl, Adv/Dis, degrees of success, fortune/misfortune, hero points);
  offline FTS5 rulebook bundled in APK; Guide chatbot with cited excerpts; 6
  synthesized sounds + looping tavern BGM; haptics; WebSocket auto-reconnect;
  `com.pathfindergod` identity + branded icons.
- **Hub**: `/health`, `/ask`, `/stream` (WS), `/rules/search`, `/generate/*`
  (7 kinds), `/campaign` CRUD; 2-tier fallback (Ollama → raw excerpts).
- Command Center (PySide6) first shipped; CI workflow; OpenAPI contract v0.1.0.

---

## Quick Start

### Laptop (Hub)
```bat
:: Option A (easiest): double-click Start_CommandCenter.bat
::   Services tab → Start Ollama → Start Hub
:: Option B (terminal):
cd C:\pathfinder_god\hub
C:\venv-hub\venv\Scripts\python.exe -m app.main   :: http://0.0.0.0:8000
```

### Phone (Spoke) — Android Studio
1. Open `spoke/`, press Run on your device.
2. **Setup → Find hub automatically** → tap your laptop → green card.

Manual fallback: hub URL is `http://<laptop-lan-ip>:8000`
(emulator: `http://10.0.2.2:8000`). Never use `:11450` — that's Ollama.

---

## Data Layer
| Asset | Location | Size | Notes |
|-------|----------|------|-------|
| `pathfinder_rag.db` | `data/` (laptop, git-ignored) | 58MB | 44,620 FTS5 rows (1E 22,131 + 2E 22,489) |
| `pathfinder_rag.db.gz` | `spoke/assets/rules/` (Git LFS) | 20MB | Bundled in APK, extracted on first launch |
| `campaign.db` | `data/` (git-ignored) | 114KB | Campaigns/sessions/NPCs/locations/quests |

Rebuild: `C:\venv-hub\venv\Scripts\python.exe hub/scripts/rebuild_rags.py`
(see [`docs/database.md`](docs/database.md)).

---

## Known Issues
1. **DB licensing** — commercial redistribution unverified (personal use fine).
2. 8,926 legacy rows still lack a source book (ranked last, shrinking per import).
3. Adventure-path prose (Product Identity) deliberately excluded — mechanics only.

---

## Credits
- **Rules data** — Paizo PRD text (OGL), Pf2ools (MIT/CUP), Community Use Policy sources.
- **LLM** — Ollama `phi4-mini` (default), `qwen2.5:3b`, `nomic-embed-text`.
- **Frameworks** — Flutter, FastAPI, PySide6, SQLite/FTS5.
- **Audio** — synthesized via `tools/gen_audio.py` (original, royalty-free).

---
*As Above, So Below. As Within, So Without. The Future Dictates the Past and the Past is Always Present.*
