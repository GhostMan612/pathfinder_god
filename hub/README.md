# Pathfinder God — Hub (Python)

The "God": a FastAPI service that answers Pathfinder GM requests using retrieval over your
local rules databases (RAG) plus a local LLM, with a graceful fallback chain.

## Backend fallback (always gives an answer)

1. **DeepSeek API** — used only if `PFGOD_DEEPSEEK_API_KEY` is set (best for long bios).
2. **Local Ollama** — the laptop's small model (`phi4-mini` by default).
3. **Raw rule excerpts** — no LLM; hands back the retrieved rules.

## Install & run

```bash
cd hub
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# point at your databases if they aren't in <repo>/data:
export PFGOD_DATA_DIR=/path/to/your/pathfinder_ai   # Windows: setx / $env:

uvicorn app.main:app --host 0.0.0.0 --port 8000     # 0.0.0.0 so the phone can reach it
```

Open `http://localhost:8000/docs` for interactive API docs. Full setup (Ollama install,
model pull, finding your laptop IP) is in [`../docs/setup-hub-windows.md`](../docs/setup-hub-windows.md).

## CLI (no phone / no server needed)

```bash
pathfinder-god "build me a level 3 rogue with a full backstory"
pathfinder-god --edition 2e            # interactive loop
```

## HTTP API (summary)

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Version, model, which DBs were found. |
| POST | `/ask` | General GM Q&A / generation (auto-detects mode). |
| POST | `/generate/{kind}` | `character`·`npc`·`monster`·`boss`·`map`·`campaign`·`encounter`. |
| GET | `/rules/search?q=&edition=` | Raw rule/bestiary lookup (no LLM). |
| GET/POST | `/campaign`, `/campaign/note`, `/campaign/reset` | Campaign state. |
| WS | `/stream` | Live token-by-token "God is typing" feed. |

Regenerate the shared contract after any change: `python scripts/export_openapi.py`.

## Package layout

```
app/
├── config.py         # env-driven settings (PFGOD_*)
├── rag/search.py     # read-only FTS retrieval + 2e→1e fallback + shape detection
├── llm/backends.py   # 3-tier fallback (DeepSeek → Ollama → raw excerpts), async + streaming
├── agent/gm.py       # detect_mode + prompt building (full bios/backstories)
├── generators/       # (mode prompts live in main.py's /generate route)
├── state/campaign.py # party roster + GM notes (JSON)
├── service.py        # orchestrates retrieval + prompt + LLM
├── models.py         # pydantic wire contract (drives OpenAPI)
├── main.py           # FastAPI app (routes + WebSocket)
└── cli.py            # terminal access
```
