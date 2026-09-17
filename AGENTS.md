<!-- As Above, So Below. As Within, So Without. The Future Dictates the Past and the Past is Always Present. -->
# AGENTS.md — Pathfinder God

## Project Structure
```
C:\pathfinder_god\
├── hub/                 # Python FastAPI service (WORKING: /health /ask /stream /rules/search /generate)
├── spoke/               # Flutter Android app, 9 tabs (BUILDS IN ANDROID STUDIO)
├── spoke_kt/            # Native Kotlin spoke, pre-Glass scaffold (see Native Lane)
├── shared/openapi.yaml  # API contract (source of truth)
├── data/                # SQLite DBs (pathfinder_rag.db 58MB / 44,620 rows, gitignored, laptop only)
├── docs/                # Setup + architecture guides
├── blueprints/          # Session docs + phased blueprints
├── tools/               # gen_audio.py (sound synth), command_center/ (PySide6 standalone exe)
└── assets/              # Images, audio
```

## Key Commands

### Spoke (Flutter)
```bash
cd spoke
flutter pub get           # resolve deps
flutter analyze           # lint (must pass)
flutter test              # unit tests (host-side only)
# Build: Android Studio ▶️ Run (NEVER flutter build apk)
```

### Hub (Python) — working
```bash
cd hub
python -m app.main        # starts on :8000 (uses C:\venv-hub)
```

### Native (Kotlin) — pre-Glass scaffold
```powershell
cd spoke_kt
$env:JAVA_HOME='C:\Users\612co\AppData\Local\Temp\opencode\jdk17\jdk-17.0.20.1+1'
.\gradlew.bat assembleDebug --no-daemon   # always --no-daemon: daemons get reaped in this shell
```

### Environment
- Python: `C:\venv-hub\venv\Scripts\python.exe` (3.14.6) — use as-is
- Ollama: `ollama serve` on `0.0.0.0:11434` (hub `.env` maps `127.0.0.1:11450`, model `phi4-mini`)
- Android SDK: `C:\android\sdk` (Gradle 9.3.1 cached)
- Flutter SDK: `C:\android\flutter` (NOT on PATH — invoke `C:\android\flutter\bin\flutter.bat`; the `C:\src\flutter` PATH entry is dead)
- Native JDK: Temurin 17 at `C:\Users\612co\AppData\Local\Temp\opencode\jdk17\jdk-17.0.20.1+1` (`$env:JAVA_HOME` per command) — Studio's bundled JBR is stripped, never use it
- Native agents: `.opencode/agent/native-dev.md` owns `spoke_kt/` (AGP 9.0.1 + KSP + Room 2.7, compileSdk 34)

## Critical Rules (from RULES.md)

1. **NEVER run full builds** — no `flutter build apk/appbundle/run`. Human builds in Android Studio.
2. **Lane ends at source correctness** — `flutter analyze` + `flutter test` only.
3. **READ-ONLY external dirs** — never touch: `C:\sovereign_tagger_bak`, `C:\Recovery for All`, `C:\Sovereign Nodes`, `C:\sovereign_mantle`, `C:\sovereign_tagger_2`
4. **Git: explicit paths only** — `git add <path>`, never `git add .` / `-A`
5. **Synthetic data only** — no real names in code/tests
6. **Every .dart/.py file needs Genesis header**:
   ```dart
   // ============================================================
   // As Above, So Below. As Within, So Without.
   // The Future Dictates the Past and the Past is Always Present.
   // ============================================================
   ```

## Session Workflow
1. Read `blueprints/SESSION_HANDOFF.md` → `RULES.md` → `blueprints/CURRENT_STATE.md`
2. Work from relevant `blueprints/blueprint-sections/BP-*.md`
3. Session end: update `CHANGELOG.md`, tick `CHECKLIST.md`, flip `CHECKPOINTS.md` gates, refresh `CURRENT_STATE.md`, commit code (not blueprints)

## Architecture Notes
- **Hub-Spoke**: Hub (laptop) does LLM + RAG + 500MB rules DB. Spoke (phone) is thin client: dice, sheet, chat, rules browser.
- **API Contract**: `shared/openapi.yaml` v0.1.0 — both sides build against this.
- **Local-Only Fallback**: Ollama (local) → Raw FTS5 excerpts (always works). No cloud tiers.
- **Rules DB**: FTS5 in `data/pathfinder_rag.db` (gitignored). Rebuild via `hub/scripts/rebuild_rags.py`

## Native Lane (`spoke_kt/`)
- **Separation**: every micro-agent (GM, encounter, loot, continuity, maps) runs on the Python Hub. Kotlin is strictly state-management (`ViewModel`/`StateFlow`) + rendering (Compose) — no LLM, no rules logic on-device beyond the bundled FTS5 read path.
- **Contract is law**: `shared/openapi.yaml` (26 paths) — Retrofit endpoints and WS frames must match it byte-for-byte. Emulator → `http://10.0.2.2:8000`; real device → laptop LAN IP.
- **Local-only**: Hub LLM is Ollama (`127.0.0.1:11450`) → raw FTS5 excerpts. No cloud tiers, no API keys anywhere in the lane.
- **Owner**: `.opencode/agent/native-dev.md` (AGP 9.0.1 + KSP 2.3.4 + Room 2.7.0, NGA sqlite-android for FTS5, compile/target 34, min 26).
- **Terminal UI**: pure 2D Jetpack Compose. No Unity/Godot, no native render surface — game-feel comes from Compose canvas animation + Oboe audio, not an engine.

## Current State
- **Spoke**: 9-tab app, builds in Android Studio, `flutter analyze` 0 issues, `flutter test` 53/53
- **Offline Spoke**: bundled rulebook (48MB gz → FTS5), Guide chatbot w/ offline retrieval, dice + PF2e degrees of success, SFX + BGM — works with laptop off
- **Hub**: Working service on :8000 (Ollama `phi4-mini`, FTS5 rules); `pytest hub/tests/` 107/107 green (hermetic harness)
- **Native spoke_kt**: Gradle scaffold builds (`assembleDebug`); Room 2.7/KSP + FTS5 driver + Retrofit/AGDK deps; services and ViewModels unwired (pre-Glass)
- **Android identity**: `com.pathfindergod`, label "Pathfinder God", circular branded icons
- **Command Center**: **Standalone exe** at `tools/command_center/dist/PathfinderGodCommandCenter.exe` (~48MB) — launches via `Start_CommandCenter.bat`, no venv required

## Verification Gates
- `flutter analyze` must pass before commit
- Hub gates in `blueprints/CHECKPOINTS.md` (G1-1 through G1-10 for Phase 1)

## Dependencies (Spoke)
- `http`, `web_socket_channel`, `shared_preferences`, `flutter_markdown_plus` (migrated from discontinued `flutter_markdown`), `sqflite`, `path`
- Offline rulebook: `sqflite_common_ffi`, `sqlite3_flutter_libs` (Android SQLite lacks FTS5; stay on 0.5.x — 0.6.0 is EOL)
- Audio: `audioplayers`; Dev: `flutter_lints`, `flutter_test`, `flutter_launcher_icons`

## Gotchas
- Android emulator → hub at `http://10.0.2.2:8000` (not localhost)
- Real device → hub at laptop's LAN IP (e.g., `http://192.168.4.144:8000`)
- WebSocket drops on sleep → SOLVED: auto-reconnect lives in `HubClient.stream`
- Markdown import: `package:flutter_markdown_plus/flutter_markdown_plus.dart` (same `Markdown`/`MarkdownBody` API as the old package)
- Re-bundling the rules DB → bump `RulebookDb.bundleVersion` or devices keep the stale copy
- Android SQLite has no FTS5 → always query via `sqflite_common_ffi` (`RulebookDb`)
- `flutter pub upgrade --major-versions` will try to bump `sqlite3_flutter_libs` to 0.6.0+eol — keep it on ^0.5.42
- **Command Center**: Use the standalone exe at `tools/command_center/dist/PathfinderGodCommandCenter.exe` (no venv needed). `Start_CommandCenter.bat` updated.