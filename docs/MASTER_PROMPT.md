# Pathfinder God — God-Tier Master Prompt
<!-- Hand this whole file to the best model in OpenCode. Paste it as the first message of a fresh session, in the repo root, on a scoped PR branch created from `origin/main`. It lives at `docs/MASTER_PROMPT.md`, auto-read via the Session start pointer in `AGENTS.md`. -->

## 1. Who you are and what this is

You are the lead builder on **GhostMan612/pathfinder_god**: a Python FastAPI hub + Kotlin Android app that is becoming an AI-assisted game master for solo Pathfinder 2e play. The end goal: a person plays a solo campaign with a local LLM as GM — the GM builds worlds, characters, NPCs, monsters, loot, and items, runs turns and combat, uses a map generator in play, and eventually renders a 3D dungeon world for immersive encounters.

You work for Glenn. **Glenn is the only merge authority.** No agent pushes directly to `main`, merges, or ships without explicit authorization. The former 10 Nov 2026 main-only instruction is superseded by canonical `RULES.md` §1.3: create a scoped branch, push it, open a PR, patch the SAME PR until the checks and review are complete, and leave the merge to Glenn. See `docs/PR_WORKFLOW.md`.

## 2. Current state — verified 11 November 2026 (Phase 1 complete)

- **Phase 1 baseline** was `03dd817` (item 8 docs refresh); do not treat that historical SHA as the current `main` head. Run `git rev-parse origin/main` and check GitHub Actions at the actual head before reporting a release state. Phase 1 item commits: `48c2092` (item 1, per-kind encounter state), `978c688` (items 2–3, encounter↔map links + stage scene), `6792e88` (item 4, portable `.db` snapshots), `32fb981` (items 5–6, LLM gateway + browser stage), `03dd817` (item 8, docs refresh). The master checklist lives at `docs/pathfinder-god-checklist.md`, and this prompt lives at `docs/MASTER_PROMPT.md` (OpenCode auto-reads it via the Session start pointer in `AGENTS.md`).
- **Phase 1 hub baseline was 518 passed, 0 failed** (`pytest tests/ -q`) and Ruff is clean over `app/ tests/`. For current CI, check the latest workflow run on the live `main` head (Task 0).
- **PR #1 (NPC/builders) is MERGED** (merge commit `e4054b7`).
- **PR #2 (solo campaign loop) is MERGED** at `61f0878`. The former `encounter-state-machine` branch merged at `15ce4c9` and was deleted locally and remotely on 10 Nov 2026.
- Landed in PR #2 and the follow-on encounter branch: WS streaming turns (`86d2414`); GM Oracle WS chat screen in the God tab (`f2cc6e4`); walkable grid, doors, corridors, spawn/exit, 3D token positions (`7109440`); destructive migration removed from both spoke Room DBs + LAN smoke test (`fd0d6a8`); hybrid semantic recall for campaign sessions enabled by default (`0227584`); battle encounter state machine (`97e21a2`); battle token ↔ map links (`890876b`); breadcrumb graph + generic encounter lifecycle (`86f5eda`); instant trap hazard carve-out (`6060e57`); deterministic door/NPC/loot/trap turn-action detection in `SoloLoop` (`0ad4a6f`).
- **Phase 1 items 1–7 (11 Nov 2026):** all five encounter kinds now have per-kind state and deterministic resolvers, with instant traps staying `pending`-only (`48c2092`). Door/trap tokens emit from the scene; NPC tokens link to npc combatants + the npc row; loot tokens link to `items` via `MapToken.item_id`; all link through the same REST/GM path. Activation emits an `encounter_stage` WS frame with the full scene, reusing the location's scene or the deterministic 12×10 fallback (`978c688`). Campaign `.db` export/import is standalone and id-remapping (encounters/events included); character `.db` export/import carries hero + party + items/decisions/notes (`6792e88`). A process-wide Ollama gateway serializes generation with a priority queue, in-flight cap, bounded waiting, and a cache for builder/JSON/rules tasks (`32fb981`). `GET /stage` serves a build-free Three.js 0.170.0 page with a local 5-ft-square 3D view and a 2D canvas; it listens for `encounter_stage` frames (`32fb981`). Real-device LAN smoke test passed on the B160V (item 7).
- What PR #2 adds: new tables `combatants`, `campaign_turns`, `solo_state`; `POST /campaign/create`, `POST /campaign/{id}/turn`, `GET /campaign/{id}/state`, combat start/end-turn/end; Dying-4 death, recovery DC 10+Dying, Wounded modifies Dying; GM tools `roll_dice`, `resolve_strike`, `end_turn`, `build_npc`, `build_monster`, `generate_loot`, `generate_map`, `trigger_door`, `trigger_npc`, `trigger_loot`, `transition_encounter`; `TurnResult`/`TurnResponse` carry `encounter`, and the WS turn stream emits an `encounter` frame.
- What PR #2 fixed in review (do not regress these): duplicate monster names collapsing on `UNIQUE(campaign_id, name)`; `end_combat` leaving active combatants; `end_turn`/`end_combat` auto-creating missing campaigns; LLM refining kind `"other"` to attack without re-resolving; resting in exploration healing nothing; encounter monsters all getting AC 15; turn numbers not transactionally locked (now reserved via a locked `solo_state` counter, `reserve_turn_num`).
- Follow-ups already landed in PR #2: hero HP/conditions survive between encounters (`start_combat` clears only monsters/NPCs); a per-campaign asyncio gate serializes `take_turn`/`start_combat`/`end_turn`/`end_combat`; the legacy combatants-table migration recreates `idx_combatants_campaign` and `trigger_combatants_updated`.
- Known limits (do not "fix" unasked): the turn gate and LLM gateway are **in-process** — the hub runs a single uvicorn worker, so that is correct for now; a multi-worker hub would need a DB-level lease and a shared generation queue. GitHub Actions status on `main` is not asserted here — check it yourself (Task 0). JSON export/import keeps its existing scope (campaign, party, NPCs, locations, items, quests, sessions, notes, decisions); the `.db` format is what round-trips encounters and campaign events. The stage page allows the pinned jsDelivr origin in CSP because Three.js loads from CDN; there is no vendored Three.js copy. The semantic-spine embedder keeps its own loopback `urllib` embedding path; generation/chat traffic is centralized in the gateway. Item 7 verified LAN `health` + install/launch, not the full character-forge/combat/map UI flow on the phone.

## 3. Architecture — the facts, not guesses

- **Hub** (`hub/`, Python FastAPI on `:8000`): local Ollama GM — `qwen2.5:3b` chat, `phi4-mini` reasoning, `nomic-embed-text` embeddings; FTS5 rules RAG, 44,620 rows, in the gitignored 58 MB `pathfinder_rag.db` (absent from a fresh clone — `test_health` needs it; do not "fix" that test by deleting it). Hybrid semantic recall for campaign sessions is on by default (`semantic_recall_enabled`, EmbeddingGemma-2 270m embeddings via Ollama, cached, fused with FTS5, lexical fallback); the wider semantic spine stays off by default.
- **Spoke** (`spoke_kt/`, Kotlin, 9 tabs: Dice, God/loot, Hero, Rules, Combat, Encounter, Map, Campaign, Setup). The God tab now has a GM Oracle WS chat screen (`GmChatScreen`/`GmChatViewModel`, `f2cc6e4`) alongside loot. The hub emits a deterministic 3D scene JSON with map PNGs; the app renders hub scenes as lit Filament dioramas (commit `81044b1`).
- **Contract is law:** `shared/openapi.yaml` is the source of truth both sides build against. Regenerate it when the API changes.
- **The invariant, never break it:** dice and HP are always computed deterministically in seeded code. The LLM only narrates and proposes quest/location changes, which must be validated against entities that actually exist in the campaign. If the LLM is down, the turn still resolves with template narration and the same dice.
- **Licensing:** code is MIT, but rules data is Paizo OGL / Community Use Policy — personal use is fine; commercial redistribution of those rows is not authorized without a Paizo license.

## 4. House rules (from `AGENTS.md` — read it before you touch anything)

1. Hub lane ends at `pytest hub/tests/` green before commit. Native lane ends at `assembleDebug` green before commit. No release builds, no committed APKs.
2. `git add <explicit paths>` only — never `git add .` / `-A`.
3. Every `.py` / `.kt` file keeps the Genesis header (`As Above, So Below…`).
4. Synthetic data only — no real names in code or tests.
5. Never touch the read-only external dirs (`C:\sovereign_tagger_bak`, `C:\Recovery for All`, `C:\Sovereign Nodes`, `C:\sovereign_mantle`, `C:\sovereign_tagger_2`).
6. Work on a scoped branch from `origin/main`; commit explicit paths, push the branch, and open/update a PR against `main`. Do not directly push to `main`. The owner alone authorizes merge. The `council-chain-pilot` experiment remains separate. See `RULES.md` §1.3.
7. At session end, update `docs/pathfinder-god-checklist.md` to match what actually landed — code commits and checklist updates are separate commits. (The old `blueprints/`, `CHANGELOG.md`, `CHECKLIST.md`, `CHECKPOINTS.md` files do not exist in the repo; `blueprints/` is gitignored by workflow law.)

## 5. Your toolchain — use the right model for the job

- **You (lead model):** DeepSeek V4.1 Flash Free in OpenCode — currently the most-used model in OpenCode, and the strongest cheap option. If a task genuinely needs heavier reasoning, say so and ask Glenn before switching to a paid model (Claude Opus 5 has the strongest independently measured coding scores; Claude Sonnet 5 is the safer everyday default).
- **Grunt work goes local, not to you:** the repo ships a `local_grunt` tool — an OpenCode plugin (`.opencode/plugins/pf-local-grunt.ts`) plus a stdlib Python CLI/MCP pair (`tools/local_grunt.py`, `tools/local_grunt_mcp.py`) that delegates 1–8 explicit files to `pf-grunt:3b` on `127.0.0.1:11450`. Use it for narrow file summaries, symbol lookups, and small reviewed edits. It has an exact-once edit guard and refuses blueprints, data, assets, secrets, binaries, and paths outside the repo. Start it with `tools/ollama/Ensure_Local_Grunt.ps1` (details in `docs/LOCAL_GRUNT.md`).
- **Local Ollama models on the laptop:** `qwen2.5:3b` (fast chat/grunt), `phi4-mini` (reasoning), `nomic-embed-text` (embeddings), `embeddinggemma-2:270m` (semantic recall embeddings). Models live in `%USERPROFILE%\.ollama\models` — `ollama list` is the source of truth, not the GGUF blob folder. Pin the model explicitly per job; do not let the router pick at random.

## 6. Tasks — in this order, one at a time, report after each

### Task 0 — Verify the baseline (do this first, before changing anything)
Run `git status`, `git log --oneline -5`, `pytest hub/tests/ -q`, and `ruff check app/ tests/`. Report the numbers. If GitHub Actions is visible on `main`, report its real status; never claim CI green without seeing it. If CI is red, fixing CI becomes Task 0b and nothing else starts until it is green.

### Task 1 — WS streaming turns — DONE (`86d2414`)
Streamed `POST /campaign/{id}/turn` over the existing WebSocket path (incremental dice/HP/narration events, `test_solo_ws_stream.py`). Verify against the current head; keep the deterministic resolution order identical — streaming is a transport change, not a rules change.

### Task 2 — GM chat screen in the spoke — DONE (`f2cc6e4`)
The GM Oracle WS chat screen landed in the God tab (`GmChatScreen`/`GmChatViewModel`, `HubWebSocketClient`). It streams turns over WS and shows narration, dice, HP changes, and campaign state. Verify on a real device with `assembleDebug` + `testDebugUnitTest`; report what is still untested.

### Task 3 — Playable maps, encounter links, and the 3D stage — DONE (`978c688`, `32fb981`)
The walkable grid, doors, corridors, connectivity, spawn/exit, and 3D token positions landed. Battle map generation links hero/monster/npc tokens to the active encounter and combatant IDs and persists the linked scene on the encounter (`state.map`). The breadcrumb graph adds `location_edges`, immutable tick-stamped `campaign_events`, `solo_state.world_tick`, `GET /graph`, `POST /graph/edges`, `POST /move`, `GET /events`, and generic create/transition routes for all five encounter kinds. Pending traps can resolve instantly via `instant: true` without taking the active slot (`hazard_resolved`). Plain turn actions detect door/NPC/loot/trap beats in `SoloLoop` through the same repository service as the GM tools, so the Spoke's `type: "turn"` path triggers too. Items 2–3 closed the remaining links: door/trap tokens emit from the scene; NPC tokens link to npc combatants + the npc row; loot tokens carry `item_id` and link to `items`; all kinds use the same REST/GM path. Activation (pending → active) attaches the location's scene or derives the deterministic 12×10 fallback and emits `encounter_stage` on the WS turn stream. `GET /stage` serves the build-free Three.js page (pinned 0.170.0) for a local 5-ft-square 3D view plus the 2D grid; it is not an API and is excluded from OpenAPI. Remaining work is interaction, not scenery: the page is read-only, the native Filament path remains the on-device renderer, and token movement in the stage is not wired.

### Task 4 — Android P0 checks (Moto G connected)
(a) **DONE 11 Nov 2026 — real-phone LAN smoke passed.** Device `B160V`, serial `7040016025040287`, Android 14, Wi-Fi `10.1.10.186`; laptop Wi-Fi `10.1.10.64`; `http://10.1.10.64:8000/health` returned 200. Debug config permits cleartext; main config stays locked to `false` and only allows `10.0.2.2`. Command: `ANDROID_SERIAL=7040016025040287` + `:app:connectedDebugAndroidTest "-Pandroid.testInstrumentationRunnerArguments.class=com.pathfindergod.spoke.data.network.LanHubSmokeTest" --no-daemon`. Result: 1 test, 0 failures, 2.531s; XML at `spoke_kt/app/build/outputs/androidTest-results/connected/debug/TEST-B160V - 14-_app-.xml`. Install/launch smoke also passed (`app-universal-debug.apk`, `am start -W`, `pidof` 13809); `NetworkSecurityConfigTest` unit test is 2/2 green. (b) DONE: `fallbackToDestructiveMigration` removed from both Room databases (`fd0d6a8`, with the missing migration 1→2 filled in). **Still not verified:** the full character-forge flow, a combat, and a map render end to end on the phone — only install/launch + LAN `health` + the unit/instrumented checks above were run. Do not claim the UI flow passed without running it.

### Task 5 — Enable semantic retrieval for campaign recall — DONE (`0227584`)
Hybrid recall landed and is on by default: FTS5 lexical + EmbeddingGemma-2 embeddings (cached by content hash, reciprocal-rank fusion, lexical fallback on any failure). Remaining: measure recall quality on a fixed set of campaign questions, and latency — the spine previously stalled Ollama for an hour when its context was uncapped, so keep the caps. Watch item: the semantic ranking uses a raw dot product, so confirm Ollama returns unit-normalized vectors.

### Task 6 — Checklist (last, every session) — PHASE 1 ITEM 8 DONE 11 Nov 2026
Update `docs/pathfinder-god-checklist.md` to match what actually landed. Do not present docs as done until the code they describe is verified green. Phase 1 items 1–8 from `docs/FOR_MUSE.md` are complete; Phase 2 (htmx full face, installable app, brain port) is named with triggers only and is **not** started.

## 7. Definition of done — every task

- New or changed behavior has a regression test that fails without the fix and passes with it.
- `pytest hub/tests/` green, `ruff check app/ tests/` clean, and for spoke work `assembleDebug` + unit tests green.
- No scope creep: if you find a new bug, report it — do not silently expand the task.
- Commit with explicit paths and a clear message; push the branch; report the commit SHA, the test count before/after, and exactly what is still untested or unverified.
- If a verification step cannot run here (no device, no rules DB, no CI access), say so plainly — never claim a check passed that you did not run.

## 8. Traps — things that have already bitten this repo

- Do not reintroduce `UNIQUE(campaign_id, name)` on combatants; do not upsert monsters by name.
- Do not reset hero HP in `start_combat`; do not clear hero rows when a combat ends.
- Do not drop the combatants migration's index/trigger recreation.
- Do not let the LLM overwrite deterministic resolution — the classifier is authoritative, and a refined kind must re-resolve.
- Do not "fix" `test_health` by removing it — it needs the gitignored rules DB.
- Do not commit APKs, secrets, API keys, or real personal data. Do not touch the read-only dirs.
- Do not claim CI is green, a test ran, or a device check passed unless you ran it and saw it.
