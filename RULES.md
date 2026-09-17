# RULES.md — Pathfinder God Operating Law
> **CANONICAL RULESET.** Every session MUST read this file before doing any work.
> If any other document contradicts this file, THIS FILE WINS.

---

## 1. ABSOLUTE RULES (never violated, no exceptions)

### 1.1 External directories are READ-ONLY
Never create, modify, move, or delete ANYTHING under these paths:
```
C:\sovereign_tagger_bak
C:\Recovery for All
C:\Sovereign Nodes
C:\sovereign_mantle
C:\sovereign_tagger_2
```
- Reading and copying FROM them into `C:\pathfinder_god` is allowed.
- Approved Python environment: use `C:\venv-hub` AS-IS (`C:\venv-hub\venv\Scripts\python.exe`, Python 3.14.6) — never copy it into the project; installing packages INTO it is allowed.
- The ONLY writable work area is `C:\pathfinder_god` (plus user-approved tool homes: `C:\Doom Shit`, usage of `C:\android`, `C:\ZDaemon`, `%USERPROFILE%\.gradle` caches).
- When in doubt: copy out, edit inside.

### 1.2 Secrets and commercial data never enter the repo
- Never commit: `.env`, API keys, keystores (`*.keystore`, `debug.keystore`), `local.properties`.
- Commercial IWADs (DOOM2.WAD etc.) live ONLY outside the repo at `C:\Doom Shit\IWADs\`. Never copy them into `C:\pathfinder_god`.

### 1.3 Git discipline
- **Stage by explicit path only.** `git add -A` / `git add .` are FORBIDDEN — they pull in unrelated work.
- Commits happen as part of an approved session workflow; never force-push, rebase public history, or delete branches unless explicitly asked.
- `blueprints\` and `_archive\` are intentionally gitignored — do not "fix" this.

### 1.4 Synthetic data only
Never include real operator family names or personal data in committed source code, tests, or fixtures. Use synthetic placeholders (e.g., `SAMPLE ANCESTOR A`). Real genealogy JSON under `MantleBridge\` (events/graph/ledger/game_state.json) is **gitignored** — it exists on disk for the game to read, never in history.

### 1.5 Nothing outside the project without approval
Do not install software, modify system settings, or write to new locations outside `C:\pathfinder_god` / approved tool homes without asking the user first.

---

## 1A. CONTEXT & OUTPUT DISCIPLINE (from CLAUDE.md)

- Filter all terminal output; pipe for failures only (`Select-String "error|fail"`), never ingest passing noise.
- No massive file reads — probe large JSON/data files with short Python scripts instead.
- Targeted verification only during development; full pipeline runs reserved for staged-commit verification.
- Spawn subagents for deep exploration when available; return summaries, not raw dumps.
- Proactively compact context after each verified+committed phase.

---

## 2. PROJECT CONVENTIONS (The Sovereign Directives)

1. **Full code only** — no partial snippets, no TODO stubs.
2. **No comments in code** — except the Genesis header every `.dart`/`.py`/`.kt` file must carry:
   ```
   // ============================================================
   // As Above, So Below. As Within, So Without.
   // The Future Dictates the Past and the Past is Always Present.
   // ============================================================
   ```
   (Use `#` for Python files.)
3. **Deterministic tables are canon** for gameplay numbers (hub XP/DC/rune/adjustment tables, never LLM memory); lore/systems flavor follows `docs\WHITEPAPER_ARCHITECTURE_v1.md`.

---

## 3. TECHNICAL LAWS (learned the hard way — see CHECKPOINTS/gotchas G1–G20)

| Law | Rule |
|-----|------|
| Long builds | Launch DETACHED (no `-Wait`) and poll logs — tool timeouts kill child processes. `Start-Process` on `.bat` may throw a cosmetic harness error; poll logs, don't trust it. |
| Native builds | Build via user's env (`local.properties` → `C:\android\sdk`, cached Gradle dists, Temurin JDK 17 in temp). Android Studio's bundled JBR is stripped (no working `java.exe`) — never point `JAVA_HOME` at it. |
| API names | Verify API/artifact names against package sources, not memory (`io.requery:sqlite-android` does not exist on Central; the maintained fork is `mil.nga:sqlite-android`). |
| SQLite platform gap | Android's platform SQLite has no FTS5 — offline rules search must go through an FTS5-capable driver (Spoke: `sqlite3_flutter_libs`; native: NGA bindings), never the platform default. |

---

## 4. WORKFLOW LAW

### 4.1 Cold start (every session, in order)
1. Read `blueprints\SESSION_HANDOFF.md`
2. Read THIS file (`RULES.md`)
3. Read `blueprints\CURRENT_STATE.md` → `CHECKLIST.md`
4. Work from the relevant `blueprints\blueprint-sections\BP-*.md`

### 4.2 Session end (every session)
1. Update `blueprints\CHANGELOG.md` (top entry, dated)
2. Tick `blueprints\CHECKLIST.md`; flip gates in `blueprints\CHECKPOINTS.md`
3. Refresh `blueprints\CURRENT_STATE.md`; rewrite handoff "Where we are" + "Next actions"
4. Commit code with a descriptive message (never commit `blueprints\`)

### 4.3 Verification law
No checklist item is done until its checkpoint gate passes (see `blueprints\CHECKPOINTS.md`). Evidence before status flips. New work → define its gate first.

### 4.4 Scope law
Big dreams go into blueprint sections with phased plans first. Ship vertical slices; never let polish precede a passing play-test gate.

---

## 5. PROJECT-SPECIFIC LAWS (Pathfinder God)

### 5.1 Hub-Spoke Architecture
- **Hub** (`hub/`) — Python FastAPI + Ollama + RAG service. Runs on laptop. Heavy lifting (LLM + retrieval).
- **Spoke** (`spoke/`) — Flutter Android app. Thin client: dice, character sheet, chat, rules browser.
- **Contract** (`shared/openapi.yaml`) — Single source of truth for API. Both sides generate from this.

### 5.2 Data & Build Boundaries
- **500MB+ rules DBs** live in `data/` on laptop ONLY. Git-ignored. Never committed. Never in APK.
- **NEVER run full builds.** Do not execute `flutter build apk`, `flutter build appbundle`, `flutter run`, or any command that produces a compiled binary artifact. The human builds the app in Android Studio.
- **Lane ends at source correctness:** `flutter pub get`, `flutter analyze`, `flutter test` (host-side) are permitted. Anything that emits an APK/AAB/binary is out of scope.
- **Verification hand-off:** After scaffolding code, state what the human should expect when they press Run in Android Studio (e.g., "analyze clean, tests pass; first Gradle sync will download X"). If a build breaks on their side, debug from their pasted error output, never by rebuilding locally.
- Commit messages must not claim build success — only analyze/test status.

### 5.3 Python Hub Conventions
- FastAPI + `uvicorn` for serving.
- Local-only 2-tier LLM fallback, in order: local Ollama → raw FTS5 excerpts (always works, no LLM). No cloud tiers — no API keys leave the laptop.
- SQLite for campaign state; SQLite FTS5 (`data/pathfinder_rag.db`) for rules RAG. No vector store — do not add Chroma/Qdrant without a blueprint gate.
- All hub code under `hub/` — keep it separate from the spokes.
- New endpoints must not be shadowed by earlier-registered routes (FastAPI matches in order — see the `/generate/loot` vs `/{kind}` outage).

### 5.4 Flutter Spoke Conventions
- State via Provider + ChangeNotifier (`CombatStore` injected at the root); screens organized `lib/api/`, `lib/screens/`, `lib/storage/`, `lib/theme/`, `lib/config/`, `lib/models/`.
- Riverpod/Provider-free: manual DI via constructors (see `main.dart`).
- WebSocket streaming for live GM chat (`/stream` endpoint).
- Theme: `PathfinderTheme` (gold/crimson/parchment palette).

### 5.5 API Versioning
- `shared/openapi.yaml` is the contract. Regenerate Dart models via `openapi-generator` if schema changes.
- Backward-compatible additions only. Breaking changes = new versioned endpoint.

---

(End of file)