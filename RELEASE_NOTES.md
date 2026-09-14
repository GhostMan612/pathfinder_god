# Pathfinder God — Release Notes

## v0.5.1 "Command Center Standalone" — 2026-08-29

### Highlights
- **Standalone Command Center executable** — `tools/command_center/dist/PathfinderGodCommandCenter.exe` (~48MB). No Python venv required. Double-click to launch.
- **System tray integration** — Minimize to tray, right-click for Show/Quit, single-click to toggle window.
- **Window icon** — Branded Pathfinder God icon on taskbar and tray.
- **Static LAN IP documented** — Hub accessible at `http://192.168.4.144:8000` for real-device play.

---

## v0.5.0 "Full PF2e Character & Offline Spoke" — 2026-08-24

### Spoke (Flutter/Android) — Complete Offline Play
- **Full PF2e Character Sheet** (9 tabs): Basics, Abilities, Proficiencies (31), Feats, Spells, Equipment, Derived Stats, Conditions, Notes
- **Derived stats auto-recalc** — HP, AC, Saves, Perception, DCs, Speed, Bulk, Initiative from PF2e Remaster rules
- **Dice Engine** — NdM±mod, kh/kl, Adv/Dis, PF2e degrees of success (crit bands, nat-20/1 bump, fortune/misfortune, hero points) — 10 unit tests
- **Offline Rulebook** — 48MB gzipped FTS5 DB (34,554 entries) bundled in APK, extracted on first launch
- **Guide Chatbot** — Scripted intents + real offline FTS5 retrieval with cited excerpts (gold Chip pills)
- **Bestiary** — Local FTS5 tier 1, Hub fallback tier 2, offline badge
- **Audio** — 6 original synthesized sounds (dice, nat-20 fanfare, nat-1 fail, error, UI tap, 24s tavern loop)
- **Haptics** — Vibration on rolls with Settings toggle, persisted
- **WebSocket Auto-reconnect** — 3 retries with backoff, `retrying`/`error` frames
- **Android Identity** — `com.pathfindergod`, "Pathfinder God" label, circular branded launcher icons
- **Build Verified** — `flutter analyze` 0 errors, `flutter test` 15/15 pass, builds in Android Studio

### Hub (Python/FastAPI) — Working Service
- **Endpoints**: `/health`, `/ask`, `/stream` (WS), `/rules/search`, `/generate/{kind}` (7 kinds), `/campaign` CRUD
- **3-Tier Fallback**: DeepSeek (cloud) → Ollama `phi4-mini` (local) → Raw FTS5 excerpts (always works)
- **Generate Fixed** — Explicit `GenerateResponse` mapping (answer, backend, mode, edition, sources)
- **Citations Live** — `sources[]` on `/generate/*` + WS `end` frames → Spoke renders gold pills
- **Continuity Keeper** — JSON decode try/except fallbacks, log noise silenced
- **Export/Import** — `/campaign/export`, `/campaign/import`, `/campaign/backup` (JSON/JSONL)
- **Health Split** — `/health` (liveness) + `/ready` (readiness) + `/metrics` (Prometheus)
- **pytest** — 5/5 critical passing, 9/13 total (4 require running Ollama)

### Command Center (Windows/PySide6)
- **6 Tabs**: Services (Ollama/Hub control), Models (list/pull), Rules (FTS5 search), Generators (all 7 kinds), Dice (kh/kl/Adv/Dis parity), Guide (streaming chat with history)
- **Chat History Persists** — `tools/command_center/chat_history.json`
- **Managed Subprocesses** — Ollama + Hub start/stop windowless (`CREATE_NO_WINDOW`)
- **Health Polling** — Every 5s, shows model + DB status

### Infrastructure
- **Docker/Compose** — `docker-compose.yml` + multi-stage `Dockerfile`s + `.env.example`
- **CI/CD** — `.github/workflows/ci.yml` (Spoke analyze/test, Hub pytest, Docker build/push, deploy)
- **OpenAPI → Dart** — Manual mirror stable; automation at `spoke/generate_models.dart`

---

## Quick Start

### Laptop (Hub)
```bash
# 1. Start Ollama
ollama serve  # listens on 0.0.0.0:11434

# 2. Start Hub (uses C:\venv-hub)
cd C:\pathfinder_god\hub
python -m app.main  # serves on 0.0.0.0:8000
```

### Phone (Spoke) — Android Studio
1. Open `spoke/` in Android Studio
2. Run ▶️ 'app' on device/emulator
3. Settings → Hub URL → `http://192.168.4.144:8000` (real device) or `http://10.0.2.2:8000` (emulator)

### Command Center (Windows GM Console)
```bat
# Double-click or run:
Start_CommandCenter.bat
# Launches tools/command_center/dist/PathfinderGodCommandCenter.exe
# Services tab → Start Ollama → Start Hub
```

---

## Data Layer
| Asset | Location | Size | Notes |
|-------|----------|------|-------|
| `pathfinder_rag.db` | `data/` (laptop) | 132MB | 34,554 FTS5 rows (1E+2E) |
| `pathfinder_rag.db.gz` | `spoke/assets/rules/` | 48MB | Bundled in APK, extracted on first launch |
| `campaign.db` | `data/` | 114KB | 9 tables, campaigns/sessions/NPCs/locations/quests |

---

## Known Issues / Tech Debt
1. **DB licensing** — Commercial redistribution rights unverified (personal use fine)
2. **OpenAPI → Dart** — Manual mirror; automation script exists but not wired to CI
3. **Hub pytest** — 4/13 tests fail when Ollama not running (expected)
4. **No Spoke widget tests** — Only dice/character derived tests exist

---

## Next Phase (Post-MVP)
- Rules Lawyer Agent (`qwen2.5:14b` for `validate_action`, `calculate_dc`)
- NPC Compiler Agent (`create_npc(concept)` → legal ABC stat block)
- Foundry VTT JSON export
- Tailscale overlay for remote play
- Voice I/O (STT/TTS)
- Multiplayer sync (WebSocket broadcast)

---

## Credits
- **Rules Data** — Pathfinder 2e SRD (Paizo, OGL)
- **LLM** — Ollama `phi4-mini` (Microsoft), `nomic-embed-text`
- **Framework** — Flutter 3.24, FastAPI, PySide6, SQLite/FTS5
- **Audio** — Synthesized via `tools/gen_audio.py` (original, royalty-free)

---

*As Above, So Below. As Within, So Without. The Future Dictates the Past and the Past is Always Present.*