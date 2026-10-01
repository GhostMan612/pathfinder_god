# Pathfinder God

A hub-and-spoke Pathfinder (1e/2e) table companion:

- **Hub** — a Python service on your Windows laptop. FastAPI + local LLM (Ollama) +
  RAG over **44,620** FTS5-indexed rules. Answers questions, generates characters/NPCs/
  encounters, keeps campaign memory. No cloud required.
- **Spoke** — a native Kotlin Android app (`com.pathfindergod.spoke`). Jetpack Compose
  everywhere, plus one Filament surface: the 3D dice pit. Dice, roster, combat ladder,
  encounter/map vaults, campaign journal, and an offline FTS5 rulebook oracle.

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

## Spoke features (9 destinations, 4-tab bar)

Navigation is a 4-item bottom bar — **Dice · Combat · Hero · Rules** — per Material 3's
3–5 item cap (`NavigationItem.kt:102-106`), on a real `NavHost`
(`NavigationGraph.kt`, `navigation-compose 2.8.4`). **Home** and the five secondary
destinations (**Campaign · Map · Encounter · God · Setup**) are reached from the Home
dashboard or the overflow **More** sheet (`HomeDashboardScreen.kt`, `MoreSheet.kt`), all
inside `NavigationSuiteScaffold` (`NavigationShell.kt:102`).

| Destination | What | Needs the hub? |
|---|---|---|
| Home | Dashboard: quick-roll dice, party, destination grid | No — local |
| Dice | Notation engine (`2d6+3`, `kh`/`kl`, exploding `d6!!`, advantage, 2e degrees of success) + spring canvas or Filament 3D pit (all six dice), haptics + SFX | No — fully offline |
| God | Loot bazaar: level/budget/theme commissions, rune-validated drops | Yes |
| Hero | Roster + sheet (AC/HP/abilities/proficiencies/feats), Room-backed, shareable | No — local |
| Rules | FTS5 oracle: live search + 1e/2e chips, expandable hits | No — on-device extract |
| Combat | Initiative ladder, conditions, vault summon, native end-turn decay | No — local |
| Encounter | Threat forge + monster vault, persisted rosters | Generation needs hub |
| Map | Vault gallery + pinch-zoom viewer, GM/player layers, PNG share | Generation needs hub |
| Campaign | Journal ledger + chronicler summaries of combat events | Summaries need hub |
| Setup | Tether (hub URL + live link status), Music/SFX/Haptics toggles, Audio Credits | — |

Sharing (not backup — there is **no** backup/restore in the app): a character exports as
plain text and a map exports as a PNG, both through the system share sheet via
`FileProvider` (`service/ExportService.kt`) — no storage permissions needed. The hub's
`/campaign/export` + `/campaign/import` endpoints exist in the contract but the Kotlin
client does not call them.

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
| `spoke_kt/` | Native Kotlin app (`com.pathfindergod.spoke`, Compose + one Filament pit). Hub owns all agents; Kotlin owns ViewModels + rendering per `shared/openapi.yaml`. |
| `shared/openapi.yaml` | The API contract both sides build against (v0.1.0, 26 paths). |
| `data/` | Laptop-only `.db` files (git-ignored). Schema: [`data/SCHEMA.md`](data/SCHEMA.md). |
| `tools/` | Command Center source (PySide6). The old `gen_audio.py` sound synth was deleted in BP-06 WP-2 — all bundled audio is licensed third-party and credited in [`docs/audio-credits.md`](docs/audio-credits.md). |
| `tools/command_center/dist/` | Standalone `.exe` (git-ignored, built via PyInstaller). |
| `docs/` | Guides: [`architecture`](docs/architecture.md) · [`database`](docs/database.md) · [`api`](docs/api.md) · [`troubleshooting`](docs/troubleshooting.md) · setup hub + retired spoke notes. |

## Data & licensing

- Rules DB: 44,620 rows built from open sources — Paizo PRD text under the
  **Open Game License 1.0a**, Pf2ools JSON under **MIT**, and targeted
  gap-fill scrapes under Paizo's **Community Use Policy**. Build scripts and
  the source registry live in `hub/scripts/`; the `.db` files themselves are
  git-ignored and reproducible.
- **Personal / non-commercial use is unrestricted.** Adventure-path prose and
  Golarion lore (Product Identity) are deliberately *not* scraped — mechanics
  only.
- **Commercial redistribution** of the bundled DB is limited by the CUP-sourced
  rows; a commercially distributable build requires a Paizo license or a
  rebuild excluding CUP sources (see
  [`docs/database.md`](docs/database.md#redistribution-terms)). The *code* in
  this repository is yours to license as you see fit — the caveat applies only
  to the rules data.

## Cloning

The native rulebook asset is stored with Git LFS — install it once
(`git lfs install`), otherwise you'll get a pointer file instead of the database:

```bash
git lfs install
git clone https://github.com/GhostMan612/pathfinder_god.git
```

## Status

Flutter spoke deleted (Phase 22): `spoke_kt/` is the client. Terminal UI is Jetpack
Compose **plus one first-party Filament surface** — the dice pit (`ui/pit/FilamentPit.kt`,
lit `shadingModel`, directional key light + IBL, shadow-mapped ground plane). No
Unity/Godot, no game engine, no NDK/CMake — which is also why AGDK's Swappy is rejected.
Current: hub `pytest hub/tests/`: 107/107 · `assembleDebug`: BUILD SUCCESSFUL.
BP-06 (WP-0…WP-9) is code-complete; see `blueprints/CURRENT_STATE.md` (local-only).
History: [`RELEASE_NOTES.md`](RELEASE_NOTES.md).

---
*As Above, So Below. As Within, So Without. The Future Dictates the Past and the Past is Always Present.*
