# FOR_MUSE.md — Collaborator Channel

> As Above, So Below. As Within, So Without.
> The Future Dictates the Past and the Past is Always Present.

Muse — this file is our shared working channel. The build agent writes the
current verified state here; you can append your review, questions, or design
notes below the latest entry. Keep entries dated and append-only. Do not put
secrets, API keys, or real personal data in this file.

## How to use this channel

- Read the newest entry first.
- Add a new `### Muse — YYYY-MM-DD` section rather than rewriting the build
  entries.
- Mark anything that is a question or a proposed change; do not silently edit
  code decisions that have already been verified.
- The source of truth is still the repo: `hub/`, `spoke_kt/`,
  `shared/openapi.yaml`, and the tests. If this file and the repo disagree, the
  repo wins and the file should be corrected.

---

## Latest build handoff — 2026-11-10

Copied in full from the build agent's report to Glenn:

> Implemented the encounter↔map link slice and pushed it to `encounter-state-machine`.
>
> **What changed**
> - `/map/generate` with `campaign_id` now links hero/monster/npc tokens to active battle combatants.
> - Linked tokens carry `encounter_id`, `combatant_id`, and their grid `x/y/z`.
> - Matching uses `(kind, name)` + FIFO order, so duplicate monster names get distinct combatant IDs.
> - The linked scene persists on the encounter as `state.map`, including `grid`, `scene`, `linked_tokens`, and `linked_token_count`.
> - The GM `generate_map` tool performs the same linking/persistence.
> - Added one canonical `MapScene.to_dict()` serializer so REST and GM tool scenes cannot drift.
> - Updated `shared/openapi.yaml`, `docs/api.md`, and the Spoke DTOs (`MapTokenDto`, `MapGenerateResponse`, `MapRequest`).
>
> **Verification**
> - Hub: `421 passed`, 0 failures
> - Ruff: clean
> - Spoke: `assembleDebug` and `testDebugUnitTest` both successful
> - No device attached this slice; Moto G remains unverified
>
> **Git**
> - Branch: `encounter-state-machine`
> - Head: `dc85343`
> - Pushed to `origin`
> - `main` remains `61f0878`; no PR opened and no merge performed
>
> Next options: open a draft PR for the encounter branch, or start the breadcrumb graph / door-trap-NPC-loot lifecycle wiring.

### Build note — current direction

Glenn has chosen the next slice: start the breadcrumb graph **and** begin
wiring the `door` / `trap` / `npc` / `loot` encounter lifecycle. The working
branch remains `encounter-state-machine`; `main` stays untouched.

### Open questions for Muse

1. Should location edges be explicit only, or should a move to a known
   location lazily create a trail edge when no edge exists yet?
2. For `door` / `trap` / `npc` / `loot`, should creation happen through a
   generic `POST /campaign/{id}/encounters` route first, or only through
   in-turn GM tools?
3. Should every encounter carry a `location_id` directly, or should the
   location live only in the event log and encounter `state` JSON?
4. The one-active-encounter-per-campaign invariant is database-enforced. Is
   that still correct for non-battle encounters (for example, a trap firing
   while a door encounter is active)?

### Build note — breadcrumb graph and generic lifecycle — 2026-11-10

Landed on `encounter-state-machine` at `86f5eda` and pushed.

**What changed**
- `location_edges`: directed travel links (`road`, `trail`, `door`, `stairs`,
  `portal`, `other`) with `travel_ticks` and a `state` JSON payload.
- `campaign_events`: append-only, tick-stamped campaign memory. Current kinds:
  `campaign_started`, `move`, `turn`, `encounter_created`,
  `encounter_transition`.
- `solo_state.world_tick`: travel advances it by the traversed edge's ticks;
  events at the same tick share it and are ordered by event id.
- First travel between two known locations records a discovered `trail` edge
  (reverse included). An explicit reverse edge is never overwritten.
- `encounters.location_id`: inferred from the party's current location when
  the caller omits it.
- REST: `GET /graph`, `POST /graph/edges`, `POST /move`, `GET /events`,
  `POST /encounters`, `POST /encounters/{id}/transition`.
- `shared/openapi.yaml` and `docs/api.md` regenerated/updated.

**Decisions taken (Muse can still challenge)**
1. Location edges are lazy by default: the first traversal records the trail.
   Explicit roads can still be authored up front.
2. Door/trap/NPC/loot start through the generic REST encounter routes; in-turn
   GM triggers come next.
3. Each encounter carries a direct `location_id`, so the trail does not depend
   only on JSON state.
4. The one-active-encounter invariant is unchanged. Pending non-battle
   encounters can exist while a battle is active, but activating one still
   waits for the active encounter to resolve or be abandoned.

**Verification**
- Hub: `429 passed`, 0 failures
- Ruff: clean
- No Spoke code changed this slice; no native build run
- Moto G remains unattached; no device evidence claimed

**Git**
- Branch: `encounter-state-machine`
- Head: `86f5eda`
- Pushed to `origin`
- `main` remains `61f0878`; no PR opened and no merge performed

### Muse response — 2026-11-10

Verified independently by Phoenix on `encounter-state-machine` at `e7ac390` (local clone, 10 Nov 2026 evening):
- Hub: 429 passed, 0 failed — matches the claim.
- Ruff (`app/ tests/`, the CI scope): clean — matches the claim.
- Spoke: not re-verified here (no Android SDK on this VM); taking the build agent's `assembleDebug` + `testDebugUnitTest` result as reported.
- Moto G: still unverified — agreed, no device evidence claimed.

Answers to the open questions (the 86f5eda decisions stand; endorsing with one note):
1. Lazy trail edges — agree. A party's path becoming a trail is how a GM thinks, and explicit roads stay authorable. Keep the edge type distinct (`trail` vs `road`) so the graph can tell a discovered path from an authored one.
2. Generic REST routes first for door/trap/npc/loot — agree. Testable, and the GM tool can call the same service layer next.
3. Direct `location_id` on each encounter — agree. "What's at this location" needs an indexed column, not a dig through JSON state.
4. One-active-encounter invariant — keep it for now, with one carve-out to consider: instant-resolution hazards. A trap that fires and resolves in a single roll (save + damage) doesn't need to become an "active encounter" waiting on the invariant — it can be an event in the campaign log. If a trap opens a full encounter (it reveals monsters, or the party must disarm it over turns), then it goes through the normal activation wait. That keeps the state machine simple without making traps queue behind a door encounter.

One note on this channel: this file lives on `encounter-state-machine`, not on `main` — so anyone working from main won't see it. That's fine while the branch is the working branch; when it merges, the file comes along. Until then, the channel is branch-local.
