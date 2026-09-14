# Pathfinder God

A hub-and-spoke Pathfinder (1e/2e) table companion:

- **Hub** — a Python service on your Windows laptop. FastAPI + local LLM (Ollama) +
  RAG over **43,884** FTS5-indexed rules. Answers questions, generates characters/NPCs/
  encounters, keeps campaign memory. No cloud required.
- **Spoke** — a Flutter Android app. Dice, character sheet, live God chat, and a full
  **offline rulebook** (the database ships inside the app — the laptop can stay off).

```
┌────────────────────────────┐         Same Wi-Fi (or laptop hotspot)          ┌──────────────────┐
│  HUB  ·  laptop (Python)   │  ◀──────────  HTTP + WebSocket  ──────────▶     │  SPOKE · Android │
│  FastAPI + Ollama + RAG    │      auto-discovery, no IP typing needed        │  Flutter app     │
│  43,884 rules (local)      │                                                 │  dice · sheet    │
└────────────────────────────┘                                                 └──────────────────┘
```

No typing IP addresses: the hub announces itself on the LAN and the app's
**Setup → Find hub automatically** connects with one tap. Details in
[`docs/troubleshooting.md`](docs/troubleshooting.md).

## Spoke features (5 tabs)

| Tab | What | Needs the hub? |
|---|---|---|
| Dice | PF2e engine (degrees of success, advantage, hero points) + animated 3D die, SFX + haptics | No — fully offline |
| God | Live GM chat, streaming markdown with source citations | Yes |
| Hero | Full PF2e character sheet (9 tabs), derived stats auto-recalc, local SQLite | No (except "Forge with the God") |
| Rules | Offline rulebook: search + browse chips + Guide chatbot, hub fallback | No — 43,884 entries on-device |
| Setup | Hub connection (auto-discover), sound/haptics toggles, backup/restore | — |

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
1. Open `spoke/` in Android Studio, press Run on your device.
2. **Setup → Find hub automatically** → tap your laptop → green "Connected to the God".

No Android Studio? See [`docs/setup-spoke-android.md`](docs/setup-spoke-android.md) for
`flutter` CLI notes. (Contributors: never commit APKs; the lane ends at
`flutter analyze` + `flutter test`.)

### 3. Command Center (Windows GM console, optional)
`Start_CommandCenter.bat` launches the standalone console: start/stop Ollama + Hub,
browse models, search rules, run generators, roll dice, chat with the God, watch logs.

## Layout

| Path | What |
|---|---|
| `hub/` | Python FastAPI service. See [`hub/README.md`](hub/README.md). |
| `spoke/` | Flutter Android app (`com.pathfindergod`). See [`spoke/README.md`](spoke/README.md). |
| `shared/openapi.yaml` | The API contract both sides build against (v0.1.0). |
| `data/` | Laptop-only `.db` files (git-ignored). Schema: [`data/SCHEMA.md`](data/SCHEMA.md). |
| `tools/` | Sound synth (`gen_audio.py`), Command Center source (PySide6). |
| `tools/command_center/dist/` | Standalone `.exe` (git-ignored, built via PyInstaller). |
| `docs/` | Guides: [`architecture`](docs/architecture.md) · [`database`](docs/database.md) · [`api`](docs/api.md) · [`troubleshooting`](docs/troubleshooting.md) · setup hub/spoke. |

## Data & licensing

- Rules DB: 43,884 rows built from open sources (Paizo PRD text via OGL, Pf2ools
  MIT/CUP JSON, Community Use scrapes). Build scripts + source registry live in
  `hub/scripts/`; the `.db` files themselves are git-ignored and reproducible.
  Details: [`docs/database.md`](docs/database.md).
- Personal use is fine. **Commercial redistribution rights for the bundled rules
  DB are unverified** — resolve before any public release. Adventure-path prose
  (Product Identity) is deliberately *not* scraped.

## Cloning

The offline rulebook asset is stored with Git LFS — install it once
(`git lfs install`), otherwise you'll get a pointer file instead of the database:

```bash
git lfs install
git clone https://github.com/GhostMan612/pathfinder_god.git
```

## Status

v0.6.2 — `flutter analyze`: clean · `flutter test`: 21/21 · hub `py_compile`: clean.
History: [`RELEASE_NOTES.md`](RELEASE_NOTES.md).

---
*As Above, So Below. As Within, So Without. The Future Dictates the Past and the Past is Always Present.*
