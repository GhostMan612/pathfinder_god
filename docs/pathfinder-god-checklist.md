# Pathfinder God — Master Checklist

Living tracker for the Pathfinder God / Intelligent Virtual Table Top Engine plan.
Updated 11 Nov 2026, ~01:05 CST. Glenn is the only merge authority — nothing
is pushed, committed, or PR'd without his explicit approval.

## Done — landed

- [x] **PR #1 merged** (10 Nov 2026, `e4054b7`): NPC/monster/world builders
      (Ollama `format="json"` + validation, template only as marked fallback),
      shared retry helper, typed endpoints, `openapi.yaml` regenerated.
- [x] **PR #2 solo campaign loop** (merged 10 Nov 2026, merge commit
      `61f0878`; PR head `0822858`): combat state machine (Dying-4 death,
      recovery DC 10+Dying, Wounded), SoloLoop engine, GM tools
      (dice/strike/end turn/build NPC/monster/loot/map), 7 toolchain-reported
      bugs fixed, WS streaming turns, GM Oracle chat screen in the God tab,
      walkable grid + doors/corridors/spawn/exit/3D token positions
      (`7109440`), destructive migration removed from both spoke Room DBs
      (`fd0d6a8`), hybrid semantic recall for campaign sessions (`0227584`).
- [x] Hub tests **407 passed, 0 failed**, Ruff clean (verified locally on
      merged `main`) and GitHub CI run `42951885968` green. Spoke unit tests,
      forced local rerun and `assembleDebug` green; CI Spoke tests/build green.
      On-device evidence: BLU B160V and `atlas_avd` each 7/7 connected tests;
      Moto G later verified 11 Nov 2026 — see item 7 below.
- [x] Council chain pilot pushed (`council-chain-pilot` @ `05989d5`); watcher
      cron live every 30 min; master prompt in `docs/MASTER_PROMPT.md`.
- [x] **Encounter lifecycle foundation** (battle-first, `97e21a2` on
      `encounter-state-machine`): pure transition matrix for all five kinds
      (`battle loot door trap npc`) and five statuses, SQLite-backed
      `encounters` table, partial unique index enforcing one active encounter
      per campaign, battle start/end/victory/defeat wiring, `active_encounter`
      in solo state, list/detail REST routes, regenerated `openapi.yaml`.
      Hub **417 tests pass**, Ruff clean.
- [x] **Encounter ↔ map position links** (battle-first, `890876b` on
      `encounter-state-machine`): `/map/generate` with `campaign_id` links
      hero/monster/npc tokens to active combatants by `(kind, name)` + FIFO
      order; each linked token carries `encounter_id`, `combatant_id`, and its
      grid cell `x/y/z`. The full scene persists on the encounter's `state.map`
      so it survives the request; the GM `generate_map` tool performs the same
      linking. Spoke DTOs parse the new fields. Hub **421 tests pass**, Ruff
      clean; Spoke `assembleDebug` + `testDebugUnitTest` green.
- [x] **Breadcrumb graph foundation** on `encounter-state-machine`:
      `location_edges` (directed road/trail/door/stairs/portal links with
      travel ticks) and immutable `campaign_events` (tick-stamped move, turn,
      and encounter events). `solo_state.world_tick` advances by traversed
      edge ticks; first travel between known locations records a discovered
      trail in both directions. `GET /graph`, `POST /graph/edges`, `POST /move`,
      and `GET /events` expose the trail; encounters now carry `location_id`.
      Hub **429 tests pass**, Ruff clean.
- [x] **Generic encounter lifecycle entry point**: `POST /campaign/{id}/encounters`
      creates `battle`/`loot`/`door`/`trap`/`npc` records and
      `POST /campaign/{id}/encounters/{id}/transition` applies the validated
      matrix, with location attachment and event logging in the same
      transaction.
- [x] **Instant trap hazards** (Muse carve-out): `instant: true` lets a pending
      `trap` transition straight to `resolved`/`failed` without taking the
      active-encounter slot, logged as `hazard_resolved`. Door/NPC/loot GM
      in-turn triggers and automatic turn-action detection landed in Slice 1.
- [x] **Per-kind encounter state and resolvers** (`48c2092`, Phase 1 item 1):
      `door` defaults `{locked,key,barred,dc}`, `trap` `{dc,damage,armed}`,
      `npc` `{npc_id,npc_name,disposition,topic}`, `loot` `{items,claimed}`.
      Door lock/bar/trap checks resolve deterministically in `SoloLoop`; failed
      traps apply damage through `hp_changes`; loot claims validate and upsert
      items; NPC disposition refreshes from the `npcs` row. Instant traps stay
      `pending`-only and never take the active slot.
- [x] **All encounter kinds link to maps** (`978c688`, Phase 1 item 2):
      `door`/`trap` token kinds emit from scene doors/secret trap features and
      are excluded from connectivity; `npc` tokens link to npc combatants + the
      encounter's `npcs` row; `loot` tokens link to `items` through
      `MapToken.item_id`; all use the same REST/GM path and `state.map` persists.
- [x] **Stage scene switch** (`978c688`, Phase 1 item 3): pending → active
      activation (any encounter kind) reuses the location's scene or derives the
      deterministic 12×10 fallback; `state.scene` mirrors it; WS emits an
      `encounter_stage` frame with the full scene. Instant traps emit no stage
      frame and do not take the active slot. `test_encounter_stage.py` 8 passed.
- [x] **Campaign and character `.db` portability** (`6792e88`, Phase 1 item 4):
      standalone `schema.sql` exports carry one campaign (id remapped to 1) and
      a `meta` marker (`schema_version = "1"`); imports validate integrity and
      remap row ids across locations, combatants, encounters, events, solo
      state, and JSON references. `replace_existing=true` replaces the target
      campaign. Character export/import carries hero + party + items/decisions/
      notes, rejects duplicate character names, and skips duplicate item names.
      JSON export/import keeps its existing scope; `.db` is the format that
      round-trips encounters/events. `test_portability.py` 8 passed.
- [x] **LLM gateway / queue** (`32fb981`, Phase 1 item 5): one process-wide
      Ollama gateway with interactive-priority queue, in-flight cap, bounded
      waiting, TTL cache for builder/JSON/rules tasks, and no chat caching.
      `OllamaClient` and the `/health` Ollama probe delegate to it; cancellations
      log and release the slot. `test_llm_gateway.py` 6 passed.
- [x] **Browser 3D encounter stage** (`32fb981`, Phase 1 item 6): `GET /stage`
      serves static HTML + `stage.js`; Three.js pinned at 0.170.0 on jsDelivr;
      `id="three-mount"` renders only the current 5-ft square with wireframe
      blocked cells and breadcrumb trail; 2D canvas draws the `SceneResponse`
      contract; listens for `encounter_stage` on `/stream`. Excluded from
      OpenAPI. `test_stage_page.py` 3 passed.
- [x] **Android P0 real-device LAN run** (Phase 1 item 7 — PASS): B160V,
      serial `7040016025040287`, Android 14, Wi-Fi `10.1.10.186`; laptop Wi-Fi
      `10.1.10.64`; `/health` 200. Debug cleartext allowed; main still locked
      with only `10.0.2.2` exempt. `LanHubSmokeTest` on the real device: 1 test,
      0 failures, 2.531s; XML under
      `spoke_kt/app/build/outputs/androidTest-results/connected/debug/`.
      `app-universal-debug.apk` install + `MainActivity` launch returned
      `Status: ok`; `NetworkSecurityConfigTest` 2/2 green. Full character-forge/
      combat/map UI flow was **not** run.
- [x] **Phase 1 docs refresh** (Phase 1 item 8): this checklist +
      `MASTER_PROMPT.md` refreshed; `FOR_MUSE.md` has the full sweep handoff.
- [x] **Hub full suite 518 passed, 0 failed** on 11 Nov 2026; Ruff clean over
      `app/ tests/`. Native `assembleDebug` green; no CI result checked in the
      sweep.

## Decisions made — locked in

- [x] **2D is the board, 3D is the stage.** Text-based tabletop at the core;
      characters move on the 2D grid; encounters switch to a full 3D stage.
      Not a 3D game you walk through.
- [x] **Deterministic engine, narrating LLM.** Dice, HP, conditions, XP are
      computed in seeded code. The LLM narrates and proposes validated changes.
- [x] **Campaign = a .db file.** Breadcrumb graph: locations, encounters,
      events linked as a graph; the party's trail through it *is* the campaign.
      Editable, modular, portable, sharable.
- [x] **Characters = portable .db files.** Carry a character between campaigns.
- [x] **Event log + world clock are one system.** The clock is the heartbeat
      (game time), the log is the memory. Every event is stamped with its tick;
      world state at any tick is the log replayed to that tick. NPC schedules
      are functions of the clock; movement is an event too.
- [x] **Two map scales.** Town/region scale is a graph (districts, shops,
      locations as nodes joined by roads — travel is an edge, things can happen
      en route). Location scale is the granular grid (5-ft squares, doors,
      corridors) for shops, streets, dungeon floors. A 7–8 square move matters
      on a location grid, not on a town map.
- [x] **3D viewport is optional and local.** Isometric 2D grid for navigation;
      the 3D view is a button that shows the encounter from the character's
      current 5-ft square only — look around from there, nothing further.
      The rest of the world is wireframes along the breadcrumb trail.
      The whole world is never 3D-generated at once.
- [x] **Brain port: cloud brain, local crew.** Log in once in the browser;
      the cloud LLM is the main GM brain; local models do embeddings, retrieval,
      small builders, background prep, offline fallback. Keys live in the hub,
      never in page JS. Local-only GM must work fully with zero cloud.
- [x] **Hub stays the heart.** Python/FastAPI (deterministic engine, builders,
      RAG, Ollama client, SQLite state). htmx face, hub first. Android spoke
      becomes optional, not required.
- [x] **System Pack (IVTT engine).** Rules corpus + entity schemas + mechanics
      config + prompt templates. Load a pack, the engine becomes that RPG's God.
      Licensing lives in the packs, not the engine.
- [x] **Shared world, later.** One campaign .db on the server is the world;
      each party has its own breadcrumb trail through it. Parties can split
      (characters have individual positions; a party is just characters at the
      same node) and multiple parties can share one world and join each other.
      Needs the event log (single timeline, first event wins) and the world
      clock (things happen off-screen).

## Next up — make the local-only GM genuinely great (the priority)

- [x] PR #2 merge decision — Glenn approved; merged and pushed `61f0878`.
- [x] Encounter state machine: types + transitions (battle, loot, door, trap,
      NPC, …). **All five kinds share the generic create/transition routes, and
      pending traps can resolve instantly via the `instant` carve-out.**
- [x] Door/NPC/loot GM triggers: `trigger_door`, `trigger_npc`,
      `trigger_loot`, and `transition_encounter` call `CampaignRepository`
      directly — no per-kind REST routes and no hub self-HTTP. Triggers create
      at the current location, activate when the slot is free, and stay
      `pending` with a note when another encounter is active. Hub **441 tests
      pass**, Ruff clean.
- [x] Automatic turn-action detection in `SoloLoop` (Slice 1): plain turns
      like `I open the door`, `I talk to the merchant`, `I search the chest`,
      and `I disarm the trap` create/advance the encounter through the same
      repository service before normal resolution. One-roll trap attempts roll
      the seeded skill check and resolve via the `instant` carve-out; multi-turn
      disarms activate. `TurnResult` and the WS `encounter` frame surface it;
      `TurnResponse` gains an additive optional `encounter` field (no new
      routes). Hub **472 tests pass**, Ruff clean; no Spoke build run.
- [x] Link encounters to map positions — **all kinds landed at `978c688`**
      (Phase 1 item 2): battle tokens carry encounter/combatant IDs; loot tokens
      carry `item_id`; NPC tokens link to npc combatants + the `npcs` row;
      door/trap tokens emit from the scene and link to their same-location
      encounter; the scene persists on the encounter's `state.map`.
- [x] Breadcrumb graph model in the campaign DB — **foundation landed** (see
      `location_edges`, `campaign_events`, `solo_state.world_tick`, graph/move/
      events routes). Town-scale travel graph and location-scale grids remain
      separate layers.
- [x] Character / campaign .db portability (`6792e88`, Phase 1 item 4).
- [x] LLM gateway / queue (`32fb981`, Phase 1 item 5): one resident model,
      priority queue, concurrency cap, builder/JSON/rules cache, no chat cache.
- [x] 3D encounter stage in the browser (`32fb981`, Phase 1 item 6): static
      htmx-ready page + Three.js 0.170.0 island, viewport from current square.
- [x] Android P0 checks: real-phone LAN cleartext passed on B160V (Phase 1
      item 7); full UI flow still unverified.
- [x] **B5-HTTPS — Release TLS for Pathfinder God Hub** (`feat/https-release-tls`, 11 Nov 2026):
      Mandatory HTTPS for release builds with zero modification to `network_security_config.xml`
      (cleartext remains locked to false, emulator `10.0.2.2` remains the only exception).
      Self-signed 10-year RSA 2048 cert generated on laptop (`hub/scripts/make_hub_cert.py`)
      covering localhost, 127.0.0.1, and detected LAN IPv4s.
      OkHttp SPKI SHA-256 public key pinning in `HubTlsClient.kt` (`HUB_CERT_PIN`).
      Hub uvicorn TLS support (`PFGOD_TLS_ENABLED`, `PFGOD_TLS_CERTFILE`, `PFGOD_TLS_KEYFILE`)
      with fail-fast validation at startup, mDNS `tls=1` advertising, and container healthcheck
      supporting HTTPS and HTTP.
- [x] Blueprint docs updates (`MASTER_PROMPT.md`, this checklist, `FOR_MUSE.md`)
      — Phase 1 item 8.

## Later — after the GM is great

- [ ] htmx face, first playable slice: a turn in the browser over SSE.
- [ ] Frozen installable app: PyInstaller-style + portable zip, then a real
      Windows installer. Ollama as prerequisite/bundled. Rules DB shipped or
      downloaded on first run.
- [ ] Brain port build-out: cloud login, hub proxies cloud calls, routing /
      cost / privacy controls (what may leave the machine).
- [ ] System Packs: first pack is PF2e (extract what's hardcoded today);
      second pack proves the abstraction.
- [ ] Shared world: event log, world clock, split parties, multi-party
      joining, GM arbitration of conflicts.
- [ ] Federation: private campaigns on your laptop, public server with a
      public GM. Needs auth / sessions / multi-tenancy design (hub is
      single-user today).
- [ ] 3D dungeon-world RTS phase (Godot as the later vehicle).

## Held thoughts

- [ ] The world clock tick — Glenn has an idea, holding it for the next round.
- [ ] Cloud LLM choice — deferred until the local GM is great.

## Open questions

- [x] Which encounter type first — **battle first**: the combat loop already
      exists, so the encounter lifecycle can be proven without inventing the
      breadcrumb graph yet. Door/trap follows once the graph model lands.
- [ ] Map scale numbers — grid sizes to tune in play (location grids
      traversable in a few minutes; town graph carries the bigness).
