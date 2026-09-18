<!-- As Above, So Below. As Within, So Without. The Future Dictates the Past and the Past is Always Present. -->
# Troubleshooting (phone + laptop)

Start here before digging into logs. Most problems are one of the five below.

## 1. "Couldn't reach the God" / no hubs found

1. Is the hub running? Easiest: **Command Center → Services → Start Ollama →
   Start Hub**. Terminal alternative: `C:\venv-hub\venv\Scripts\python.exe -m app.main`
   in `C:\pathfinder_god\hub`.
2. Same network? The phone must be on the **same Wi-Fi as the laptop**, or join the
   **laptop's own hotspot** (most reliable at the table).
3. In the app: **Setup → Find hub automatically** → tap your laptop.
4. Still nothing? Check `tools/command_center/logs/hub.log` on the laptop.

## 2. "Hub returned 404"

You typed Ollama's port. The hub is `:8000`, Ollama is `:11450` — the phone
**never** talks to `:11450`. The app auto-corrects this, but fix the URL to
`http://<laptop-ip>:8000` to be sure.

## 3. Windows Firewall blocks the phone

Allow inbound **TCP 8000** (Private network profile is enough for home Wi-Fi /
hotspot). Quick test from the phone's browser: `http://<laptop-ip>:8000/health`
should return JSON.

## 4. Rules show "Offline book unavailable"

The bundled database extracts on first launch (20MB → 58MB, ~30 seconds, spinner
in the Rules tab). If it fails: force-stop the app, clear storage, relaunch on
good Wi-Fi (extraction is local, but first launch shouldn't be interrupted).
Developers: watch `adb logcat` across first launch; the Oracle gates until extraction succeeds.

## 5. Link drops or won't connect

The foreground service retries with backoff and the status dot in Setup → Tether
shows the live state. If it never reaches CONNECTED, the laptop IP changed or the
hub restarted — re-enter the URL and press CONNECT.

## 6. "No entry" for something that should exist

Tap **Fetch from the web** under the empty result (needs the hub online once).
The hub scrapes that exact term into the database permanently — it works
offline afterwards. If fetch fails, the query stays queued and a later
backfill run picks it up.

## 7. Emulator vs real device

- Emulator on the same machine as the hub: `http://10.0.2.2:8000` (default).
- Real device: auto-discovery, or the laptop's LAN/hotspot IP with `:8000`.

## Where logs live

| Symptom | Log |
|---|---|
| Hub won't start / 500s | `tools/command_center/logs/hub.log` |
| Ollama/model issues | `tools/command_center/logs/ollama.log` |
| App extraction/search | `adb logcat` during first launch |
| API shapes | `http://localhost:8000/docs` (hub running) |
