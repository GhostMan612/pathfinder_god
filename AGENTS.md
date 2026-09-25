<!-- As Above, So Below. As Within, So Without. The Future Dictates the Past and the Past is Always Present. -->
# AGENTS.md — Pathfinder God

## Project Structure
```
C:\pathfinder_god\
├── hub/                 # Python FastAPI service (WORKING: /health /ask /stream /rules/search /generate)
├── spoke_kt/            # Native Kotlin app, 9 tabs (see Native Lane)
├── shared/openapi.yaml  # API contract (source of truth)
├── data/                # SQLite DBs (pathfinder_rag.db 58MB / 44,620 rows, gitignored, laptop only)
├── docs/                # Setup + architecture guides
├── blueprints/          # Session docs + phased blueprints
├── tools/               # gen_audio.py (sound synth), command_center/ (PySide6 standalone exe)
└── assets/              # Images, audio
```

## Key Commands

### Hub (Python) — working
```bash
cd hub
python -m app.main        # starts on :8000 (uses C:\venv-hub)
```

### Spoke (Kotlin) — the client
```powershell
cd spoke_kt
$env:JAVA_HOME='C:\Users\612co\AppData\Local\Temp\opencode\jdk17\jdk-17.0.20.1+1'
.\gradlew.bat assembleDebug --no-daemon   # required before commit; daemons get reaped in this shell
# Human runs Install/Run in Android Studio. Never commit APKs.
```

### Environment
- Python: `C:\venv-hub\venv\Scripts\python.exe` (3.14.6) — use as-is
- Ollama: `ollama serve` on `0.0.0.0:11434` (hub `.env` maps `127.0.0.1:11450`, model `phi4-mini`)
- Android SDK: `C:\android\sdk` (Gradle 9.3.1 cached)
- Native JDK: Temurin 17 at `C:\Users\612co\AppData\Local\Temp\opencode\jdk17\jdk-17.0.20.1+1` (`$env:JAVA_HOME` per command) — Studio's bundled JBR is stripped, never use it
- Native agents: `.opencode/agent/native-dev.md` owns `spoke_kt/` (AGP 9.0.1 + KSP + Room 2.7, compileSdk 34)

## Critical Rules (from RULES.md)

1. **Native lane ends at `assembleDebug`** — green debug compile required before commit. No release builds, no committed APKs. Human runs in Android Studio.
2. **Hub lane ends at `pytest`** — `pytest hub/tests/` green before commit.
3. **READ-ONLY external dirs** — never touch: `C:\sovereign_tagger_bak`, `C:\Recovery for All`, `C:\Sovereign Nodes`, `C:\sovereign_mantle`, `C:\sovereign_tagger_2`
4. **Git: explicit paths only** — `git add <path>`, never `git add .` / `-A`
5. **Synthetic data only** — no real names in code/tests
6. **Every .py/.kt file needs Genesis header**:
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
- **Hub-Spoke**: Hub (laptop) does LLM + RAG + 500MB rules DB. Spoke (phone) is the 9-tab native client: dice, roster, ladder, vaults, journal, oracle.
- **API Contract**: `shared/openapi.yaml` v0.1.0 — both sides build against this.
- **Local-Only Fallback**: Ollama (local) → Raw FTS5 excerpts (always works). No cloud tiers.
- **Rules DB**: FTS5 in `data/pathfinder_rag.db` (gitignored). Rebuild via `hub/scripts/rebuild_rags.py`; the device extract ships at `spoke_kt/app/src/main/assets/rules/pathfinder_rag.db` (Git LFS — raw `.db`, AGP decompresses `.gz` assets at build time so gzip must not be used)

## Native Lane (`spoke_kt/`)
- **Separation**: every micro-agent (GM, encounter, loot, continuity, maps) runs on the Python Hub. Kotlin is strictly state-management (`ViewModel`/`StateFlow`) + rendering (Compose) — no LLM, no rules logic on-device beyond the bundled FTS5 read path.
- **Contract is law**: `shared/openapi.yaml` (26 paths) — Retrofit endpoints and WS frames must match it byte-for-byte. Emulator → `http://10.0.2.2:8000`; real device → laptop LAN IP.
- **Local-only**: Hub LLM is Ollama (`127.0.0.1:11450`) → raw FTS5 excerpts. No cloud tiers, no API keys anywhere in the lane.
- **Owner**: `.opencode/agent/native-dev.md` (AGP 9.0.1 + KSP 2.3.4 + Room 2.7.0, NGA sqlite-android for FTS5, compile/target 34, min 26).
- **Terminal UI**: pure 2D Jetpack Compose. No Unity/Godot, no native render surface — game-feel comes from Compose canvas animation + SoundPool audio, not an engine.

## Current State
- **Spoke**: 9-tab native app (Dice, God/loot, Hero, Rules, Combat, Encounter, Map, Campaign, Setup); `assembleDebug` green
- **Offline Spoke**: rulebook asset bundled (19MB gz → FTS5 extract on first launch), dice engine + haptics/SFX, Room vaults — works with laptop off
- **Hub**: Working service on :8000 (Ollama `phi4-mini`, FTS5 rules); `pytest hub/tests/` 107/107 green (hermetic harness)
- **Native spoke_kt**: the client — Room 2.7/KSP + NGA FTS5 + Retrofit + Compose BOM 2024.10.01; FileProvider export; vault→tracker bridge
- **Android identity**: `com.pathfindergod`, label "Pathfinder God", circular branded icons
- **Command Center**: **Standalone exe** at `tools/command_center/dist/PathfinderGodCommandCenter.exe` (~48MB) — launches via `Start_CommandCenter.bat`, no venv required

## Verification Gates
- `assembleDebug` green before any native commit
- `pytest hub/tests/` green before any hub commit
- Hub gates in `blueprints/CHECKPOINTS.md` (G1-1 through G1-10 for Phase 1)

## Dependencies (spoke_kt)
- Compose BOM 2024.10.01 (ui, material3, icons-extended, animation), activity-compose, lifecycle-viewmodel-compose
- Room 2.7.0 (KSP 2.3.4) + `mil.nga:sqlite-android:3450200` (Android SQLite lacks FTS5 — never the platform driver)
- Retrofit 2.11/OkHttp 4.12 + kotlinx-serialization converter
- Audio is framework `SoundPool` + `MediaPlayer` (no Oboe dependency; AGDK artifacts removed — nothing referenced them)

## Gotchas
- Android emulator → hub at `http://10.0.2.2:8000` (not localhost)
- Real device → hub at laptop's LAN IP (e.g., `http://192.168.4.144:8000`)
- WebSocket drops on sleep → SOLVED: backoff reconnect lives in `HubForegroundService`
- Re-bundling the rules DB → bump `DatabaseAssetManager.BUNDLE_VERSION` or devices keep the stale extract
- Android SQLite has no FTS5 → always query via the NGA bridge (`NgaSQLiteOpenHelperFactory`)
- `./gradlew` daemons get reaped in this shell → always `--no-daemon` with a capped heap
- `io.requery:sqlite-android` does not exist on Central — the fork is `mil.nga:sqlite-android`, do not "fix" it
- **Command Center**: Use the standalone exe at `tools/command_center/dist/PathfinderGodCommandCenter.exe` (no venv needed). `Start_CommandCenter.bat` updated.