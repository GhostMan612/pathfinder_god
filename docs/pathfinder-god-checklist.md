# Pathfinder God — Master Checklist

Living tracker for the Pathfinder God / Intelligent Virtual Table Top Engine plan.
Updated 10 Nov 2026, ~22:00 CST. Glenn is the only merge authority — nothing
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
      Moto G still unverified (not attached).
- [x] Council chain pilot pushed (`council-chain-pilot` @ `05989d5`); watcher
      cron live every 30 min; master prompt in `docs/MASTER_PROMPT.md`.
- [x] **Encounter lifecycle foundation** (battle-first, `97e21a2` on
      `encounter-state-machine`): pure transition matrix for all five kinds
      (`battle loot door trap npc`) and five statuses, SQLite-backed
      `encounters` table, partial unique index enforcing one active encounter
      per campaign, battle start/end/victory/defeat wiring, `active_encounter`
      in solo state, list/detail REST routes, regenerated `openapi.yaml`.
      Hub **417 tests pass**, Ruff clean.

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
      NPC, …). **Battle-first slice landed on `encounter-state-machine` at
      `97e21a2`; the remaining kinds reuse the same lifecycle and are next
      wired as their content lands.**
- [ ] Link encounters to map positions — next slice; start with battle tokens
      carrying encounter/combatant IDs and map cell coordinates.
- [ ] Breadcrumb graph model in the campaign DB.
- [ ] Character / campaign .db portability (export, import, carry between games).
- [ ] LLM gateway / queue: one resident model, priority queue (turns first,
      background second), concurrency cap, prompt/result caching.
- [ ] 3D encounter stage in the browser client (htmx + small Three.js island,
      viewport from the current square).
- [ ] Android P0 checks: real-phone LAN cleartext tethering on a real device
      (LAN smoke test landed in `fd0d6a8`, on-device run still unconfirmed).
- [ ] Blueprint docs updates (Task 6 of the master prompt).

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
