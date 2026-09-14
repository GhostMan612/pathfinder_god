# Pathfinder God 🐉

A hub-and-spoke Pathfinder RPG system:

- **Hub** — a Python service that runs on your Windows laptop (WSL or native) and acts as a
  full Pathfinder "God" / Game Master. It answers rules questions, and builds characters,
  NPCs, monsters, bosses, maps, and campaigns — each with full biographies and backstories —
  using a local LLM (via [Ollama](https://ollama.com)) grounded in your Pathfinder rules
  databases (RAG).
- **Spoke** — a [Flutter](https://flutter.dev) Android app that is *your character*: dice
  roller, character sheet, live chat with the God, and a rules/bestiary browser.

```
┌────────────────────────────┐         Wi-Fi / LAN (later: Tailscale)         ┌──────────────────┐
│  HUB  ·  laptop (Python)   │  ◀──────────  HTTP + WebSocket  ──────────▶    │  SPOKE · Android │
│  FastAPI + Ollama + RAG    │                                                 │  Flutter app     │
│  500MB+ rules .db (local)  │                                                 │  dice · sheet    │
└────────────────────────────┘                                                 └──────────────────┘
```

## Why this shape?

The hub does all the heavy lifting (LLM inference + retrieval over 500MB+ of rules), so the
phone stays a thin, fast client. That split means:

- The **500MB+ databases never touch GitHub or the phone** — they live only on the laptop,
  reproducible from the builder scripts in `hub/scripts/`. See [`data/SCHEMA.md`](data/SCHEMA.md).
- The laptop (a CPU-only i5) runs **small local models** (`phi4-mini`, `llama3.2:3b`) with a
  **2-tier fallback**: local Ollama → raw rule excerpts (always an answer).
- Each half uses the best tool for its job (Python for AI, Flutter for a native themed UI),
  connected by one small [OpenAPI contract](shared/openapi.yaml).

## Layout

| Path | What |
|---|---|
| `hub/` | Python + FastAPI service (the God). See [`hub/README.md`](hub/README.md). |
| `spoke/` | Flutter Android app (your character). See [`spoke/README.md`](spoke/README.md). |
| `shared/openapi.yaml` | The API contract both sides build against. |
| `data/` | Where the big `.db` files live on the laptop (git-ignored). |
| `tools/` | Sound synth (`gen_audio.py`), Windows Command Center (prototype). |
| `docs/` | Setup + architecture guides. |

## Spoke features

- **Works offline** (laptop off): dice with PF2e degrees of success + 8π animated 3D die, the full 34k-entry
  rulebook via **native 8KB MethodChannel streaming** (Kotlin `AssetManager→GZIP`), the Pathfinder Guide chatbot
  (scripted intents + real rulebook retrieval), sound FX + ambient BGM, character storage.
- **Online extras**: live LLM generation via the hub (characters, NPCs, bosses, campaigns)
  with WebSocket `pingInterval:15s` + history rehydration and 3× auto-reconnect; hub auto-selects `phi4-mini` (fast) or `qwen2.5:3b` ReAct tool loop.

## Current status (2026-08-30 v0.6.0)

`flutter analyze` **No issues**, `flutter test` **18/18**, hub deterministic Rules Lawyer (`LEVEL_DC`/`ACTION_SKILL` never LLM), 2-tier + citation fidelity `[Source - Rule]` ≤3 sentences, Command Center `dist/PathfinderGodCommandCenter.exe` ~48MB standalone. See `docs/WHITEPAPER_ARCHITECTURE_v1.md` for deep dive and `blueprints/CURRENT_STATE.md` for gate status.

## Quick start

1. **Hub** — [`docs/setup-hub-windows.md`](docs/setup-hub-windows.md)
2. **Spoke** — [`docs/setup-spoke-android.md`](docs/setup-spoke-android.md)
3. **How it fits together** — [`docs/architecture.md`](docs/architecture.md)
