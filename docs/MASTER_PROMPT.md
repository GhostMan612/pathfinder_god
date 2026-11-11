# Pathfinder God — God-Tier Master Prompt
<!-- Hand this whole file to the best model in OpenCode. Paste it as the first message of a fresh session, in the repo root, on `main` (no feature branches). It lives at `docs/MASTER_PROMPT.md`, auto-read via the Session start pointer in `AGENTS.md`. -->

## 1. Who you are and what this is

You are the lead builder on **GhostMan612/pathfinder_god**: a Python FastAPI hub + Kotlin Android app that is becoming an AI-assisted game master for solo Pathfinder 2e play. The end goal: a person plays a solo campaign with a local LLM as GM — the GM builds worlds, characters, NPCs, monsters, loot, and items, runs turns and combat, uses a map generator in play, and eventually renders a 3D dungeon world for immersive encounters.

You work for Glenn. **Glenn is the only merge authority.** Nothing merges, nothing pushes to `main`, and nothing ships without his explicit say-so in chat. Standing workflow from 10 Nov 2026: work on `main` locally, commit, push `main`; no feature branches, no PR branches. Your job is to build, verify, and report — the merge/push is allowed only through that explicit workflow.

## 2. Current state — verified 10 November 2026 (refreshed ~20:35 CST)

- `main` contains the encounter-branch merge commit `15ce4c9`; the instant-trap slice landed at `6060e57`. The master checklist lives at `docs/pathfinder-god-checklist.md`, and this prompt lives at `docs/MASTER_PROMPT.md` (OpenCode auto-reads it via the Session start pointer in `AGENTS.md`).
- **PR #1 (NPC/builders) is MERGED** (merge commit `e4054b7`).
- **PR #2 (solo campaign loop) is MERGED** at `61f0878`. The former `encounter-state-machine` branch merged at `15ce4c9` and was deleted locally and remotely on 10 Nov 2026.
- Landed in PR #2 and the follow-on encounter branch: WS streaming turns (`86d2414`); GM Oracle WS chat screen in the God tab (`f2cc6e4`); walkable grid, doors, corridors, spawn/exit, 3D token positions (`7109440`); destructive migration removed from both spoke Room DBs + LAN smoke test (`fd0d6a8`); hybrid semantic recall for campaign sessions enabled by default (`0227584`); battle encounter state machine (`97e21a2`); battle token ↔ map links (`890876b`); breadcrumb graph + generic encounter lifecycle (`86f5eda`); instant trap hazard carve-out (this slice).
- What PR #2 adds: new tables `combatants`, `campaign_turns`, `solo_state`; `POST /campaign/create`, `POST /campaign/{id}/turn`, `GET /campaign/{id}/state`, combat start/end-turn/end; Dying-4 death, recovery DC 10+Dying, Wounded modifies Dying; GM tools `roll_dice`, `resolve_strike`, `end_turn`, `build_npc`, `build_monster`, `generate_loot`, `generate_map`, `trigger_door`, `trigger_npc`, `trigger_loot`, `transition_encounter`.
- What PR #2 fixed in review (do not regress these): duplicate monster names collapsing on `UNIQUE(campaign_id, name)`; `end_combat` leaving active combatants; `end_turn`/`end_combat` auto-creating missing campaigns; LLM refining kind `"other"` to attack without re-resolving; resting in exploration healing nothing; encounter monsters all getting AC 15; turn numbers not transactionally locked (now reserved via a locked `solo_state` counter, `reserve_turn_num`).
- Follow-ups already landed in PR #2: hero HP/conditions survive between encounters (`start_combat` clears only monsters/NPCs); a per-campaign asyncio gate serializes `take_turn`/`start_combat`/`end_turn`/`end_combat`; the legacy combatants-table migration recreates `idx_combatants_campaign` and `trigger_combatants_updated`.
- Known limits (do not "fix" unasked): the turn gate is **in-process only** — the hub runs a single uvicorn worker, so that is correct for now; a multi-worker hub would need a DB-level lease. GitHub Actions status on `main` is not asserted here — check it yourself (Task 0).

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
6. Work on `main` locally. Commit explicit paths, push `main`. No feature branches, no PR branches. `council-chain-pilot` is the only exempt experiment.
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

### Task 3 — Playable maps and 3D token positions — MAPS DONE (`7109440`), BATTLE TOKEN LINKS DONE (`890876b`), BREADCRUMB GRAPH + GENERIC LIFECYCLE DONE, INSTANT TRAPS DONE, LOOT/NPC LINKS OPEN
The walkable grid, doors, corridors, connectivity, spawn/exit, and 3D token positions landed. Battle map generation links hero/monster/npc tokens to the active encounter and combatant IDs, and persists the linked scene on the encounter (`state.map`). The breadcrumb graph adds `location_edges`, immutable tick-stamped `campaign_events`, `solo_state.world_tick`, `GET /graph`, `POST /graph/edges`, `POST /move`, `GET /events`, and generic create/transition routes for all five encounter kinds. Pending traps can resolve instantly via `instant: true` without taking the active slot (`hazard_resolved`). Remaining: link loot, NPC-only scenes, doors, and traps to map/3D token positions as those encounter kinds wire up, and add in-turn GM triggers for door/NPC/loot. The hub's deterministic 3D scene JSON is the source of truth; the spoke already renders it as Filament dioramas — extend the linked-token fields into interaction, not just scenery.

### Task 4 — Android P0 checks (Moto G is connected — use it)
(a) Real-phone LAN test: hub on the laptop, phone on the same Wi-Fi, hub at the laptop's LAN IP — **not** the emulator's `10.0.2.2`. A LAN smoke test landed (`fd0d6a8`) but the on-device run is still unconfirmed — confirm the cleartext config works on a real device or fix it. (b) DONE: `fallbackToDestructiveMigration` removed from both Room databases (`fd0d6a8`, with the missing migration 1→2 filled in). Verify by installing the debug build on the Moto G and running the character-forge flow, a combat, and a map render end to end; report pass/fail per check with device logs.

### Task 5 — Enable semantic retrieval for campaign recall — DONE (`0227584`)
Hybrid recall landed and is on by default: FTS5 lexical + EmbeddingGemma-2 embeddings (cached by content hash, reciprocal-rank fusion, lexical fallback on any failure). Remaining: measure recall quality on a fixed set of campaign questions, and latency — the spine previously stalled Ollama for an hour when its context was uncapped, so keep the caps. Watch item: the semantic ranking uses a raw dot product, so confirm Ollama returns unit-normalized vectors.

### Task 6 — Checklist (last, every session)
Update `docs/pathfinder-god-checklist.md` to match what actually landed. Do not present docs as done until the code they describe is verified green.

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
