# Pathfinder God — Hub (Python)

The "God": a FastAPI service that answers Pathfinder GM requests using retrieval
over your local rules database (RAG) plus a local LLM — with a fallback chain
that always returns an answer.

## Backend fallback (never a dead end)

1. **Local Ollama** — the laptop's small model (`phi4-mini` by default,
   `qwen2.5:3b` for tool-calling). RAG-grounded, citations attached.
2. **Raw rule excerpts** — no LLM; hands back the retrieved rules directly.

## Semantic Retrieval Overlay (SS-001)

The Hub includes an optional hybrid semantic retrieval spine combining local lexical FTS5 search with vector similarity via Reciprocal Rank Fusion (RRF):

- **Default-OFF in production**: Governed by `PFGOD_SEMANTIC_ENABLED=False` in `hub/.env` (or environment). When disabled, retrieval is pure lexical FTS5 with identical baseline performance.
- **Model pin**: `embeddinggemma-2:270m` (text-only 270M parameters, 256 dimensions with L2 renormalization).
- **Index requirement**: Requires an externally prebuilt SQLite sidecar index at `data/semantic_rules.sqlite3` built via `python -m app.rag.semantic_spine.cli build`. No index is built dynamically during user requests.
- **Fail-closed safety**: If the sidecar is absent, stale, corrupted, or the local Ollama embedding service is unreachable/timed out, retrieval seamlessly falls back to lexical FTS5 without raising errors or fabricating results.
- **Hub-only**: This capability exists solely on the Python Hub. The Android Spoke does not perform vector embeddings and continues to query its bundled offline FTS5 rulebook directly.

## Install & run

Use the existing environment as-is — do **not** create a local `.venv`:

```powershell
cd C:\pathfinder_god\hub
C:\venv-hub\venv\Scripts\python.exe -m app.main   # http://0.0.0.0:8000
```

Or double-click **`Start_CommandCenter.bat`** at the repo root
(Services → Start Ollama → Start Hub). Logs: `tools/command_center/logs/`.

Open `http://localhost:8000/docs` for interactive API docs. On startup the hub
announces `_pathfindergod._tcp` over mDNS so the phone finds it automatically
(`app/discovery.py`; silent no-op if `zeroconf` is missing).

Settings live in `hub/.env` (see `.env.example`, `PFGOD_*` keys) — never commit it.

### Running with Release HTTPS (TLS)

Release Android builds enforce HTTPS with public key pinning. To serve TLS from the Hub:

1. Generate the self-signed 10-year certificate (RSA 2048):
   ```powershell
   C:\venv-hub\venv\Scripts\python.exe hub/scripts/make_hub_cert.py
   ```
   This generates `data/tls/hub-cert.pem` and `data/tls/hub-key.pem` (git-ignored) and prints the OkHttp SHA-256 SPKI pin string (e.g. `HUB_CERT_PIN = "sha256/..."`).

2. Configure TLS in `hub/.env`:
   ```ini
   PFGOD_TLS_ENABLED=true
   PFGOD_TLS_CERTFILE=../data/tls/hub-cert.pem
   PFGOD_TLS_KEYFILE=../data/tls/hub-key.pem
   ```

3. Ensure the printed pin matches `HUB_CERT_PIN` in `spoke_kt/app/src/main/java/com/pathfindergod/spoke/data/network/HubTlsClient.kt`.

4. Start the hub normally (`python -m app.main`). Uvicorn will bind HTTPS on port 8000 and mDNS will advertise `tls=1`. Plain HTTP development remains available by omitting or disabling `PFGOD_TLS_ENABLED`.

## CLI (no phone / no server needed)

```powershell
C:\venv-hub\venv\Scripts\python.exe -m app.cli "build me a level 3 rogue"
```

## HTTP API (summary)

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Version, model, which DBs were found. |
| POST | `/ask` | GM Q&A / generation (auto-detects mode, RAG + citations). |
| POST | `/generate/{kind}` | `character`·`npc`·`monster`·`boss`·`map`·`campaign`·`encounter`. |
| GET | `/rules/search?q=&edition=&limit=` | Raw rule lookup, exact-match first (no LLM). |
| GET/POST | `/campaign`, `/campaign/note`, `/campaign/reset` | Campaign state + continuity. |
| GET/POST | `/campaign/export`, `/campaign/import` | Backup/restore (JSON). |
| WS | `/stream` | Token-by-token feed (`start`→`chunk`*→`end`, plus `retrying`/`error`). |
| POST | `/rules/fetch` | Scrape one missing 1e term into the DB permanently (else 404+queue). |
| POST/GET | `/rules/missed` | Offline miss queue in/out (`data/misses.jsonl` backfill feed). |

Contract: [`../shared/openapi.yaml`](../shared/openapi.yaml) (v0.1.0).
Regenerate after changes: `python scripts/export_openapi.py`.
Full endpoint reference: [`../docs/api.md`](../docs/api.md).

## Package layout

```
app/
├── main.py            # FastAPI factory, middleware, lifespan (DB + mDNS)
├── config.py          # PFGOD_* settings (pydantic-settings)
├── discovery.py       # mDNS advertisement (_pathfindergod._tcp)
├── api/               # health, ask (+/stream WS), generate, rules,
│                      # campaign (+export/import), monitoring, security
├── rag/               # retriever.py (hybrid router, exact→FTS5→Unknown tiers),
│                      # raw_fallback.py, search.py (legacy shape detection),
│                      # semantic_spine/ (OllamaEmbedder, SemanticStore, RRF, adapter)
├── llm/               # orchestrator.py (2-tier + qwen ReAct loop),
│                      # ollama_client.py (generate/stream/chat/embeddings)
├── agents/            # rules_lawyer.py (deterministic LEVEL_DC/ACTION_SKILL),
│                      # npc_compiler.py, continuity.py
├── db/repository.py   # campaign SQLite (9 tables)
└── cli.py             # terminal access
```

Rules data: [`../docs/database.md`](../docs/database.md) ·
schema [`../data/SCHEMA.md`](../data/SCHEMA.md).
