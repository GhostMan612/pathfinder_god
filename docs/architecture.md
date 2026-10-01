<!-- As Above, So Below. As Within, So Without. The Future Dictates the Past and the Past is Always Present. -->
# Architecture

## The shape

```
        ┌─────────────────────────────────────────┐
        │  HUB — laptop (Python + FastAPI)         │
        │                                          │
        │   ┌────────┐   ┌─────────┐   ┌────────┐  │
        │   │  RAG   │◀──│  God    │──▶│  LLM   │  │
        │   │ FTS5   │   │ service │   │ router │  │
        │   │44k rows│   └─────────┘   └───┬────┘  │
        │   │ 57 MB  │                     │       │
        │   └────────┘        ┌────────────┴─────┐ │
        │                     │ 1. Ollama (local) │ │
        │                     │ 2. raw excerpts   │ │
        │                     └───────────────────┘ │
        └───────────────▲──────────────────────────┘
                        │  HTTP (REST) + WebSocket (/stream)
                        │  mDNS announce (hub side) · LAN now · Tailscale later
        ┌───────────────┴──────────────────────────┐
        │  SPOKE — phone (native Kotlin / Android)  │
        │  dice · sheet · ladder · vaults · oracle  │
        └───────────────────────────────────────────┘
```

## Why two languages (and why that's correct here)

The hub does all the heavy lifting — LLM inference and retrieval over 44,620 rules — so the
phone can stay a thin, fast client. Because of that split, the two halves share almost no
logic: only a small JSON contract ([`../shared/openapi.yaml`](../shared/openapi.yaml)) and the
dice math. That makes "one language for both" a cost with no benefit, so each side uses the
best tool:

- **Python** on the hub — reuses the existing RAG/agent code and has the best local-LLM
  ecosystem.
- **Kotlin** on the phone — Jetpack Compose in a single `:app` module, Room for
  vaults, Retrofit/OkHttp for the hub contract. One first-party native render surface:
  the Filament dice pit (`ui/pit/FilamentPit.kt`). No game engine, no Unity/Godot, and
  no NDK/CMake in the lane.

The hub package holds the RAG, the 2e→1e edition fallback, and the 2-tier LLM
fallback (Ollama → raw excerpts). The two halves share almost no logic beyond that.

## Request flow (a GM question)

1. Phone opens an OkHttp WebSocket to `/stream` and sends `{query, edition, mode?, history}`; `HubForegroundService` owns the socket and the backoff reconnect, so a Doze/Wi-Fi roam drop no longer costs the stream.
2. Hub retrieves the top rule snippets from the FTS5 DB (2e first, then 1e).
3. Hub builds a mode-specific prompt (mode templates + `[Source - Rule]` ≤3 sentences ≤300 chars citation fidelity) with that rule context.
4. Hub routes the prompt through the fallback chain:
   - `qwen2.5:3b` path: 3-turn ReAct loop (`chat` with `RULES_LAWYER+NCP+continuity` tools → execute → final `chat`) `hub/app/llm/orchestrator.py:_agentic_chat`
   - `phi4-mini` path: single `generate` with RAG context (5–7 tok/s vs 8–11 tok/s Q4_K_M)
   Streams tokens back: `start` → many `chunk` → `end` (with sources) or `retrying`/`error` on drop.
5. `Rules Lawyer` deterministic (`LEVEL_DC`, `SIMPLE_DC`, `RARITY_ADJ`, `ACTION_SKILL` `hub/app/agents/rules_lawyer.py`) validates actions / calculates DCs — never LLM — e.g., `Trip` checks `athletics >= trained`.
6. If no LLM is reachable, the `end`/answer carries **raw rule excerpts** — never a dead end. The client resends `history` on reconnect so the hub rehydrates context.

## The rules-database problem

- The `.db` files live **only on the laptop**, are **git-ignored**, and are **never** committed
  to git. The phone carries its own copy: the ~19MB device extract of the 58MB FTS5 database
  (44,620 rows) ships inside the APK via Git LFS at
  `spoke_kt/app/src/main/assets/rules/pathfinder_rag.db` and is copied into app storage on
  first use, then opened read-only.
- **Extraction:** `DatabaseAssetManager.ensureExtracted` (Kotlin, on `Dispatchers.IO`) copies
  the asset to a temp file, `renameTo`s it into `context.getDatabasePath("pathfinder_rag.db")`,
  and drops a `pathfinder_rag.db.v2` marker. There is **no gzip and no Dart isolate** in this
  path: the asset is a **raw `.db`** because AGP decompresses `.gz` assets at build time and
  renames the entry, which would break the runtime open path. Play Asset Delivery
  `install-time` raw pack remains the Play Store option (future).
- Git tracks the *builder scripts* (`hub/scripts/`) + the schema doc, so the databases are
  reproducible without ever committing 500MB.
- If you need to move them between machines: a GitHub **Release asset** or **Google Drive** —
  not git.
- **Re-bundling:** replace the asset and bump `DatabaseAssetManager.BUNDLE_VERSION`, or
  installed devices keep their stale extracted copy.

## Offline-first tiers (Spoke)

| Need | Tier 1 (always) | Tier 2 (hub online) |
|---|---|---|
| Rules lookup | Bundled FTS5 DB (`RulesDatabase` over `NgaSQLiteOpenHelperFactory`, 250 ms debounced query) | Hub `/rules/search` fallback |
| Generation (PCs/NPCs/campaigns/maps) | — | Hub `/generate/*` + `/stream`, with `retrying` frames and history rehydration |
| Dice | Full PF2e engine (degrees, exploding `d6!!`, `kh`/`kl`, advantage) + spring Compose canvas or the Filament 3D pit | — |
| Character / campaign state | Room v3 (`AppDatabase`), vaults and journal | Summary generation needs the hub |

WebSocket resilience: OkHttp `WebSocket` to `/stream`, owned by `HubForegroundService`,
with backoff reconnect and `retrying` frames; the last turns are resent as `history` on
reconnect so the hub rehydrates context.

## Hardware-tuned defaults

| Device | Role | Notes |
|---|---|---|
| Dell Latitude 5400 (i5, CPU-only) | Hub | `phi4-mini` default (5–7 tok/s) or `qwen2.5:3b Q4_K_M` (8–11 tok/s) for ReAct tool-calling; `nomic-embed-text`; `rag_limit 4`, `num_predict 700`, `temperature 0.6`. |
| Moto G 5G (2025) | Spoke | UI only; local dice + the bundled 44,620-row FTS5 rule extract; no LLM. The pit requests high refresh explicitly — the panel advertises `[120, 90, 60]`. |

## Discovery (zero-config LAN)

The hub announces `_pathfindergod._tcp.local` over mDNS on startup
(`hub/app/discovery.py`, TXT: version + model). **The phone side does not browse yet** —
there is no `NsdManager` in the lane — so hub entry is manual: **Setup → Tether**, type the
LAN address, tap CONNECT. The hub probes `/health` and the header goes green.
Candidate order to implement if mDNS lands: last-known URL → laptop-hotspot gateway
`192.168.137.1:8000` (the laptop is always the gateway — no SSH needed) → emulator
`10.0.2.2:8000`, each verified with `GET /health` before display.

## Roadmap / next steps

- **Play from anywhere:** add [Tailscale](https://tailscale.com) to both devices; point the
  app at the laptop's Tailscale IP instead of its LAN IP. No code changes needed.
- ~~Offline rules on the phone~~ — **DONE**: bundled FTS5 extract + local dice. (The scripted
  offline "Guide chatbot" was **not** ported; the Guide tier is hub-only.)
- ~~Windows GM console~~ — **DONE**: standalone PySide6 exe (`tools/command_center/dist/`,
  git-ignored; build with PyInstaller from `command_center.spec`).
- **Other clients:** the HTTP hub extends to any platform with no architectural
  change; the native client is Android-only.
