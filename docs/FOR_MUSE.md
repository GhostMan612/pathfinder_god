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

### Muse response

_Reserved for Muse._
