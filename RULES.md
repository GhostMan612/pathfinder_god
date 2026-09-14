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
2. **No comments in code** — except the Genesis header every `.dart`/`.py` file must carry:
   ```
   // ============================================================
   // As Above, So Below. As Within, So Without.
   // The Future Dictates the Past and the Past is Always Present.
   // ============================================================
   ```
3. **Design bible is canon** for gameplay numbers (`docs\game-design-bible.txt`); whitepaper is canon for lore/systems flavor (`docs\white-paper-3.1.0-extracted.txt`).
4. Scene names are string-coupled: `GameBootstrap.firstLevelScene` ↔ `CorruptedWard.unity`. Renames require touching both + EditorBuildSettings.

---

## 3. TECHNICAL LAWS (learned the hard way — see CHECKPOINTS/gotchas G1–G20)

| Law | Rule |
|-----|------|
| Batchmode generation | ALWAYS use the delayCall pattern (`*Headless` entries): NO `-quit` flag, `EditorApplication.delayCall` + `AssetDatabase.Refresh()`, self `Exit(0)`. Otherwise prefabs save broken `m_Script:{fileID:0}` refs. |
| Art pass ordering | ANY `SceneBuilder.BuildAllHeadless` run resets materials → rerun `ArtPassBuilder.ArtPassHeadless` BEFORE building APK/exe. |
| Input handling | `activeInputHandler` stays `2` (Both). Never -1. New input code goes through `SNInput`, never raw `Input.` in gameplay scripts. |
| Long builds | Launch DETACHED (no `-Wait`) and poll logs — tool timeouts kill child processes. `Start-Process` on `.bat` may throw a cosmetic harness error; poll logs, don't trust it. |
| Cross-enemy AI | Use `BaseEnemy.AlertChase()`; `TransitionTo` is protected. |
| NavMesh | Namespace is `Unity.AI.Navigation` (not UnityEngine.AI) for `NavMeshSurface`. |
| Random | In files with `using System`, qualify `UnityEngine.Random`. |
| BuildTarget | Windows target enum = `BuildTarget.StandaloneWindows64`. Verify API names against package sources, not memory. |
| CompanionApp | Generated BuildConfig ns = `com.wastelandscrolls`; palette lives in `ui/theme/Color.kt`; build via user's env (`local.properties` → `C:\android\sdk`, cached Gradle 9.3.1). |
| Starter WAD | Ships NODES-less; ZDaemon auto-builds, else resave from UDB once. |

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
- Ollama client for local LLM calls (fully local, no cloud fallback).
- SQLite for campaign state; Chroma/Qdrant for vector RAG.
- All hub code under `hub/` — keep it separate from Flutter.

### 5.4 Flutter Spoke Conventions
- Clean Architecture: `lib/api/`, `lib/screens/`, `lib/storage/`, `lib/theme/`, `lib/config/`, `lib/models/`.
- Riverpod/Provider-free: manual DI via constructors (see `main.dart`).
- WebSocket streaming for live GM chat (`/stream` endpoint).
- Theme: `PathfinderTheme` (gold/crimson/parchment palette).

### 5.5 API Versioning
- `shared/openapi.yaml` is the contract. Regenerate Dart models via `openapi-generator` if schema changes.
- Backward-compatible additions only. Breaking changes = new versioned endpoint.

---

(End of file)