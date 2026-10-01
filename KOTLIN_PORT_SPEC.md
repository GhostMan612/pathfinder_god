<!-- As Above, So Below. As Within, So Without. The Future Dictates the Past and the Past is Always Present. -->
# Pathfinder God — Kotlin/AGDK Port Specification (Muse Spark 1.3)
> **STATUS: COMPLETE (Phase 22, 2026-09-18) + BP-06 WP-0…WP-9.** The Flutter spoke is deleted;
> `spoke_kt/` is the client. This document is a build record. Where a passage
> below is still forward-looking, the **as-built** block at the head of that
> section wins; the residual forward-looking parts are called out there.

Record: the Flutter Spoke is rewritten as a 100% native Kotlin Android app
(applicationId `com.pathfindergod.spoke`, label "Pathfinder God"). The UI is
Jetpack Compose with exactly **one** first-party native render surface — the
Filament 1.76 dice pit (swapchain on a `SurfaceView`, lit shading, directional
key light + IBL, shadow-mapped ground plane; see §4). No Unity, no Godot, no
game engine, no NDK/CMake. Audio ships on SoundPool/MediaPlayer; AGDK supplies
the activity base and an explicit high-refresh request, and
`games-frame-pacing` is pinned but **not called into** — jank telemetry is
`Choreographer.getFrameMetrics()` sampled by `PitFrameTelemetry`.
The Python Hub is untouched; `shared/openapi.yaml` plus the existing REST/WS
shapes remain the wire contract.

> **Port correction (read first):** the Hub serves HTTP **and** WebSocket on
> port **8000**. Port **11450** is Ollama on the laptop and is never
> contacted by the phone. Any reference to "Hub on 11450" means `:8000`.

## 0. Source Inventory (what is being ported)

> **This section describes the deleted Flutter `spoke/` tree as it stood at the
> start of the port.** Every path below is gone. Where the port diverged from
> this inventory, the as-built blocks in §§1–5 and the notes inline here say so —
> e.g. the `48 MB gz` rulebook asset shipped **raw** at ~19MB, `slm_guide`
> (MediaPipe/Gemma 3n) was **never ported**, and the `haptics_service` was
> replaced by `VibrationEffect` waveforms inside `AudioService.kt`.

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

> **As-built corrections (BP-06):** there is **no DI framework** — no Hilt, no
> Dagger, no kapt. Wiring is manual constructor injection plus
> `ViewModelProvider.Factory` helpers (RULES.md §5.4). Preferences are
> **`SharedPreferences`** in `data/local/AppPreferences.kt`, not `DataStore` —
> and its `FILE_NAME` is still `"pathfinder_network"` (the file was renamed
> `NetworkPreferences.kt` → `AppPreferences.kt` in WP-6, the key was not, so
> live installs keep their hub URL and audio prefs). The screen→ViewModel map
> below is close to as-built except that `GodChatViewModel` and
> `CharacterSheetViewModel` are not separate classes: streaming is collected
> from `HubWebSocketClient` into the Loot/Rule/Combat screens' own ViewModels,
> and the sheet lives inside `CharacterDetailScreen`.

Stack as planned: single-`Activity` + Compose Navigation, one `ViewModel`
per screen, `StateFlow<UiState>` + `SharedFlow<Event>` for one-shots
(snackbars, share sheets). Rules:

| Flutter (current) | Kotlin (target) |
|---|---|
| `ChangeNotifierProvider(CombatStore)` in `main.dart` | ~~Hilt `@Singleton CombatRepository` + `@HiltViewModel CombatViewModel`~~ — **Hilt was never adopted**; manual constructor injection + `ViewModelProvider.Factory` (see the as-built block above). `collectAsStateWithLifecycle()` in composables (replaces `Consumer`) |
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

> **As-built corrections (BP-06):** the three stores were **not** merged into one
> `SpokeDatabase`; `AppDatabase` (`pathfinder_spoke.db`, characters/maps/
> encounters/campaigns/rolls) and `RulesDatabase` (`pathfinder_rag.db`, the
> read-only FTS5 rules extract) both exist, the latter behind
> `NgaSQLiteFactory`. The 2→3 upgrade is a **hand-written additive
> `MIGRATION_2_3`**, not an `autoMigration` — `AppDatabase` is at `version = 3`
> and registers the migration explicitly. Room's identity-hash check against the
> *external* FTS5 table is resolved by keeping rules in a separate database, so
> the "still unproven" spike below no longer applies to the rules screen.

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
- **Rules FTS5 — resolved as-built.** The app bundles `pathfinder_rag.db` raw (a `.gz` name must not be used — AGP decompresses gzipped assets at build time and renames the entry, breaking the runtime open path)
  because `sqlite3_flutter_libs` ships FTS5, which AOSP SQLite lacks.
  Native side runs Room on `mil.nga:sqlite-android:3450200` (SQLite 3.45
  with FTS5) through the hand-rolled `NgaSQLiteOpenHelperFactory` bridge
  (`io.requery:sqlite-android` does not exist on Central — do not revert).
  `RuleFtsEntity` maps the real `rules` virtual table with `@RawQuery`
  `MATCH` + `bm25()`, and lives in `RulesDatabase` (its own Room database), so
  Room's identity-hash check never sees the external table. The "spike before
  the Glass rules screen" risk is closed.
- Extraction flow as-built: the asset is a **raw `.db`**, so there is no
  gunzip. `DatabaseAssetManager.ensureExtracted` copies the asset
  (`context.assets.open("rules/pathfinder_rag.db")` → temp file →
  `renameTo`, on `Dispatchers.IO`) into `context.getDatabasePath(...)` once,
  and a marker file `pathfinder_rag.db.v$BUNDLE_VERSION` (currently
  `BUNDLE_VERSION = 2`) forces a re-copy. There is no `AppViewModel`; the rules
  database is opened on demand from the screens that need it.
- Tests: the migration is exercised by `MIGRATION_2_3` being registered on
  `AppDatabase` (`version = 3`); there is no `room-testing` in this lane —
  the lane is JUnit 4 only, and DAO/FTS5 assertions live in `hub/tests/` on the
  Python side.

## 3. Network Resilience (OkHttp + ForegroundService)

> **As-built corrections (BP-06):** base URL is `SharedPreferences`
> (`AppPreferences`), not `DataStore`. The foreground service shipped as
> `service/HubForegroundService.kt` (`FOREGROUND_SERVICE_DATA_SYNC`, declared
> in the manifest) and owns the backoff reconnect, so the Doze drop is solved.
> **Not shipped:** `WorkManager` / `MissQueueWorker` and `NsdManager` mDNS
> discovery — neither is a dependency of this lane. Hub entry is manual in
> **Setup → Tether** plus the hub `/health` probe; mDNS is a future item.

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

## 4. Native Performance (AGDK libraries, one render surface, no engine)

Terminal decision: the UI is Jetpack Compose. No Unity, no Godot, no game
engine, no JNI bridge skeleton — earlier drafts reserved a `GodotBridge.kt` seam
and are deleted from the plan. One narrow exception was taken in BP-06 WP-4: the
dice pit is a first-party Filament 1.76 render surface (swapchain on a
`SurfaceView`), because a lit, shadowed, settling die cannot be drawn
convincingly with 2D canvas primitives. That surface is ours — no engine, no
NDK/CMake, and therefore **no Swappy** (it is C++). What survives from AGDK is
libraries plus the activity base:

- AGDK activity base (WP-5): `MainActivity` extends
  `androidx.games.activity.GameActivity` (games-activity 3.0.5). It is an
  `AppCompatActivity`, so `Theme.PathfinderGod` parents
  `Theme.AppCompat.NoActionBar` in both `res/values/` and
  `res/values-v31/`, and `androidx.appcompat` is a direct dependency. A
  platform `android:Theme.Material` parent compiles clean and then throws
  `IllegalStateException: You need to use a Theme.AppCompat theme (or
  descendant) with this activity` on launch — this pairing is a single
  contract, never change one half without the other.
- Explicit high-refresh request (WP-5): Android 15+ throttles games to
  60 Hz unless the app asks, so `PitFrameGovernor` reads the target from
  `display.mode` and same-resolution `display.supportedModes` (never a
  hardcoded 120), then requests it with `Window.setFrameRate(rate,
  FRAME_RATE_COMPATIBILITY_FIXED_SOURCE)` on API 30+, with
  `LayoutParams.preferredRefreshRate` / `preferredDisplayModeId` as the
  API-21+ floor and `Surface.setFrameRate` on the pit's own surface.
  `Surface.setFrameRate` is also API 30, so it is not the pre-30
  fallback — `preferredDisplayModeId` is.
- Frame budget (WP-5): the integration step ceiling, the Filament
  `Renderer.DisplayInfo` refresh rate and the jank threshold are all
  derived from the live display mode (`PitRefreshPolicy`), not
  hardcoded. `Choreographer` exposes no interval setter — vsync fixes the
  interval — so "tuning the swap interval" means requesting the mode and
  measuring against the budget it implies.
- Jank telemetry (WP-5): `Choreographer.getFrameMetrics()` sampled by
  `PitFrameTelemetry`, gated on `ApplicationInfo.FLAG_DEBUGGABLE`, one
  log line per 240 frames. **Tuning Fork is not a dependency** and the
  earlier "frame-time histograms around the Compose dice/map canvases"
  claim was never true; the sampled surface is the Filament pit.
  `androidx.games:games-frame-pacing` stays declared at 2.1.2 but is not
  called into — `ChoreographerWrapper` is the intended consumer and was
  left alone deliberately, because its API could not be verified without
  a compiler in the WP-5 lane.
- Audio: Oboe remains superseded without execution — `SoundPool` +
  `MediaPlayer` serve; the low-latency AAudio stream buys nothing on the
  dice SFX budget.

## 5. Build, Test, Rollout

- UI architecture (locked): Jetpack Compose is terminal, **with the single
  documented exception of the Filament dice pit** (§4). No Unity/Godot
  integration at any milestone — §§4–5 describe libraries, ViewModels, the one
  render surface, and Compose screens only.
- Modules: `:app` only (single-module app, as built). Pinned as-built:
  AGP 9.0.1 (built-in Kotlin — no `kotlin.android` plugin, no kapt),
  KSP 2.3.4 + Room 2.7.0 (2.6.1's processor crashes on new Kotlin),
  Compose BOM 2024.10.01, navigation-compose 2.8.4 + material3-adaptive-
  navigation-suite 1.3.1, SDK floor compileSdk 37 (Filament 1.76 demands
  it) + targetSdk 34 + minSdk 26 (as built in `app/build.gradle.kts`),
  `mil.nga:sqlite-android:3450200`, Filament + filamat 1.76.0,
  Retrofit 2.11/OkHttp 4.12, androidx.appcompat 1.7.0 (GameActivity needs
  it), AGDK games-activity/frame-pacing. `androidx.sqlite` 2.5 interfaces are
  Kotlin properties (`override val/var`, `Array<out Any?>` bind args).
  Every pin lives in `gradle/libs.versions.toml`; nothing bumps without a gate.
- Tests: **JUnit 4** (`junit 4.13.2`) for the JVM lane. There is no Turbine,
  no Robolectric, no MockWebServer and no JUnit 5 in this lane — the earlier
  plan assumed all four. What actually exists: `DiceEngineTest` (34 cases after
  the WP-6 rewrite), `PitSettleTest` / `PitGeometryTest` / `PitFramePolicyTest` /
  `DieMeshTest` (centroid-normal settle, 2D↔3D parity, mip chain), and
  `MapSamplingTest`; plus an `src/androidTest` source set of instrumented
  accessibility tests that need a device. Hub side: `pytest hub/tests/` with a
  hermetic conftest that patches every bound `get_settings`, so the suite is
  green with `data/` absent.
- Rollout (done): M1 data+network (Room + Retrofit, behind the shared hub) —
  done; M2 screens (Dice → Combat → Hero → Rules → Map → Campaign → Setup →
  God → Encounter — **nine destinations**) — done. **The bottom bar is four
  items, not nine** (BP-06 WP-3): Material 3 caps a navigation bar at 3–5, so
  Dice · Combat · Hero · Rules are the tabs and Home plus the other five live
  behind the dashboard and `MoreSheet`, all inside a `NavigationSuiteScaffold`.
  UI sprints Phases 12–21 (Glass shell, dice physics, roster, ladder, tether,
  vault, chronicler, oracle, bazaar, encounter, FileProvider export,
  vault→tracker bridge) — done. Superseded without execution: Oboe migration
  (SoundPool serves), baseline profiles, `games-frame-pacing`'s
  `ChoreographerWrapper` (platform `FrameMetrics` telemetry serves), MediaPipe
  /Gemma 3n on-device SLM (no such dependency in the lane). Executed in BP-06:
  the AGDK `GameActivity` base + its AppCompat theme contract, the explicit
  high-refresh request, the Filament pit, the `God*` design system, the audio
  licence discharge, and the accessibility pass — the "AGDK surface milestone"
  line below predates the Filament pit landing.
  Acceptance held: hub `pytest` green, wire payloads byte-identical to
  `openapi.yaml`.
- Risks: platform SQLite without FTS5 (§2 — mitigated by the NGA
  bridge); **MediaPipe Gemma 3n was never ported** — there is no LLM on-device
  and no MediaPipe dependency, so the Guide tier remains hub-only; the
  58 MB rules DB keeps the `android:largeHeap` + extraction plan mandatory.
