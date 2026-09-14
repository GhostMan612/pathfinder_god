# Hub setup — the laptop (Dell Latitude 5400)

The hub is the Python service that acts as the Pathfinder God. It runs on your laptop and
serves the phone over your Wi-Fi.

Your laptop is CPU-only (i5 8th gen, no discrete GPU), so we use **small** local models.

## 1. Install Ollama (the local LLM engine)

1. Install Ollama for Windows from <https://ollama.com/download>. It runs as a background
   service at `http://localhost:11434`.
2. Pull a small, CPU-friendly model:

   ```powershell
   ollama pull phi4-mini        # ~3.8B, the default
   # optional alternative:
   ollama pull llama3.2:3b
   ```

3. Sanity check: `ollama run phi4-mini "Say hello as a Pathfinder GM."`

> On this CPU, expect a slow but usable pace. For long biographies, the local model
> will take longer but still works — no cloud dependency.

## 2. Put your rules databases in place

Copy your existing `.db` files (`pathfinder_rag.db`, `pathfinder_god.db`,
`pathfinder_1e_rag.db`, `pathfinder_2e_rag.db`) into the repo's `data/` folder — **or** point
the hub at wherever they already live:

```powershell
$env:PFGOD_DATA_DIR = "\\wsl.localhost\Ubuntu\home\sovereign_mantle\pathfinder_ai"
```

These files are git-ignored and never uploaded. See [`../data/SCHEMA.md`](../data/SCHEMA.md).
To rebuild them from source, drop your `build_rag.py` / `build_2e_rag.py` into `hub/scripts/`
and run `python hub/scripts/rebuild_rags.py`.

> **If the databases are currently on the phone:** move them to the laptop first, e.g.
> `adb pull /sdcard/pathfinder_rag.db data\` (or copy via Google Drive). The phone doesn't
> need them — it asks the hub.

## 3. Install and run the hub

Works in WSL (Ubuntu) or native Windows. Python 3.10+.

```bash
cd hub
python -m venv .venv
. .venv/bin/activate                 # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"

# start the server, bound so the phone can reach it:
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open <http://localhost:8000/docs> to try the API. `GET /health` shows the model and which
databases were found.

## Troubleshooting

- **Phone can't connect:** confirm both devices are on the same Wi-Fi, the firewall allows
  8000, and you started uvicorn with `--host 0.0.0.0` (not the default localhost-only).
- **`/health` shows `databases_found: []`:** `PFGOD_DATA_DIR` is wrong, or the `.db` files
  aren't there yet.
- **Generations are slow:** normal on CPU. Use a smaller model, lower `PFGOD_OLLAMA_NUM_PREDICT`.
