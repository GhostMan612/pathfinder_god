# Hub API reference

Source of truth: [`../shared/openapi.yaml`](../shared/openapi.yaml) (v0.1.0).
Interactive playground (hub running): `http://localhost:8000/docs`.

## REST

| Method | Path | Body / Query | Returns |
|---|---|---|---|
| GET | `/health` | — | `{status, version, ollama_model, databases_found[]}` |
| GET | `/ready`, `/health/detailed`, `/version`, `/metrics`, `/metrics/json` | — | Readiness probe (db + ollama checks), detailed health, version, Prometheus text / JSON metrics |
| POST | `/ask` | `{query, edition=both, mode?, history=[[role,text]…]}` | `{answer, backend, mode, edition, sources[]}` |
| POST | `/generate/{kind}` | `{prompt, edition}` · kind ∈ `npc monster boss map campaign encounter` | Same as `/ask` (mode forced) |
| POST | `/generate/character` | `{prompt}` | `{valid, character?, errors[]}` — LLM + Rules Lawyer validated |
| POST | `/generate/loot` | `{prompt}` | `{valid, item?, craft_dc?, errors[]}` — rune/price/dice validated |
| POST | `/combat/resolve-strike` | `{attack_roll, target_ac, damage_roll, target_hp, target_temp_hp?}` | `{outcome, damage_dealt, new_hp, new_temp_hp, notes}` |
| POST | `/combat/end-turn` | `{conditions[], current_hp?}` | `{conditions[], notes, damage_taken}` — persistent damage + flat checks |
| POST | `/encounter/generate` | `{party_level, party_size, threat, theme}` | `{target_xp, total_xp, monsters[]}` — XP-budget exact |
| POST | `/map/generate` | `{prompt, grid_enabled=true, campaign_id?}` | `{valid, gm_base64_png, player_base64_png, width, height, rooms[], secret_features[], scene, encounter_id?}` — active-battle maps carry linked tokens |
| GET | `/rules/search` | `?q=&edition=both&limit=5` | `{query, edition, results: RuleHit[]}` — exact-name first |
| GET | `/campaign?campaign_id=` | — | `{party[], notes[]}` |
| POST | `/campaign/note` | `{prompt, response}` | Updated state (+ background continuity) |
| POST | `/campaign/reset` | — | Fresh state |
| GET | `/campaign/export?campaign_id=` | — | Full dump (campaigns, sessions, npcs, locations, items, quests, decisions, party) |
| POST | `/campaign/import` | Export payload | Merged state (incl. sessions, notes, decisions) |
| POST | `/campaign/summarize-session` | `{events[], campaign_name}` | `{summary, event_count}` — chronicler journal entry |
| GET/POST | `/campaign/npcs`, `/campaign/party` | NPC/member JSON | IDs + names |
| GET | `/campaign/backup` | - | Full export as download |
| POST | `/campaign/create` | `{name, edition=2e, premise?, hero_prompt?}` | `{campaign_id, opening_narration, ...}` |
| POST | `/campaign/{campaign_id}/turn` | `{action, actor=player, seed?}` | `TurnResponse` (dice, HP, conditions, narration, choices) |
| GET | `/campaign/{campaign_id}/state` | - | Solo state (phase, round, world tick, active encounter, combatants, quests, recent turns, chronicle) |
| GET | `/campaign/{campaign_id}/graph` | - | `{campaign_id, world_tick, current_location_id, nodes[], edges[], event_count}` |
| POST | `/campaign/{campaign_id}/graph/edges` | `{from_location_id, to_location_id, kind=trail, label?, travel_ticks=1, state?, bidirectional=false}` | One travel edge (plus the reverse when bidirectional) |
| POST | `/campaign/{campaign_id}/move` | `{location_id, summary?}` | `{location, tick, edge, event}`; advances the world clock |
| GET | `/campaign/{campaign_id}/events` | `?limit=&since_tick=&location_id=&encounter_id=&kind=` | Breadcrumb trail, oldest event first |
| GET | `/campaign/{campaign_id}/encounters` | - | `{campaign_id, encounters[]}` newest first |
| GET | `/campaign/{campaign_id}/encounters/{encounter_id}` | - | One encounter lifecycle record |
| POST | `/campaign/{campaign_id}/encounters` | `{kind, status=pending, summary?, state?, seed?, location_id?}` | Create any encounter kind |
| POST | `/campaign/{campaign_id}/encounters/{encounter_id}/transition` | `{status, summary?, state?}` | One validated lifecycle transition |
| POST | `/campaign/{campaign_id}/combat/start` | `{monster_names?, theme?, threat, party_level, seed?}` | Combat state + `encounter_id` |
| POST | `/campaign/{campaign_id}/combat/end-turn`, `/combat/end` | - | Combat state |
| POST | `/rules/fetch` | `{q, edition}` | Scrape one missing term into the DB permanently (1e live; else 404 + queued) |
| POST | `/rules/missed` | `{queries: [{q, edition}]}` | Queue offline misses for backfill |
| GET | `/rules/missed?limit=` | — | Queued misses (backfill feed) |

`RuleHit = {name, content, system, category, source_book}`.
`backend` is `ollama` or `raw-excerpts` (LLM down — excerpts still answer).
`edition` accepts `1e 2e both` (aliases like `pf2e` normalized server-side).

### Breadcrumb graph and world clock

Locations are graph nodes and `location_edges` are directed travel links
(`road`, `trail`, `door`, `stairs`, `portal`, `other`). Every campaign starts
with no edges. On the first traversal between two known locations the hub
records a discovered `trail` edge (and its reverse), so the party's route
accumulates as the campaign does; explicit roads can be created up front with
`POST /graph/edges`.

`GET /graph` returns the nodes, edges, current location, `world_tick`, and the
number of events. `POST /move` requires a known `location_id`, advances the
clock by the traversed edge's `travel_ticks` (at least 1), moves
`solo_state.current_location_id`, and appends a `move` event.

`campaign_events` is the campaign memory: immutable rows stamped with `tick`
and optionally `location_id` and `encounter_id`. `GET /events` returns the most
recent `limit` events oldest-first, so a client can replay the trail in order.
`tick = 0` is campaign creation; travel advances it, while encounters and turns
are stamped at the current tick.

### Encounter lifecycle

An encounter is campaign-scoped state: `kind` ∈ `battle loot door trap npc`,
`status` ∈ `pending active resolved failed abandoned`. Only one encounter per
campaign may be `active` (database-enforced). Legal transitions:

```
pending -> active | abandoned
active  -> resolved | failed | abandoned
resolved | failed | abandoned -> terminal
```

Every encounter carries a `location_id`, inferred from the party's current
location when the caller omits it. `POST /campaign/{id}/encounters` creates any
kind (the door/trap/NPC/loot lifecycle entry point), and
`POST /campaign/{id}/encounters/{encounter_id}/transition` applies one validated
transition. Both append `encounter_created` / `encounter_transition` events to
the breadcrumb trail in the same transaction.

`instant: true` is the trap carve-out. A pending trap may transition directly
to `resolved` (avoided or disarmed) or `failed` (triggered) without becoming
`active`, so a one-roll hazard never waits behind a battle or door encounter.
That transition is logged as a `hazard_resolved` event with `instant: true`.
The carve-out is trap-only; other kinds still follow the normal matrix.

`POST /combat/start` creates a `battle` encounter in `pending`, activates it
once the roster is built, and returns its `encounter_id`. `POST /combat/end`
resolves it; wiping out the last active monster resolves it as `resolved`, while
losing the last hero resolves it as `failed`. A new battle abandons the previous
active encounter. `GET /state` includes the current `active_encounter`.

#### GM encounter tools

The GM tool loop exposes `trigger_door`, `trigger_npc`, `trigger_loot`, and
`transition_encounter`. They call the same `CampaignRepository` methods as the
generic REST routes — there are no per-kind REST routes and the hub never calls
itself over HTTP. A trigger creates the encounter at the party's current
location and activates it when the active slot is free; if another encounter
is already active, it stays `pending` and the tool returns a note. The
transition tool applies the validated matrix, including `instant: true` for a
pending trap.

### Encounter map links

When `/map/generate` is called with `campaign_id` and that campaign has an
active `battle`, the generator links hero/monster/npc tokens to the active
combatants by `(kind, name)` and FIFO order. Each linked token carries
`encounter_id` and `combatant_id` alongside its grid cell `x`/`y`/`z`; the
response also exposes the top-level `encounter_id`. Unmatched map dressing
(loot, extra NPCs) keeps `combatant_id = null`.

The linked scene is persisted on the encounter's `state.map` so reopening the
encounter does not regenerate it:

```
state.map = {
  encounter_id,
  grid: {w, h, tile_m},
  scene: Scene,                 # full scene, tokens include the IDs
  linked_token_count,
  linked_tokens: [Token]        # only tokens with a combatant_id
}
```

The GM `generate_map` tool performs the same linking and persistence when used
during an active battle. Other encounter kinds do not claim map tokens yet.

## WebSocket `/stream` (alias of `/ask/stream`)

Send one JSON frame: `{query, edition, mode?, history}`. Receive frames:

```
{type: "start", backend, model} → {type: "chunk", text}* →
{type: "end", sources[]} | {type: "error", message}
```

The Spoke emits its own `retrying` frame across reconnects (server regenerates
the answer; clients should clear partial text). 15s ping keeps Android Doze away.

### Solo turn frames (same `/stream` socket)

A solo campaign turn uses the same WebSocket instead of a separate
`/campaign/ws/{id}` route. Send one turn frame:

```json
{"campaign_id": 1, "action": "I search the altar", "actor": "player", "seed": 123}
```

`type: "turn"` is accepted as a marker, but `campaign_id` + `action` are the
required fields. `actor` defaults to `"player"`; `seed` is optional and makes
resolution reproducible.

Event order and shapes:

```
{type: "start", campaign_id, turn_num, phase, round}
{type: "dice", dice_rolls[]}
{type: "hp", hp_changes[]}
{type: "conditions", conditions[]}
{type: "narration", text}*          # sentence chunks
{type: "end", result: TurnResult}
| {type: "error", message}
```

The resolver, RNG, and persisted state are identical to
`POST /campaign/{campaign_id}/turn`; the socket is an observer sink, so a dropped
client does not abort or partially apply the turn. When an API key is configured,
turn frames require `X-API-Key`, `Authorization: Bearer ...`, or `?api_key=...`.
Ask frames remain backward-compatible with keyless local installs.
`shared/openapi.yaml` documents the REST contract only; this section is the
authoritative WebSocket contract.

## mDNS discovery (out-of-band, no auth)

Service `_pathfindergod._tcp.local`, port 8000, TXT `version / model / app`.
Browse → resolve A record → `GET /health` to verify → connect. Fallbacks:
hotspot gateway `192.168.137.1:8000`, emulator `10.0.2.2:8000`, last-known URL.
