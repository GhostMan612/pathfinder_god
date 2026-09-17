# Pathfinder God — Kotlin/AGDK Port Specification (Muse Spark 1.3)

Target: rewrite the Flutter Spoke (`spoke/lib`, 39 files) as a 100% native
Kotlin Android app (package `com.pathfindergod`, label "Pathfinder God"),
Jetpack Compose UI, AGDK-ready native layer for future game-loop rendering.
The Python Hub is untouched; `shared/openapi.yaml` plus the existing REST/WS
shapes remain the wire contract.

> **Port correction (read first):** the Hub serves HTTP **and** WebSocket on
> port **8000**. Port **11450** is Ollama on the laptop and is never
> contacted by the phone. Any reference to "Hub on 11450" means `:8000`.

## 0. Source Inventory (what is being ported)

- `main.dart` — boot chain: reclaim temp files → FlutterGemma init →
  HubConfig load → AudioService/Haptics init → RulebookDb open →
  SlmGuide probe → `ChangeNotifierProvider(CombatStore)` → `HomeScreen`.
- 13 screens: Dice, God chat, Hero list, Character sheet (9 tabs),
  Character builder, Rulebook (search/browse/guide), Rulebook chat,
  Combat tracker, Encounter builder, Map maker (forge/vault), Settings.
- 12 services: `hub_client` (REST+WS), `hub_discovery` (mDNS),
  `rulebook_db` (bundled 48 MB gz → ~58 MB FTS5), `slm_guide`
  (Gemma 3n ~2 GB via MediaPipe, gated download), `audio_service`
  (4-player SFX pool + looping BGM), `combat_store`, `miss_queue`,
  `rulebook_chatbot`, `backup_service`, `haptics_service`, `export_service`
  (Markdown sheets, letter-size map PDFs).
- 3 SQLite stores: `pathfinder_spoke.db` v3 (characters, 29 cols, heavy
  JSON blobs), `maps_cache.db` v2 (dual GM/player layers), 
  `encounters_cache.db` v1. Plus the read-only 44,620-row rules FTS5.
- Models: `character.dart` (~1100 lines: abilities, proficiencies, feats,
  spells, equipment, derived-stat math), `combatant.dart`, `encounter.dart`,
  `api/models.dart` (`RuleHit`, `HubHealth`, `AskResponse`, `StreamEvent`…).
- Dice: pure-Dart roller + `Matrix4` 3D tumble animation + impact SFX /
  haptics / crit flash — first candidate for native rendering (§4).

## 1. Architecture Translation (Provider → ViewModel/StateFlow)

Stack: single-`Activity` + Compose Navigation, Hilt DI, one `ViewModel`
per screen, `StateFlow<UiState>` + `SharedFlow<Event>` for one-shots
(snackbars, share sheets). Rules:

| Flutter (current) | Kotlin (target) |
|---|---|
| `ChangeNotifierProvider(CombatStore)` in `main.dart` | Hilt `@Singleton CombatRepository` + `@HiltViewModel CombatViewModel`; `collectAsStateWithLifecycle()` in composables (replaces `Consumer`) |
| `CombatStore extends ChangeNotifier` + `notifyListeners()` | `MutableStateFlow<CombatUiState>`; single `data class CombatUiState(combatants, activeIndex, round, isProcessing)` — one emission per mutation, no listener leaks |
| `FutureBuilder` boot gate | `AppViewModel: StateFlow<BootState>` (`Loading → Ready(models) / Failed`); splash API (`androidx.core.splashscreen`) until `Ready` |
| `StatefulWidget` + `TextEditingController` (sheet, 26 fields) | `CharacterSheetViewModel` holding `MutableStateFlow<CharacterDraft>`; Compose `TextField(value/onValueChange)` — no controller disposal graph |
| `ReorderableListView(onReorderItem)` | Compose `LazyColumn` + `rememberReorderableLazyListState` (BurnoutCrew) or drag-handle `Modifier.draggable` |
| `SegmentedButton`, `TabRow` (9-tab sheet) | Material3 `SingleChoiceSegmentedButtonRow`, `ScrollableTabRow` + `HorizontalPager` |
| `flutter_animate` cascades | `AnimatedVisibility` + `animateItem()` / `updateTransition` staggers |
| `ImagePicker` portrait | ActivityResult `PickVisualMedia`; Coil `AsyncImage` for file + base64 (`data:` URIs for map PNGs) |
| `share_plus` text/files | `ACTION_SEND`/`ACTION_SEND_MULTIPLE` via `FileProvider` (PDFs, PNGs, Markdown `.md` file — Android has no text+file combo guarantee) |
| `pdf` + `printing` letter export | Android `PrintedPdfDocument` (framework, no dep) rendering the bitmap centered onLetter; share via `FileProvider` |
| `flutter_native_splash` + `flutter_launcher_icons` | `core-splashscreen` (`#1E1B18`, centered `pf_logo`) + adaptive-icon XML (already `#2D2C2A`/`#7B1E1E`) |
| `flutter_markdown_plus` rulebook sheet | `MarkdownText` (JeeteshSurana) or WebView fallback; keep gold/crimson stylesheet mapping |
| `path_provider` temp/docs dirs | `cacheDir` / `filesDir`; `FileProvider` for shares |

Screen → ViewModel map: `DiceViewModel` (roller state, history ≤30),
`GodChatViewModel` (collects `Flow<StreamEvent>`), `HeroViewModel`,
`SheetViewModel` (+ `recalculateDerived()` ported 1:1 — ancestry/class HP,
proficiency bonus `level+2/4/6/8`, AC/装甲 caps, spell DCs),
`RulebookViewModel` (FTS5 query, miss-queue drain), `CombatViewModel`
(end-turn notes → snackbar event + SFX event), `EncounterViewModel`,
`MapViewModel` (grid flag, GM/player toggle, vault CRUD),
`SettingsViewModel` (base URL, hub probe, SLM download state machine).

## 2. Database Migration (SQLite → Room)

Keep the proven shape: normalized columns for query fields, JSON blobs
for deep sub-documents (`kotlinx.serialization` `TypeConverter`s). One
`SpokeDatabase` (`pathfinder_spoke.db`) absorbing the three files is
acceptable; keep separate DBs only if migration risk demands it.

- `CharacterEntity` — all 29 columns verbatim (`portrait_path` included);
  `abilities/proficiencies/feats/spellcasting/equipment/derived/conditions`
  as `@TypeConverter` JSON strings. `Room autoMigrations 2→3`
  (`ALTER TABLE characters ADD COLUMN portrait_path TEXT`).
- `MapEntity` — `id, prompt, gm_base64_png, player_base64_png, width,
  height, created_at`; precedent is the destructive v1→v2 `DROP TABLE`
  upgrade; repeat only for cache tables, never for characters.
- `EncounterEntity` — `id, theme, threat, monsters_json, target_xp,
  created_at`.
- **Rules FTS5 — resolved as-built.** The app bundles `pathfinder_rag.db.gz`
  because `sqlite3_flutter_libs` ships FTS5, which AOSP SQLite lacks.
  Native side runs Room on `mil.nga:sqlite-android:3450200` (SQLite 3.45
  with FTS5) through the hand-rolled `NgaSQLiteOpenHelperFactory` bridge
  (`io.requery:sqlite-android` does not exist on Central — do not revert).
  `RuleFtsEntity` maps the real `rules` virtual table with `@RawQuery`
  `MATCH` + `bm25()`. Still unproven: Room's identity-hash check against
  the external table at first open — spike before the Glass rules screen.
- Extraction flow to preserve: first launch gunzips 48 MB → app storage
  once (`bundleVersion` marker file forces re-extract); `RoomDatabase.Callback`
  is the wrong hook for a 58 MB asset — do it in `AppViewModel` boot
  with progress events, same as today.
- Tests: `room-testing` migrations (`2→3` portrait column present),
  DAO round-trips for dual-layer `CachedMap`, FTS5 smoke query returning
  the known `Flanking` row.

## 3. Network Resilience (OkHttp + ForegroundService)

- Base URL: `DataStore<Preferences>` key `hub_base_url`, default
  `http://10.0.2.2:8000` (emulator). `HttpUrl` builder mirrors
  `HubConfig.httpUri/wsUri` (http↔ws scheme swap).
- REST: Retrofit + Moshi codegen against `shared/openapi.yaml` surface:
  `GET /health`, `POST /ask`, `GET /rules/search`, `POST /rules/fetch`,
  `POST /rules/missed`, `POST /generate/{character,loot,…}`,
  `POST /combat/resolve-strike`, `POST /combat/end-turn`
  (`conditions + current_hp` → `conditions + notes + damage_taken`),
  `POST /encounter/generate`, `POST /map/generate`
  (`prompt + grid_enabled` → `gm_base64_png + player_base64_png`),
  campaign import/export. Timeouts mirror `HubClient`: 6 s health,
  30 s generated calls.
- Streaming: OkHttp `WebSocket` to `/stream` with 15 s ping, mapping
  start/chunk/retrying/end/error frames to `Flow<StreamEvent>`; retry
  policy identical to today (≤3 reconnects, 400 ms exponential backoff,
  hub regenerates after mid-stream reconnect — clear partial text on
  `retrying`). Collect in `GodChatViewModel` with
  `flowOn(Dispatchers.IO)` + `stateIn(SharingStarted.WhileSubscribed)`.
- Keep-alive: `HubLinkService : Service()` as a **foreground service**
  (`FOREGROUND_SERVICE_CONNECTED_DEVICE`, persistent status-bar
  notification with hub name/latency + Disconnect action) owning the
  OkHttp client and socket; UI binds via `ServiceConnection` or shares
  the singleton from the `:app` process. This survives Doze windows that
  today drop the Dart socket on sleep; add `WorkManager` periodic
  `MissQueueWorker` (15 min, `NetworkType.CONNECTED`) to drain queued
  rule misses, replacing the manual `MissQueue.drain` call.
- Discovery: `NsdManager` browse `_pathfindergod._tcp.local` (4 s resolve
  window) + identical fallbacks in order: last-known URL →
  `192.168.137.1:8000` hotspot gateway → `10.0.2.2:8000` emulator; every
  candidate verified with `GET /health` before display. Requires
  `CHANGE_WIFI_MULTICAST_STATE` + runtime `NEARBY_WIFI_DEVICES` on API 33+.
- Offline tiers preserved: bundled FTS5 → hub → miss queue → on-demand
  scrape; `GET /rules/fetch` results upserted locally.

## 4. AGDK Integration (future game-loop hooks)

No engine today — this section reserves the seams so a Godot/Unity C++
module drops in without rewriting the app:

- Ship `GameActivity` (`com.google.androidgamesdk.GameActivity`) as the
  `MainActivity` base now (static `android.app.NativeActivity` meta-data
  off); render the Compose UI on top until a surface is needed. Keeps
  `android:configChanges` and immersive-sticky behavior identical.
- `native-lib` module skeleton: `externalNativeBuild` (CMake), one JNI
  bridge `GodotBridge.kt` (`external fun rollDiceVisual(seed: Long)`),
  `System.loadLibrary("godot_bridge")` guarded by `try/catch` so the app
  runs fully without the `.so` present.
- Audio: migrate dice SFX to **Oboe** (`AAudio`, low-latency stream,
  `PerformanceMode::LowLatency`) reusing the pooled-player design
  (4 voices) and the existing CC0/CC-BY asset set; BGM stays on
  `MediaPlayer` loop.
- Dice 3D first: port `dice_physics.dart` tumble curves to a Vulkan
  swapchain scene or Filament `ModelViewer` as the pilot native surface
  (deterministic result stays in Kotlin; native layer is presentation
  only). Frame pacing via **Swappy**, perf telemetry via **Tuning Fork**
  from day one of native rendering.
- Input: **Paddleboat** game-controller mapping reserved for tabletop
  remote mode; `games-frame-pacing` + `games-performance-tuner` AARs via
  the AGDK libraries bill of materials.

## 5. Build, Test, Rollout

- Modules: `:app` only (single-module scaffold, as built). Pinned as-built:
  AGP 9.0.1 (built-in Kotlin — no `kotlin.android` plugin, no kapt),
  KSP 2.3.4 + Room 2.7.0 (2.6.1's processor crashes on new Kotlin),
  Compose BOM 2024.10.01 (newer BOMs demand compileSdk 35; directive
  holds 34), `mil.nga:sqlite-android:3450200`, Retrofit 2.11/OkHttp 4.12,
  AGDK games-activity/frame-pacing. `androidx.sqlite` 2.5 interfaces are
  Kotlin properties (`override val/var`, `Array<out Any?>` bind args).
- Tests: JUnit5 + Turbine (`CombatViewModel` end-turn notes event,
  `GodChatViewModel` retry frame clears text), Robolectric for DAOs,
  MockWebServer for `/combat/end-turn` dual payload + `/map/generate`
  dual layers, screenshot tests for `RpgPanel` 9-patch equivalents
  (port `stone_border/parchment/gothic_stone` center-slices 1:1).
- Rollout (strangler, contract-first): milestones M1 data+network
  (Room + Retrofit + discovery, behind the Flutter app via shared hub),
  M2 screens in Navigation order (Dice → Combat → Sheet → Rulebook →
  Map → Settings), M3 native audio/dice pilot, M4 AGDK surface option.
  Acceptance per milestone: `connectedAndroidTest` green, hub
  `pytest` untouched, wire payloads byte-identical to `openapi.yaml`.
- Risks: platform SQLite without FTS5 (§2 — mitigated by the NGA
  bridge); MediaPipe Gemma 3n has no AGDK shortcut — keep the
  `flutter_gemma` equivalent via MediaPipe LLM Inference AAR and the
  existing side-load + gated-download flow; 58 MB rules DB keeps the
  `android:largeHeap` + scoped-storage extraction plan mandatory.
