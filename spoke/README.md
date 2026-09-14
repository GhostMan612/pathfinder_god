# Pathfinder God — Spoke (Flutter / Android)

The player's companion app: an offline **dice roller**, a **character sheet**
(with "forge a full bio with the God"), **live GM chat** streamed from the hub,
and a **rules browser** with 44,620 entries on-device. A thin client — the laptop
hub does the LLM + RAG work.

Package: `com.pathfindergod` · 5 tabs: Dice, God, Hero, Rules, Setup.

## Build (Android Studio — recommended)

Open `spoke/` in Android Studio, let Gradle sync, press **Run**.
`android/` is committed (branded config, icons, splash, `MainActivity` with the
rulebook streaming channel) — do **not** run `flutter create` over it.

```bash
cd spoke
flutter pub get
flutter analyze        # must be clean
flutter test           # 21/21
```

Contributor lane ends at source correctness: never commit APKs/AABs, never run
`flutter build`/`flutter run` for verification — a human builds in Android Studio.
Keep `sqlite3_flutter_libs` on `^0.5.42` (0.6.0 is end-of-life upstream).

## Connect (no IP typing)

**Setup → Find hub automatically** → tap your laptop → green
"Connected to the God" card. Falls back to hotspot gateway, emulator loopback,
and last-known URL. Manual entry: `http://<laptop-lan-ip>:8000`
(emulator: `http://10.0.2.2:8000`). Never `:11450` — that's Ollama.

## Offline-first

| Dice (degrees, animated die, SFX/haptics) | Always |
| Character sheet + export/import | Always |
| Rules search/browse/Guide chatbot | Always (bundled FTS5) |
| God chat, generators, Forge | Hub online |

Offline DB: `assets/rules/pathfinder_rag.db.gz` (Git LFS) extracts on first
launch to app storage, read-only. After re-bundling, bump
`RulebookDb.bundleVersion` or devices keep the stale copy.

## Layout

```
lib/
├── main.dart                  # init (HubConfig, audio, haptics) + MaterialApp
├── config/hub_config.dart     # hub URL persistence (hub_base_url)
├── api/                       # hub_client (REST + auto-reconnect WS), models
├── dice/                      # dice.dart (NdM/kh/kl/PF2e check), dice_physics.dart
├── models/character.dart      # full PF2e model + recalculateDerived()
├── screens/                   # dice, gm_chat, character_*, rulebook (+chat), settings
├── services/                  # rulebook_db (offline FTS5), rulebook_chatbot,
│                              # audio_service, haptics_service, backup_service,
│                              # hub_discovery (mDNS)
├── storage/character_store.dart  # phone-only SQLite (characters)
└── theme/app_theme.dart       # gold/crimson/parchment
test/                          # dice_check, character_derived, rulebook_db, hub_discovery
```

Full walkthrough: [`../docs/setup-spoke-android.md`](../docs/setup-spoke-android.md).
Troubleshooting: [`../docs/troubleshooting.md`](../docs/troubleshooting.md).
