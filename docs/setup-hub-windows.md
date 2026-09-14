# Hub setup — the laptop (Windows)

The hub is the Python service that acts as the Pathfinder God. It runs on your laptop
and serves the phone over your Wi-Fi (or your laptop's hotspot).

Your laptop is CPU-only, so we use **small** local models.

## 0. What you need

- Windows 10/11, Python environment at `C:\venv-hub`
  (use it as-is — do **not** create a local `.venv`; install extra packages into it
  with `C:\venv-hub\venv\Scripts\python.exe -m pip install <pkg>`).
- Ollama for Windows: <https://ollama.com/download>.

## 1. Install the model (the local LLM engine)

```powershell
# Ollama listens on 0.0.0.0:11434; the hub talks to it on 127.0.0.1:11450
ollama pull phi4-mini        # ~3.8B, the default (5-7 tok/s on i5)
ollama pull qwen2.5:3b       # optional: better tool-calling (8-11 tok/s Q4)
```

Sanity check: `ollama run phi4-mini "Say hello as a Pathfinder GM."`

> On this CPU expect a slow but usable pace. Long biographies take longer —
> there is no cloud dependency. Switch models with `PFGOD_OLLAMA_MODEL`
> (see `hub/.env.example`).

## 2. Rules database (already warm)

`data/pathfinder_rag.db` (43,884 FTS5 rows) lives **only on the laptop** and is
git-ignored. A fresh clone won't have it — either copy it from your machine or
rebuild from open sources:

```powershell
C:\venv-hub\venv\Scripts\python.exe hub/scripts/rebuild_rags.py
```

How the DB is built, where the sources come from, and licensing:
[`database.md`](database.md). Schema: [`../data/SCHEMA.md`](../data/SCHEMA.md).

## 3. Run the hub

Easiest — double-click **`Start_CommandCenter.bat`** at the repo root, then
**Services → Start Ollama → Start Hub**. Logs live in
`tools/command_center/logs/` — check them first when something fails.

Or in a terminal:

```powershell
cd C:\pathfinder_god\hub
C:\venv-hub\venv\Scripts\python.exe -m app.main   # http://0.0.0.0:8000
```

Open <http://localhost:8000/docs> to try the API. `GET /health` shows the model
and which databases were found. On startup the hub also announces itself over
mDNS (`_pathfindergod._tcp`) so the phone finds it automatically.

## 4. Let the phone reach it

- Same Wi-Fi **or** the laptop's own hotspot both work.
- Windows Firewall must allow inbound **TCP 8000** (and 11450 only matters
  laptop-internally — the phone never talks to Ollama directly).
- You do **not** need to find your LAN IP by hand: the app's
  **Setup → Find hub automatically** lists the laptop. Manual fallback is
  `http://<laptop-lan-ip>:8000`.

## Troubleshooting

- **Phone can't connect:** hub running? Same network? Firewall rule for 8000?
  Started with `--host 0.0.0.0` (both launchers already do)? See
  [`troubleshooting.md`](troubleshooting.md).
- **`/health` shows `databases_found: []`:** the `.db` files aren't in `data/`
  — copy or rebuild them (step 2).
- **Generations are slow:** normal on CPU. Smaller model, or lower
  `PFGOD_OLLAMA_NUM_PREDICT`.
