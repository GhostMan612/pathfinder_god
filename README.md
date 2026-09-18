# Pathfinder God

A hub-and-spoke Pathfinder (1e/2e) table companion:

- **Hub** — a Python service on your Windows laptop. FastAPI + local LLM (Ollama) +
  RAG over **44,620** FTS5-indexed rules. Answers questions, generates characters/NPCs/
  encounters, keeps campaign memory. No cloud required.
- **Spoke** — a native Kotlin Android app (Jetpack Compose, 2D). Dice, roster, combat
  ladder, encounter/map vaults, campaign journal, and an offline FTS5 rulebook oracle.

```
┌────────────────────────────┐         Same Wi-Fi (or laptop hotspot)          ┌──────────────────┐
│  HUB  ·  laptop (Python)   │  ◀──────────  HTTP + WebSocket  ──────────▶     │  SPOKE · Android │
│  FastAPI + Ollama + RAG    │      same Wi-Fi (or laptop hotspot)             │  Native Kotlin   │
│  44,620 rules (local)      │                                                 │  dice · sheet    │
└────────────────────────────┘                                                 └──────────────────┘
```

Point the app at the hub once: **Setup → Tether**, enter the laptop's LAN address
(`http://192.168.x.x:8000`, emulator `http://10.0.2.2:8000`), CONNECT. Details in
[`docs/troubleshooting.md`](docs/troubleshooting.md).

## Spoke features (9 tabs, all native Compose)

| Tab | What | Needs the hub? |
|---|---|---|
| Dice | Notation engine (`2d6+3`, `kh`, advantage) + spring-physics canvas, haptics + SFX | No — fully offline |
| God | Loot bazaar: level/budget/theme commissions, rune-validated drops | Yes |
| Hero | Roster + sheet (AC/HP/abilities/proficiencies/feats), Room-backed, shareable | No — local |
| Rules | FTS5 oracle: live search + 1e/2e chips, expandable hits | No — on-device extract |
| Combat | Initiative ladder, conditions, vault summon, native end-turn decay | No — local |
| Encounter | Threat forge + monster vault, persisted rosters | Generation needs hub |
| Map | Vault gallery + pinch-zoom viewer, GM/player layers, PNG share | Generation needs hub |
| Campaign | Journal ledger + chronicler summaries of combat events | Summaries need hub |
| Setup | Tether (hub URL + live link status) | — |

Backup/restore (Settings): characters + campaign export as JSON/JSONL via the system
share sheet — no storage permissions needed.

## Quick start

### 1. Laptop (Hub)
```bat
:: Easiest: double-click Start_CommandCenter.bat, then Services → Start Ollama → Start Hub
:: Or classic:
cd C:\pathfinder_god\hub
C:\venv-hub\venv\Scripts\python.exe -m app.main   :: serves http://0.0.0.0:8000
```
Full guide (Ollama models, firewall, LAN IP): [`docs/setup-hub-windows.md`](docs/setup-hub-windows.md).

### 2. Phone (Spoke)
1. Open `spoke_kt/` in Android Studio, press Run on your device.
2. **Setup → Tether** → enter `http://<laptop-LAN-IP>:8000` → CONNECT → green CONNECTED.

Lane: `./gradlew assembleDebug` (Temurin 17, `--no-daemon`). Never commit APKs.
Retired Flutter notes: [`docs/setup-spoke-android.md`](docs/setup-spoke-android.md).

### 3. Command Center (Windows GM console, optional)
`Start_CommandCenter.bat` launches the standalone console: start/stop Ollama + Hub,
browse models, search rules, run generators, roll dice, chat with the God, watch logs.

## Layout

| Path | What |
|---|---|
| `hub/` | Python FastAPI service. See [`hub/README.md`](hub/README.md). |
| `spoke_kt/` | Native Kotlin app (`com.pathfindergod`, Compose 2D). Hub owns all agents; Kotlin owns ViewModels + rendering per `shared/openapi.yaml`. |
| `shared/openapi.yaml` | The API contract both sides build against (v0.1.0). |
| `data/` | Laptop-only `.db` files (git-ignored). Schema: [`data/SCHEMA.md`](data/SCHEMA.md). |
| `tools/` | Sound synth (`gen_audio.py`), Command Center source (PySide6). |
| `tools/command_center/dist/` | Standalone `.exe` (git-ignored, built via PyInstaller). |
| `docs/` | Guides: [`architecture`](docs/architecture.md) · [`database`](docs/database.md) · [`api`](docs/api.md) · [`troubleshooting`](docs/troubleshooting.md) · setup hub + retired spoke notes. |

## Data & licensing

- Rules DB: 44,620 rows built from open sources (Paizo PRD text via OGL, Pf2ools
  MIT/CUP JSON, Community Use scrapes). Build scripts + source registry live in
  `hub/scripts/`; the `.db` files themselves are git-ignored and reproducible.
  Details: [`docs/database.md`](docs/database.md).
- Personal use is fine. **Commercial redistribution rights for the bundled rules
  DB are unverified** — resolve before any public release. Adventure-path prose
  (Product Identity) is deliberately *not* scraped.

## Cloning

The native rulebook asset is stored with Git LFS — install it once
(`git lfs install`), otherwise you'll get a pointer file instead of the database:

```bash
git lfs install
git clone https://github.com/GhostMan612/pathfinder_god.git
```

## Status

Migration complete (Phase 22): the Flutter spoke is deleted; `spoke_kt/` is the client.
Terminal UI: pure 2D Jetpack Compose — no Unity/Godot, no native render surface.
Current: hub `pytest hub/tests/`: 107/107 · `assembleDebug`: BUILD SUCCESSFUL.
History: [`RELEASE_NOTES.md`](RELEASE_NOTES.md).

---
*As Above, So Below. As Within, So Without. The Future Dictates the Past and the Past is Always Present.*
