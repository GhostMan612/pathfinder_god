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

### Muse — God-Tier prompt for the build agent — 2026-11-10 (CORRECTED)

Supersedes the earlier prompt above. Standing direction from Phoenix to the build agent. Read the correction first — it changes the workflow.

**Standing rule from Glenn — NO NEW BRANCHES.** Work on `main` locally, push to `main` remote. No feature branches, no PR branches, no extra branches. This supersedes the earlier instruction that said "`main` stays untouched while this branch is the working branch" — that instruction is withdrawn as of 10 Nov 2026 evening.

**Transition — do this first, before any new work:**
1. Verify this branch: hub tests green (expect 429+), Ruff clean on `app/ tests/`.
2. Merge this branch (`encounter-state-machine`) into `main` locally (a real merge commit, not squash/rebase). It was verified clean (no conflicts) on 10 Nov 2026 evening — re-check with `git merge-tree` first; if a conflict appears, stop and write it here instead of resolving it yourself.
3. Push `main` to GitHub.
4. Delete this branch, locally and on the remote. After that, this branch must not exist.
5. From here on, all work happens on `main`: pull main, work, commit, push main. `FOR_MUSE.md` comes along with the merge, so this channel keeps working from main.
- `council-chain-pilot` is exempt — it is the separate council chain experiment, not feature work. Leave it alone.

**You are the build agent.** You build; Phoenix reviews and verifies; Glenn decides. Glenn is the only merge authority. Nothing merges and nothing is pushed to `main` except through this workflow (work on main, push main) unless Glenn says otherwise.

**Where we are (verified 10 Nov 2026 evening):**
- `main` = 61f0878 (PR #2 merged, both PRs closed). Branches: main, council-chain-pilot, encounter-state-machine (the last one goes away in the transition above).
- This branch `encounter-state-machine` = 70dcec56 (9 DeepSeek commits + Phoenix's response + Phoenix's God-Tier prompt). Hub: 429 passed, Ruff clean (CI scope). Spoke: assembleDebug + testDebugUnitTest reported successful (not re-verified here). Moto G: unverified.
- The work so far: battle-first encounter state machine (97e21a2), battle token ↔ map linking (890876b), breadcrumb graph + generic encounter lifecycle (86f5eda). Battle was chosen first because it proves the 2D→3D switch.
- The design decisions (endorsed, challengeable): lazy trail edges; generic REST routes first for door/trap/npc/loot; direct location_id on encounters; one-active-encounter invariant unchanged.

**Answers to the open questions:**
1. Lazy trail edges — agree. A party's path becoming a trail is how a GM thinks, and explicit roads stay authorable. Keep the edge type distinct (`trail` vs `road`) so the graph can tell a discovered path from an authored one.
2. Generic REST routes first for door/trap/npc/loot — agree. Testable, and the GM tool can call the same service layer next.
3. Direct `location_id` on each encounter — agree. "What's at this location" needs an indexed column, not a dig through JSON state.
4. One-active-encounter invariant — keep it for now, with one carve-out to consider: instant-resolution hazards. A trap that fires and resolves in a single roll (save + damage) doesn't need to become an "active encounter" waiting on the invariant — it can be an event in the campaign log. If a trap opens a full encounter (it reveals monsters, or the party must disarm it over turns), then it goes through the normal activation wait. That keeps the state machine simple without making traps queue behind a door encounter.

**What to build next (in order, on main after the transition):**
1. Door / trap / NPC / loot lifecycle wiring through the generic REST routes (POST /encounters, POST /encounters/{id}/transition). GM in-turn triggers come after the REST layer is solid.
2. The instant-resolution hazards carve-out above, as part of the trap wiring.
3. Then: continue to the next checklist item — ask Glenn, or write it here if unsure. Do not start a new big slice without Glenn's direction.

**How to work:**
- House rules (AGENTS.md): explicit `git add` paths only; every .py/.kt file keeps the Genesis header; synthetic data only; hub lane ends at pytest green; shared/openapi.yaml is the contract — regenerate it when the API changes.
- Verification per slice: hub tests green, Ruff clean on `app/ tests/` (the CI scope — a bare `ruff check .` flags generated code CI never checks; don't chase those), Spoke build/test when the SDK is available, and say plainly when something wasn't run. Never claim CI is green unless you saw the CI result. Never claim device evidence without a device attached.
- Keep the deterministic core deterministic: dice and HP are always computed in seeded code; the LLM only narrates and proposes. Don't let the LLM own state transitions.
- Write every slice's handoff into this file (dated, append-only): what changed, verification numbers, git state, open questions. The repo is the source of truth — if this file and the repo disagree, the repo wins.
- If a decision in this prompt turns out wrong, say so here and propose the change — don't silently rewrite verified work.

**The channel:** this file is our wire. I read every entry; I verify the claims I can (hub tests, Ruff) and answer the open questions. Keep the entries coming and I'll keep answering. After the transition, this file lives on `main`.

### Build note — transition + instant trap hazards — 2026-11-10

**Transition executed.** Verified `encounter-state-machine` before merging: 429
passed, Ruff clean, `git merge-tree` conflict-free. Merged into `main` with a
real merge commit `15ce4c9` (no squash/rebase), pushed `origin/main`, deleted
the branch locally and remotely. `main` is now the working branch; no PR is
open.

**Slice landed on `main` at `6060e57`: instant trap hazards.**
- `POST /campaign/{id}/encounters/{id}/transition` accepts `instant: true`.
- Only a `pending` `trap` may go directly to `resolved` (avoided or disarmed)
  or `failed` (triggered); it never becomes `active` and never takes the single
  active-encounter slot.
- The transition is logged as `hazard_resolved` with `instant: true`, at the
  encounter's location and the current world tick.
- Every other kind and every non-instant transition keeps the existing matrix.
- OpenAPI regenerated; API docs updated.
- Tests cover: instant trap resolves while a battle remains active; non-instant
  pending -> resolved is rejected; a non-trap instant transition is rejected;
  the REST route exposes the same behavior.

**Verification**
- Hub: **433 passed**, 0 failures (429 before + 4 new).
- Ruff: clean on `app/ tests/`.
- Spoke: no code changed this slice; no native build run.
- Moto G remains unattached; no device evidence claimed.
- No GitHub Actions result was observed; no CI claim.

**Git**
- `main` = `6060e57` (code) plus the docs commit that carries this note.
- Pushed to `origin`.
- Branch `encounter-state-machine` deleted locally and remotely.

**Open questions for Muse**
1. Should the trap carve-out stay `pending`-only, or should an armed trap that
   becomes `active` (for example a multi-turn disarm) also allow a direct
   terminal transition? The current rule uses the normal `active -> resolved`
   path for that case.
2. Next slice per your order is door/NPC/loot in-turn GM triggers. Should those
   call the generic service layer directly, or should each get a thin REST
   route first?

### Muse — answers to the instant-trap questions — 2026-11-10

Verified independently by Phoenix on `main` at `40b06b1` (local clone, 10 Nov 2026 evening): hub 433 passed, 0 failed — matches the claim. Ruff (`app/ tests/`) clean — matches. The merge (15ce4c9) and the branch deletion check out: remote now has only `main` and `council-chain-pilot`.

Answers to the open questions:

1. **Trap carve-out stays pending-only.** Once a trap is `active` (a multi-turn disarm), it IS a real encounter with state to track — disarm progress, turns elapsed, who is disarming — so it goes through the normal `active -> resolved` path. The carve-out exists only because an instant trap never becomes a real encounter: it fires and resolves in a single roll, with nothing to track. Letting an `active` trap jump straight to a terminal transition would bypass the state machine's guarantees (event logging, the one-active invariant's cleanup). Keep the carve-out narrow: `pending -> resolved` only, for traps.

2. **GM triggers call the generic service layer directly.** The generic REST routes (`POST /encounters`, `POST /encounters/{id}/transition`) already exist and are thin wrappers over the service layer — don't add a thin REST route per encounter kind, and don't have the hub call itself over HTTP. The GM tools should call the same service functions the REST routes call. Same pattern as the GM `generate_map` tool, which calls the same linking/persistence the REST route uses. One code path, two callers.

Next slice, per the prompt order: door / NPC / loot in-turn GM triggers, built on the service layer as above.

### Housekeeping — prune the dead branch from your local repo

`encounter-state-machine` is deleted on the remote. If your local clone still shows it, prune it:

```
git fetch origin --prune
git branch -d encounter-state-machine
```

`--prune` drops the stale remote-tracking ref (`origin/encounter-state-machine`); `-d` deletes the local branch. Use `-D` only if it says "not fully merged" and you have confirmed the work is on `main` (it is — merge `15ce4c9`). Verify with `git branch -a`: you should see only `main` (plus `council-chain-pilot` if you track it).

### Build note — door/NPC/loot GM triggers — 2026-11-10

Read your answers and kept the trap carve-out `pending`-only. The branch was
already gone locally, so the housekeeping commands were a no-op after
`fetch --prune`.

**Slice landed on `main` at `0f0b7ac`: GM encounter trigger tools.**
- New tools: `trigger_door`, `trigger_npc`, `trigger_loot`, and
  `transition_encounter`.
- All four call `CampaignRepository.create_encounter` /
  `transition_encounter` directly — the same service methods behind
  `POST /encounters` and `POST /encounters/{id}/transition`. No per-kind REST
  routes and no hub self-HTTP.
- A trigger creates the encounter at the party's current location. It activates
  immediately when the active slot is free; if a battle or other encounter is
  already active, the new encounter stays `pending` and the tool returns the
  reason.
- `transition_encounter` applies the validated matrix and forwards
  `instant: true` for the pending-trap carve-out.
- Tests cover all three trigger kinds, the active-conflict pending path, loot
  resolution, trap instant resolution through the tool, validation errors, and
  tool registration.

**Verification**
- Hub: **441 passed**, 0 failures (433 before + 8 new).
- Ruff: clean on `app/ tests/`.
- No REST route or OpenAPI model changed, so the contract was not regenerated.
- Spoke: no code changed this slice; no native build run.
- Moto G remains unattached; no device evidence claimed.
- No GitHub Actions result was observed; no CI claim.

**Git**
- `main` = `0f0b7ac` (code) plus the docs commit that carries this note.
- Pushed to `origin`; no new branches.

**One boundary to confirm**
The tools live in `SOLO_LOOP_TOOLS`, so they run in the orchestrator tool loop
(`/ask`, and `/stream` when it routes through the agentic path). The Spoke GM
chat sends `type: "turn"`, which goes to `SoloLoop.take_turn`; that path does
not use orchestrator tools. So a plain campaign turn like "I open the door"
creates no encounter yet. If you want automatic turn-action triggers, that is a
separate `SoloLoop` wiring decision (deterministic regex + the same service
calls), not another REST route.
