# Architecture

## The shape

```
        ┌─────────────────────────────────────────┐
        │  HUB — laptop (Python + FastAPI)         │
        │                                          │
        │   ┌────────┐   ┌─────────┐   ┌────────┐  │
        │   │  RAG   │◀──│  God    │──▶│  LLM   │  │
        │   │ FTS5   │   │ service │   │ router │  │
        │   │ .db    │   └─────────┘   └───┬────┘  │
        │   │ 500MB+ │                     │       │
        │   └────────┘        ┌────────────┴─────┐ │
        │                     │ 1. Ollama (local) │ │
        │                     │ 2. raw excerpts   │ │
        │                     └───────────────────┘ │
        └───────────────▲──────────────────────────┘
                        │  HTTP (REST) + WebSocket (/stream)
                        │  LAN now · Tailscale later
        ┌───────────────┴──────────────────────────┐
        │  SPOKE — phone (Flutter / Android)        │
        │  dice · character sheet · GM chat · rules │
        └───────────────────────────────────────────┘
```

## Why two languages (and why that's correct here)

The hub does all the heavy lifting — LLM inference and retrieval over 500MB+ of rules — so the
phone can stay a thin, fast client. Because of that split, the two halves share almost no
logic: only a small JSON contract ([`../shared/openapi.yaml`](../shared/openapi.yaml)) and the
dice math. That makes "one language for both" a cost with no benefit, so each side uses the
best tool:

- **Python** on the hub — reuses the existing RAG/agent code and has the best local-LLM
  ecosystem.
- **Flutter** on the phone — native performance on a budget device, and a themable UI for the
  Pathfinder look and feel.

The original scripts (`hub_agent.py`, `gm_local.py`, `gm_termux_combined.py`) were consolidated
into the hub package rather than rewritten — same RAG, same 2e→1e edition fallback, same
3-tier LLM fallback.

## Request flow (a GM question)

1. Phone opens a WebSocket to `/stream` and sends `{query, edition, mode?, history}` with 15s `pingInterval` (`IOWebSocketChannel`) to survive Doze/Wi-Fi roam.
2. Hub retrieves the top rule snippets from the FTS5 DB (2e first, then 1e).
3. Hub builds a mode-specific prompt (mode templates + `[Source - Rule]` ≤3 sentences ≤300 chars citation fidelity) with that rule context.
4. Hub routes the prompt through the fallback chain:
   - `qwen2.5:3b` path: 3-turn ReAct loop (`chat` with `RULES_LAWYER+NCP+continuity` tools → execute → final `chat`) `hub/app/llm/orchestrator.py:_agentic_chat`
   - `phi4-mini` path: single `generate` with RAG context (5–7 tok/s vs 8–11 tok/s Q4_K_M)
   Streams tokens back: `start` → many `chunk` → `end` (with sources) or `retrying`/`error` on drop.
5. `Rules Lawyer` deterministic (`LEVEL_DC`, `SIMPLE_DC`, `RARITY_ADJ`, `ACTION_SKILL` `hub/app/agents/rules_lawyer.py`) validates actions / calculates DCs — never LLM — e.g., `Trip` checks `athletics >= trained`.
6. If no LLM is reachable, the `end`/answer carries **raw rule excerpts** — never a dead end. Client resends `history` on reconnect so hub rehydrates context.

## The 500MB database problem

- The `.db` files live **only on the laptop**, are **git-ignored**, and are **never** committed
  to git. The phone carries its own copy: a 48MB gzip of the 132MB FTS5 database ships inside
  the APK (`spoke/assets/rules/`) and is extracted on first launch (`RulebookDb`, read-only).
- **Extraction (Gemini §15.1, 2026-08-30):** Native Kotlin `MainActivity` streams via `AssetManager→GZIPInputStream` 8KB chunks → `FileOutputStream` → `fd.sync()` → ext4 atomic `renameTo` (peak 8KB, not 180MB). Dart `MethodChannel('com.pathfindergod/rulebook')` tries native first; `Isolate.run(gzip.decode)` fallback for non-Android/tests. `getApplicationDocumentsDirectory()/rulebook` is the writable target (not `/.dart_tool/...` which gave `ENOENT` on Moto G). Static `Future` lock prevents double 50MB decode (OOM); `addPostFrameCallback` defers until after first frame (fixes `Skipped 227 frames` / `Davey 3844ms`). Pad: Play Asset Delivery `install-time` raw 132MB pack for Play Store Approach B (future).
- Git tracks the *builder scripts* (`hub/scripts/`) + the schema doc, so the databases are
  reproducible without ever committing 500MB.
- If you need to move them between machines: a GitHub **Release asset** or **Google Drive** —
  not git.
- **Re-bundling:** regenerate the `.gz`, replace the asset, and bump `RulebookDb.bundleVersion`
  or installed devices keep their stale extracted copy.

## Offline-first tiers (Spoke)

| Need | Tier 1 (always) | Tier 2 (hub online) |
|---|---|---|
| Rules lookup | Bundled FTS5 DB (`RulebookDb` native 8KB) | Hub `/rules/search` fallback |
| Guide chatbot | Scripted intents + offline retrieval (cited) | Hub RAG `/ask`/`/stream` with ReAct |
| Dice | Full PF2e engine (degrees, fortune, hero points) + 8π→9.3π animated die | — |
| Generation (PCs/NPCs/campaigns) | — | Hub `/generate/*` + `/stream` (heartbeat 15s + history + `retrying`) |

WebSocket resilience: `HubClient.stream` `IOWebSocketChannel(pingInterval:15s)` + 3× exponential backoff 400·2ⁿ ms, `retrying` frames; `GmChatScreen._buildHistory` passes last 12 turns for continuity.

## Hardware-tuned defaults

| Device | Role | Notes |
|---|---|---|
| Dell Latitude 5400 (i5, CPU-only) | Hub | `phi4-mini` default (5–7 tok/s) or `qwen2.5:3b Q4_K_M` (8–11 tok/s) for ReAct tool-calling; `nomic-embed-text`; `rag_limit 4`, `num_predict 700`, `temperature 0.6`. |
| Moto G 5G (2025) | Spoke | UI only; local dice + 8KB-streamed 34k rule DB; no LLM. MethodChannel keeps peak 8KB (not 180MB) on 4GB RAM. |

## Roadmap / next steps

- **Play from anywhere:** add [Tailscale](https://tailscale.com) to both devices; point the
  app at the laptop's Tailscale IP instead of its LAN IP. No code changes needed.
- ~~Offline rules on the phone~~ — **DONE**: bundled FTS5 DB + offline chatbot + local dice.
- **Windows GM console:** PySide6 + QtAsyncio desktop app (`tools/`, research complete;
  Tkinter prototype is disposable).
- **iOS / web:** both the Flutter app and the HTTP hub extend to these with no architectural
  change.
```
