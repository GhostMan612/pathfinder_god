<!-- ============================================================
As Above, So Below. As Within, So Without.
The Future Dictates the Past and the Past is Always Present.
============================================================ -->

# Horizon Audit — Pre-Compose Freeze

Read-only sweep of `hub/` and `spoke_kt/` plus Flutter extraction inventory.
Method: route-table diff, live route probe, signature inspection of cached
AARs, compile-log forensics. No source modified.

Severity: CRITICAL (broken at runtime now) > HIGH (blocks Glass) > MEDIUM
> LOW (hygiene).

## 0. Live-Proven Criticals

| # | Path | Issue | Recommended Action |
|---|------|-------|--------------------|
| C1 | `hub/app/agents/continuity.py:153,187,201,211,224,236` | Six `await` calls on synchronous `CampaignRepository` methods (all repo methods are plain `def`, `hub/app/db/repository.py:109-230`). `process_session` raises `TypeError` on every run; the `/campaign/note` background task (`hub/app/api/campaign.py:123-127`) dies silently behind try/except. Session continuity pipeline is fully down. | Make repo methods async or drop the six `await`s; add a regression test calling `process_session` with fakes. |
| C2 | `hub/app/main.py:65,72` + `hub/app/api/loot.py:32` | `POST /generate/loot` is unreachable. The generic `/{kind}` route registers first and `loot` is absent from `VALID_KINDS`, so every call returns `400 Unknown kind` (proven live via TestClient). Phase 9's flagship endpoint has never served traffic. | Add `"loot"` to `VALID_KINDS` with a dedicated-branch, or move `loot.router` inclusion above `generate.router`. |

## 1. Orphaned / Unused Code Stubs

| Path | Issue | Recommended Action |
|------|-------|--------------------|
| `hub/app/agents/continuity.py:25-29` | `LLMOrchestrator` imported twice (direct + `TYPE_CHECKING` re-import). | Delete one import. |
| `hub/app/agents/character_builder.py:182-212` | `RulesLawyerAgent.validate_action_sync` monkey-patched at module import; splits validation logic across two files. | Move into `rules_lawyer.py` as a real `@staticmethod`. |
| `hub/app/api/campaign.py:89,111` | `get_client_ip(request) if 'request' in locals()` — `request` is never a local; always logs `"unknown"`. | Accept `Request` param or log honestly. |
| `hub/app/api/campaign.py:139-147` | `reset_campaign` declares `request: Request = None` then calls `get_client_ip(request)` → `AttributeError` on `None.headers` at runtime. | Default-guard or require the parameter. |
| `hub/app/api/monitoring.py:163` vs `hub/app/api/health.py:17` | Duplicate `GET /health` operation ID (`health_health_get` warning on every boot/test run). | Rename one operation ID. |
| `spoke_kt/.../data/network/HubWebSocketClient.kt` | Every message is emitted twice: `callbackFlow.trySend` and companion `_events.tryEmit`; nothing consumes the client-level flow. | Keep one channel; delete the other. |
| `spoke_kt/.../service/HubForegroundService.kt` | `_status`/`_events` are process-global companion singletons; a second service instance would corrupt both streams. | Scope flows to the service instance; expose via Binder only. |
| `spoke_kt/.../data/repository/*.kt` | `CharacterRepository`, `EncounterRepository`, `MapRepository` all hold an unused `api: HubApi` parameter. Zero call sites in the tree. | Either wire sync methods or drop the parameter until Glass needs it. |

## 2. Hub-to-Spoke API Contract Mismatches

Hub prefixes: `/combat`, `/generate`, `/map`, `/encounter`, `/campaign`, `/ask`, `/rules`, `/health`. Spoke Kotlin client: `spoke_kt/.../data/network/HubApi.kt`.

| Endpoint | Hub Status | Spoke (`HubApi.kt`) Status |
|----------|-----------|----------------------------|
| `POST /combat/resolve-strike` | OK | OK, shapes match |
| `POST /combat/end-turn` | OK (`conditions`+`current_hp` → `conditions`+`notes`+`damage_taken`) | OK, `EndTurnRequest/Response` match |
| `POST /generate/loot` | **Shadowed, returns 400 (C2)** | Declared, `LootResponse` shape matches the (unreachable) handler |
| `POST /generate/character` | Dedicated handler wins over `/{kind}`; expects `{prompt}`, returns `{valid,character,errors}` | **MISMATCH**: sends `{prompt,edition}`, expects `{answer,backend,mode,edition,sources}` → deserialization failure at runtime |
| `POST /generate/map` | Generic orchestrator route, returns freeform `GenerateResponse` | Declared, shape matches |
| `POST /map/generate` (dual GM/player layers) | OK | **Absent** — two map paths exist, Kotlin only knows the freeform one |
| `POST /encounter/generate` | OK, but `template` param and new `hp`/`template` monster fields are agent-only: `EncounterRequest` has no `template`, `EncounterMonsterResponse` drops `hp`/`template` | **Absent entirely** |
| `GET /health`, `POST /ask`, `WS /stream` | OK, no auth on WS | **Absent** (service hardcodes only the stream URL string) |
| `GET /rules/search`, `POST /rules/fetch`, `POST+GET /rules/missed` | OK | **Absent** (offline-first rules has no remote leg) |
| `GET|POST /campaign/*` (state, note, reset, summarize, export, import, backup, npcs, party) | OK | **Absent** (entire Phase 11 surface missing natively) |
| `GET /monitoring/*`, `GET /ready`, `GET /version` | OK | Absent (acceptable; diagnostics only) |

## 3. Missing Native Kotlin Infrastructure

| Component | Status | Priority |
|-----------|--------|----------|
| `Application` subclass / DI graph (Hilt or manual) | Missing. No owners for `AppDatabase`, `RulesDatabase`, `HubApi`, repositories, ViewModels. | HIGH — Glass cannot start without it |
| Retrofit builder (`Retrofit.Builder`, base URL, converters) | Missing. `HubApi` is an uninstantiable interface; converter dep already declared but unused. | HIGH |
| Base-URL configuration (DataStore + Settings) | Missing. Stream URL is a hardcoded `DEFAULT_STREAM_URL` constant. | HIGH |
| Compose screens / Navigation graph | Missing. Zero `@Composable` screens; `AppShell` is a placeholder `Text`. ViewModels have no collectors. | HIGH (is the Glass sprint itself) |
| `src/test` + `src/androidTest` | Missing entirely. No unit-test target exists. | HIGH |
| Rules DB asset (`assets/rules/pathfinder_rag.db.gz`) | Missing. `DatabaseAssetManager` points at an asset that is not in `spoke_kt/` (48 MB, must be copied from `spoke/`). | HIGH — blocks the offline rules screen |
| Launcher/adaptive icons | Missing (`android:icon` was dropped to keep the manifest mergeable). | MEDIUM |
| ProGuard/R8 rules (`consumer-rules.pro`, `proguard-rules.pro`) | Missing. kotlinx-serialization + Room need keep rules before any release build. | MEDIUM |
| `RuleFtsEntity` runtime validation | Risk. Plain `@Entity(tableName="rules")` over an external FTS5 virtual table: Room's identity-hash schema check runs at open time against a table it did not create. Compile passes; first launch of the rules screen may throw. | HIGH — spike before Glass rules screen |
| NGA driver thread-safety under Room's WAL + pooled access | Unproven. Bridge compiles; `SupportSQLite*` concurrency contract against `org.sqlite` sessions is exercised only at runtime. | MEDIUM — cover with instrumented open/query/close test |
| `KSP 2.3.4` pin (downgraded from 2.3.5 during debug; Room 2.6.1's processor crashes on new Kotlin, hence Room 2.7.0) | Works, but fragile pair. Re-verify on every Room/Kotlin bump. | LOW |
| `POST_NOTIFICATIONS` (API 33+) | Not declared; foreground-service notifications are exempt, so no action unless non-FGS notifications are added. | LOW (watch item) |

## 4. Database & RAG Integrity (Hub)

Healthy. `hub/app/db/schema.sql` covers campaigns/sessions/NPCs/locations/
items/quests/decisions/party/session_notes; every `CampaignRepository`
method used by export/import resolves to a real table and the new
`sessions`/`notes`/`decisions` import branches match column names
(`facts_json` string parsed back to list for `save_session`).
`data/pathfinder_rag.db` verified locally: FTS5 `rules(name, raw_content,
system, category, source_book)`, 44,620 rows. Phase 8/11 suites green
(28 + 4 tests). Pre-existing debt only: `hub/tests/test_api.py` carries
5 stale failures (Ollama-offline assumptions, outdated generate/websocket
expectations) unrelated to recent phases.

## 5. Flutter Extraction Inventory (still to port or document)

| Flutter source | What Glass still needs from it |
|----------------|--------------------------------|
| `spoke/lib/models/character.dart` (~1100 lines) | Full `recalculateDerived()` math (ancestry/class HP, `level+2/4/6/8` proficiency curve, armor Dex caps, spell DCs) — port 1:1 with property tests |
| `spoke/lib/services/combat_store.dart` | `onReorderItem` index semantics (already adjusted, no `-1` fixup); hub round-trip + offline `_tickConditionsLocally` fallback |
| `spoke/lib/models/encounter.dart`, `combatant.dart` | Canonical JSON keys (`xp_each`, `is_pc`, `duration_rounds`) the Kotlin models must match |
| `spoke/lib/dice/dice_physics.dart` | Tumble/bounce tween curves — the AGDK pilot-scene spec |
| `spoke/lib/services/slm_guide.dart` | Gated 2 GB download state machine (token, side-load, URL verify) for the native Guide screen |
| `spoke/lib/services/miss_queue.dart`, `backup_service.dart` | Offline queue + campaign export shapes for `WorkManager` + bundle sharing |
| `spoke/lib/services/export_service.dart` | Markdown sheet layout + letter-PDF centering rules for `PrintedPdfDocument` |
| `docs/audio-credits.md` + `audio_service.dart` | CC0/CC-BY asset list and 4-voice pool design for the Oboe migration |
| `KOTLIN_PORT_SPEC.md` §§2/5 | Stale: still names `io.requery:sqlite-android`, Room 2.6.1/kapt, and pre-verification assumptions — refresh to `mil.nga:sqlite-android:3450200`, Room 2.7.0/KSP, SDK 34 Compose BOM 2024.10.01 |

## 6. Actionable Roadmap for "The Glass"

1. Fix C1 (continuity awaits) and C2 (loot route shadow) + `reset_campaign` None crash; add regression tests. Nothing downstream is trustworthy while the journal pipeline 400s/500s.
2. Close the contract gaps decided in §2: fix `generateCharacter` shape, add `template`/`hp` to the encounter API, expose campaign + rules endpoints to `HubApi.kt`.
3. Land native infrastructure: `Application` + Retrofit builder + DataStore base URL + copy the rules asset + first instrumented Room/FTS5 open test (de-risks the §3 validation unknown).
4. Build Glass in dependency order: Rules (highest runtime risk) → Combat → Sheet (derived-math port with tests) → Dice/Map/Settings.
5. Refresh `KOTLIN_PORT_SPEC.md` §2/§5 to the as-built coordinates, then freeze it as the build record.
