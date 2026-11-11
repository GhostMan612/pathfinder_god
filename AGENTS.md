<!-- As Above, So Below. As Within, So Without. The Future Dictates the Past and the Past is Always Present. -->
# AGENTS.md — Pathfinder God

## Project Structure
```
C:\pathfinder_god\
├── hub/                 # Python FastAPI service (WORKING: /health /ask /stream /rules/search /generate)
├── spoke_kt/            # Native Kotlin app, 9 destinations (4 bottom tabs + navigation)
├── shared/openapi.yaml  # API contract (source of truth)
├── data/                # SQLite DBs (pathfinder_rag.db 58MB / 44,620 rows, gitignored, laptop only)
├── docs/                # Setup + architecture guides
├── blueprints/          # Session docs + phased blueprints
├── tools/               # Command Center + local-grunt tooling (PySide6/Python)
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
- Native JDK: Temurin 17 at `C:\Users\612co\AppData\Local\Temp\opencode\jdk17\jdk-17.0.20.1+1` (`$env:JAVA_HOME` per command) — the lane JDK, pinned via `kotlin.jvmToolchain(17)`. Studio's bundled JBR (`C:\android\Android Studio\jbr`) is a working OpenJDK 25, not a stripped/broken one, but it is deliberately not the lane JDK
- Native agents: `.opencode/agent/native-dev.md` owns `spoke_kt/` (AGP 9.0.1 + KSP + Room 2.7, compileSdk 37 / targetSdk 34)
- Local grunt: `local_grunt` ships as an OpenCode plugin (`.opencode/plugins/pf-local-grunt.ts`) plus a stdlib-only CLI/MCP pair (`tools/local_grunt.py`, `tools/local_grunt_mcp.py`) that delegates 1–8 explicit files to `pf-grunt:3b` on `127.0.0.1:11450` for read/propose/apply; start it with `tools/ollama/Ensure_Local_Grunt.ps1`, details in `docs/LOCAL_GRUNT.md`

## Critical Rules (from RULES.md)

1. **Native lane ends at `assembleDebug`** — green debug compile required before commit. No release builds, no committed APKs. Human runs in Android Studio.
2. **Hub lane ends at `pytest`** — `pytest hub/tests/` green before commit.
3. **READ-ONLY external dirs** — never touch: `C:\sovereign_tagger_bak`, `C:\Recovery for All`, `C:\Sovereign Nodes`, `C:\sovereign_mantle`, `C:\sovereign_tagger_2`
4. **Git: PR-first integration** — branch per change, explicit paths only (`git add <path>`), open/update the same PR until owner-authorized merge; no direct pushes to `main` (canonical: `RULES.md` §1.3; procedure: `docs/PR_WORKFLOW.md`).
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
- **Contract is law**: `shared/openapi.yaml` (verify live path count) — Retrofit endpoints and WS frames must match it byte-for-byte. Emulator → `http://10.0.2.2:8000`; real device → laptop LAN IP.
- **Local-only LLM**: Hub Ollama (`127.0.0.1:11450`) → raw FTS5 excerpts. No cloud model dependency.
- **Auth integration gap**: `HubApiFactory` and `HubWebSocketClient` currently do not attach `X-API-Key` or Bearer credentials, while many Hub campaign routes require `require_auth` when `PFGOD_API_KEY_SHA256` is configured. Do not claim the protected Android→Hub flow is integrated; design client credential storage, TLS and tests before enabling strict Hub authentication for a physical Spoke.
- **Owner**: `.opencode/agent/native-dev.md` (AGP 9.0.1 + KSP 2.3.4 + Room 2.7.0, NGA sqlite-android for FTS5, Filament 1.76, compile 37 / target 34, min 26).
- **Rendering**: Jetpack Compose for UI plus a real Filament 1.76 render surface for the 3D dice pit (`ui/pit/FilamentPit.kt`). No Unity/Godot. Game-feel comes from Compose canvas animation + SoundPool audio.

## Current State
- **Spoke**: 9 destinations (Dice, God/loot, Hero, Rules, Combat, Encounter, Map, Campaign, Setup) using a 4-item bottom bar, dashboard and More navigation; CI verifies `assembleDebug`.
- **Offline Spoke**: rulebook asset bundled (19MB gz → FTS5 extract on first launch), dice engine + haptics/SFX, Room vaults — works with laptop off
- **Hub**: FastAPI on configured host/port (default `:8000`), with Ollama + FTS5; see the current GitHub Actions `Hub - Tests` and `Hub - Lint` jobs for the live test count instead of relying on a historical 107-test snapshot.
- **Native spoke_kt**: the client — Room 2.7/KSP + NGA FTS5 + Retrofit + Compose BOM 2024.10.01; FileProvider export; vault→tracker bridge
- **Android identity**: applicationId/namespace `com.pathfindergod.spoke`, label "Pathfinder God", circular branded icons
- **Command Center**: **Standalone exe** at `tools/command_center/dist/PathfinderGodCommandCenter.exe` (~48MB) — launches via `Start_CommandCenter.bat`, no venv required

## Verification Gates
- `assembleDebug` green before any native commit
- `pytest hub/tests/` green before any hub commit
- Hub gates in `blueprints/CHECKPOINTS.md` (G1-1 through G1-10 for Phase 1)

## Dependencies (spoke_kt)
- Compose BOM 2024.10.01 (ui, material3, icons-extended, animation), activity-compose, lifecycle-viewmodel-compose
- Room 2.7.0 (KSP 2.3.4) + `mil.nga:sqlite-android:3450200` (Android SQLite lacks FTS5 — never the platform driver)
- Retrofit 2.11/OkHttp 4.12 + kotlinx-serialization converter; AGDK games-activity/frame-pacing
- Audio is framework `SoundPool` + `MediaPlayer` (no Oboe dependency)

## Gotchas
- Android emulator → hub at `http://10.0.2.2:8000` (not localhost)
- Real device debug build → hub at the current laptop LAN IP (`http://<laptop-LAN-IP>:8000`); a release build requires trusted HTTPS to a real phone
- WebSocket drops on sleep → SOLVED: backoff reconnect lives in `HubForegroundService`
- Re-bundling the rules DB → bump `DatabaseAssetManager.BUNDLE_VERSION` or devices keep the stale extract
- Android SQLite has no FTS5 → always query via the NGA bridge (`NgaSQLiteOpenHelperFactory`)
- `./gradlew` daemons get reaped in this shell → always `--no-daemon` with a capped heap
- `io.requery:sqlite-android` does not exist on Central — the fork is `mil.nga:sqlite-android`, do not "fix" it
- **Command Center**: Use the standalone exe at `tools/command_center/dist/PathfinderGodCommandCenter.exe` (no venv needed). `Start_CommandCenter.bat` updated.
## Session start (OpenCode / any agent)
- Before doing anything else, read `docs/MASTER_PROMPT.md` — it is the current mission brief: verified repo state, architecture facts, house rules, toolchain routing, and the prioritized task list.
- Then read `docs/pathfinder-god-checklist.md` — the living tracker of what is done, decided, and next.
- The repository owner is the only merge authority. Work on a scoped branch and keep its PR open through review/patch/CI; never push directly to `main`. `RULES.md` §1.3 overrides any older main-only instructions in `docs/MASTER_PROMPT.md` or dated `docs/FOR_MUSE.md` entries.
