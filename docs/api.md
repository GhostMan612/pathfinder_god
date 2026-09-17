# Hub API reference

Source of truth: [`../shared/openapi.yaml`](../shared/openapi.yaml) (v0.1.0).
Interactive playground (hub running): `http://localhost:8000/docs`.

## REST

| Method | Path | Body / Query | Returns |
|---|---|---|---|
| GET | `/health` | — | `{status, version, ollama_model, databases_found[]}` |
| POST | `/ask` | `{query, edition=both, mode?, history=[[role,text]…]}` | `{answer, backend, mode, edition, sources[]}` |
| POST | `/generate/{kind}` | `{prompt, edition}` · kind ∈ `npc monster boss map campaign encounter` | Same as `/ask` (mode forced) |
| POST | `/generate/character` | `{prompt}` | `{valid, character?, errors[]}` — LLM + Rules Lawyer validated |
| POST | `/generate/loot` | `{prompt}` | `{valid, item?, craft_dc?, errors[]}` — rune/price/dice validated |
| POST | `/combat/resolve-strike` | `{attack_roll, target_ac, damage_roll, target_hp, target_temp_hp?}` | `{outcome, damage_dealt, new_hp, new_temp_hp, notes}` |
| POST | `/combat/end-turn` | `{conditions[], current_hp?}` | `{conditions[], notes, damage_taken}` — persistent damage + flat checks |
| POST | `/encounter/generate` | `{party_level, party_size, threat, theme}` | `{target_xp, total_xp, monsters[]}` — XP-budget exact |
| POST | `/map/generate` | `{prompt, grid_enabled=true}` | `{valid, gm_base64_png, player_base64_png, width, height, rooms[], secret_features[]}` |
| GET | `/rules/search` | `?q=&edition=both&limit=5` | `{query, edition, results: RuleHit[]}` — exact-name first |
| GET | `/campaign?campaign_id=` | — | `{party[], notes[]}` |
| POST | `/campaign/note` | `{prompt, response}` | Updated state (+ background continuity) |
| POST | `/campaign/reset` | — | Fresh state |
| GET | `/campaign/export?campaign_id=` | — | Full dump (campaigns, sessions, npcs, locations, items, quests, decisions, party) |
| POST | `/campaign/import` | Export payload | Merged state (incl. sessions, notes, decisions) |
| POST | `/campaign/summarize-session` | `{events[], campaign_name}` | `{summary, event_count}` — chronicler journal entry |
| GET/POST | `/campaign/npcs`, `/campaign/party` | NPC/member JSON | IDs + names |
| GET | `/campaign/backup` | — | Full export as download |
| POST | `/rules/fetch` | `{q, edition}` | Scrape one missing term into the DB permanently (1e live; else 404 + queued) |
| POST | `/rules/missed` | `{queries: [{q, edition}]}` | Queue offline misses for backfill |
| GET | `/rules/missed?limit=` | — | Queued misses (backfill feed) |

`RuleHit = {name, content, system, category, source_book}`.
`backend` is `ollama` or `raw-excerpts` (LLM down — excerpts still answer).
`edition` accepts `1e 2e both` (aliases like `pf2e` normalized server-side).

## WebSocket `/stream` (alias of `/ask/stream`)

Send one JSON frame: `{query, edition, mode?, history}`. Receive frames:

```
{type: "start", backend, model} → {type: "chunk", text}* →
{type: "end", sources[]} | {type: "error", message}
```

The Spoke emits its own `retrying` frame across reconnects (server regenerates
the answer; clients should clear partial text). 15s ping keeps Android Doze away.

## mDNS discovery (out-of-band, no auth)

Service `_pathfindergod._tcp.local`, port 8000, TXT `version / model / app`.
Browse → resolve A record → `GET /health` to verify → connect. Fallbacks:
hotspot gateway `192.168.137.1:8000`, emulator `10.0.2.2:8000`, last-known URL.
