# B5-HTTPS — Release TLS for the Pathfinder God Hub (one-sweep blueprint)

**Decision (Glenn, 11 Nov 2026):** Require HTTPS for release. Cleartext stays locked in the
release network-security config. A release build will not talk to the hub over plain HTTP on LAN.

**Base:** main `9419a22` (PRs #22–#25 merged). Hub suite 554 passed, Ruff clean, 0 open PRs.

**What already exists (do not rebuild):**
- Release config `spoke_kt/app/src/main/res/xml/network_security_config.xml` — base cleartext
  `false`, exactly one exception (`10.0.2.2`, emulator host). `NetworkSecurityConfigTest` pins this.
- Debug config — base cleartext `true` (any LAN hub). Debug builds are unaffected by this work.
- `HubEndpoint.requiresHttpsInRelease()` — true for http + non-emulator host. `SettingsScreen`
  already blocks an http hub URL in a non-debug build with
  "This build requires HTTPS for remote Hub connections. Use a trusted TLS endpoint."
  The transport notice already says production requires HTTPS.
- `HubEndpoint.normalize` accepts `http` and `https`; `streamUrl` maps `https` → `wss`.
  `isStreamPermitted` allows `wss://` always, `ws://` only in debug / emulator-only.
- `HubApiFactory` already sets `.followSslRedirects(false)` ("An HTTPS Hub must not silently
  downgrade to HTTP via redirect").
- The face dashboard (`/play`) and stage page are same-origin — no absolute hub URL anywhere,
  so they work over whatever scheme the hub serves. No change.

**What is missing (this blueprint):** the hub does not serve TLS at all, and the app has no way
to trust a hub certificate. OkHttp uses the system trust store, so a self-signed hub cert is
rejected today. That is the whole gap.

## 0. Trust model — read this first, it drives every choice below

- A public CA cannot issue for a private LAN IP, and Let's Encrypt needs a public domain.
  So the hub uses a **self-signed certificate**, generated once on the laptop.
- The app trusts **exactly one certificate, by pin** — OkHttp `CertificatePinner` with the
  SHA-256 of the hub cert's public key (`sha256/<base64>`). The pin is a hash of a public
  key, not a secret; it is committed to the repo.
- The hub's LAN IP changes with DHCP, so the cert's SAN cannot reliably match the address
  the app connects to. Therefore the app's hostname verification is relaxed **only because
  the pin is strict**: the shared hub client uses a `HostnameVerifier` that returns `true`,
  and the `CertificatePinner` then requires the exact pinned cert. An attacker presenting
  any other certificate — even a publicly valid one for that IP — fails the pin and the
  connection dies. The verifier is permissive **only** on this hub-only client; it must
  never be set on a general-purpose client.
- Do **not** trust user-installed CAs (`<trust-anchors><certificates src="user"/>`) — that
  would let any CA the user installs MITM the app, and it weakens the release posture this
  decision was made to keep. Do **not** open cleartext in the release config. Do **not**
  disable pinning in release.
- The certificate is long-lived (10 years). Rotation is rare and is a deliberate, manual
  step (see §9).

## 1. Hub — generate the certificate (new script)

New file: `hub/scripts/make_hub_cert.py` (stdlib + `cryptography`; add `cryptography` to
`hub/requirements.txt` — it has Windows wheels, so `pip install` works on the laptop).

- Generates an RSA 2048 self-signed certificate, validity 10 years (3650 days).
- Subject: `CN=Pathfinder God Hub`. SANs: `DNS:localhost`, `IP:127.0.0.1`, plus every
  non-loopback LAN IPv4 detected at generation time (reuse the address logic in
  `hub/app/discovery.py:_local_ipv4_addresses` — do not duplicate it; import it).
- Writes `data/tls/hub-cert.pem` and `data/tls/hub-key.pem` (0600 on the key where the
  platform allows it). `data/` is already gitignored (laptop-only) — verify the tls files
  are covered and add an explicit `data/tls/` line if they are not.
- Prints, on success, the exact OkHttp pin line to paste into the app, in the form
  `sha256/<base64-of-SPKI-hash>`, plus the cert expiry date and the SANs it contains.
  The pin is computed from the certificate's public key (SPKI), not from the whole cert.
- Idempotent and safe to re-run: refuses to overwrite an existing cert unless passed
  `--force`; on `--force` it warns that the old pin is now invalid and the app must be
  updated (see §9).
- Genesis header on the new file, per repo rules.

## 2. Hub — serve TLS (settings + startup)

`hub/app/config.py` (Server section, next to `host`/`port`):
- `tls_enabled: bool = False` (env `PFGOD_TLS_ENABLED`).
- `tls_certfile: Path | None = None` (env `PFGOD_TLS_CERTFILE`).
- `tls_keyfile: Path | None = None` (env `PFGOD_TLS_KEYFILE`).
- Defaults keep plain HTTP, so dev and the existing launch paths are untouched unless TLS
  is explicitly enabled.

`hub/app/main.py` (`__main__` block, line ~151):
- When `settings.tls_enabled` is true, call
  `uvicorn.run(app, host=settings.host, port=settings.port, ssl_certfile=settings.tls_certfile, ssl_keyfile=settings.tls_keyfile)`.
- Fail fast with a clear, actionable error if TLS is enabled but either file is missing
  or unreadable (log the exact path that is missing; do not start in plain HTTP as a
  silent fallback — a silent fallback would defeat the release decision).
- When TLS is off, the current call is unchanged.

`.env` / Command Center: no code change to the launcher. `tools/command_center/services.py`
starts the hub as `[VENV_PYTHON, "-m", "app.main"]`, so TLS is turned on by setting
`PFGOD_TLS_ENABLED=true`, `PFGOD_TLS_CERTFILE`, and `PFGOD_TLS_KEYFILE` in the hub `.env`
(or the environment). Document the three lines in the hub README (see §8).

## 3. Hub — advertise TLS over mDNS

`hub/app/discovery.py`:
- `start_advertisement` gains a `tls: bool = False` parameter; `main.py` passes
  `settings.tls_enabled`.
- When TLS is on, the TXT record gains `b"tls": b"1"`. When off, the key is absent
  (not `b"0"` — absence keeps old readers working).
- No other change: the service type, name, addresses, and port are unchanged.
- The phone side does not need to browse mDNS for this to work (manual IP entry still
  works), but when it does browse, it must read the `tls` flag and build an `https://`
  URL for a flagged hub instead of `http://`. If the discovery UI does not yet consume
  the flag, that is a follow-up, not a blocker — manual entry works.

## 4. Hub — Docker

`hub/Dockerfile`:
- `CMD` is unchanged (`["python", "-m", "app.main"]` — env-driven, same as the laptop).
- The healthcheck `curl -f http://localhost:8000/health` will fail once the container
  serves TLS. Change it to `curl -k -f https://localhost:8000/health` and gate it on TLS
  being on, OR keep the container on plain HTTP behind a TLS-terminating reverse proxy.
  Pick the first (in-container TLS) — it is the smaller change and matches the laptop.
- The cert/key must be mounted into the container (a volume), never baked into the image.
  Document the mount in the README.
- `EXPOSE 8000` is unchanged.

## 5. App — one shared pinned client (the core change)

New file: `spoke_kt/app/src/main/java/com/pathfindergod/spoke/data/network/HubTlsClient.kt`
(or extend `HubApiFactory` — one place either way, never two).

- Builds **one** `OkHttpClient` for all hub traffic, with:
  - `CertificatePinner` holding the hub cert pin as a constant, e.g.
    `const val HUB_CERT_PIN = "sha256/<base64 from §1>"`. Pin the hub's hostname/IP
    as the pattern (the pin applies to whatever host the client connects to — the
    client is hub-only, so a broad pattern is correct here; document why).
  - A `HostnameVerifier` that returns `true`, with a comment citing §0 (permissive
    only because the pin is strict, client is hub-only).
  - The existing timeouts and `.followSslRedirects(false)` from `HubApiFactory.client()`.
- `HubApiFactory` must use this shared client instead of building its own. Keep its
  caching, `normalize`, and `shutdown` behaviour unchanged.
- `HubWebSocketClient` currently builds its **own** `OkHttpClient` in its default
  constructor parameter. Change it to accept the shared client (default to the shared
  factory) so the `wss://` stream is pinned by the same trust. Do not build a second
  pinning client — one trust configuration, two consumers.
- Pinning only applies to `https`/`wss` connections, so `http` URLs (debug builds,
  emulator `10.0.2.2`) are unaffected — no behaviour change there.
- The pin constant is the **only** app-side value that comes from the cert generation
  step. The blueprint consumer (DeepSeek) must paste the exact `sha256/...` line the
  script prints; do not hand-type or re-derive it.

## 6. App — no config change, no Settings change

- `spoke_kt/app/src/main/res/xml/network_security_config.xml` (main): **no change**.
  Base cleartext stays `false`, the only exception stays `10.0.2.2`.
- `spoke_kt/app/src/debug/res/xml/network_security_config.xml`: **no change**.
- `NetworkSecurityConfigTest`: **no change** — it already asserts the locked state.
- `SettingsScreen`: **no change** — it already blocks http hub URLs in non-debug builds
  and already shows the transport notice. Once this work lands, a release build will
  accept an `https://` hub URL and connect; before it lands, the same URL fails TLS
  trust (which is the correct failure, not a bug).

## 7. Tests

### Hub (Python, `hub/tests/`)
- `test_tls_settings.py` (new): `tls_enabled` defaults false; enabling it with missing
  cert/key files fails fast at startup (assert the error names the missing path);
  enabling it with valid files starts the server (use the generated test cert, not the
  real one).
- `test_make_hub_cert.py` (new): the script generates a valid cert + key, the cert
  parses, its SANs include `localhost`/`127.0.0.1`, the printed pin matches the cert's
  SPKI hash, and re-running without `--force` refuses to overwrite.
- `test_tls_smoke.py` (new): start the app with a test cert over TLS and assert
  `GET /health` returns 200 over `https` (with verification disabled in the test client)
  and that plain `http` to the same port is refused (connection error, not a silent
  redirect or a 200).
- `test_discovery.py` (extend): when TLS is on, the advertised TXT record contains
  `tls=1`; when off, the key is absent.

### Spoke (Kotlin, `spoke_kt/app/src/test/`)
- `HubTlsClientTest.kt` (new): with the pinned client, a connection to a server
  presenting the pinned test cert succeeds; a server presenting a different cert
  (same hostname, valid public chain) is rejected; an `http://` URL still works
  through the same factory (pinning is https-only).
- `HubApiFactoryTest.kt` (extend): `HubApiFactory.get("https://...")` returns an API
  backed by the pinned client (assert the client's certificate pinner contains the
  hub pin). Existing https/wss/`requiresHttpsInRelease` cases stay.
- `NetworkSecurityConfigTest`: no change.
- Note: these are JVM unit tests with a local test TLS server (OkHttp `MockWebServer`
  with TLS, or an in-process `HttpsServer`). Do not add a test that depends on the
  real hub cert — the real pin is a build-time constant, the tests use a test pin.

## 8. Docs

- `hub/README.md`: run instructions gain the TLS path — generate the cert
  (`python scripts/make_hub_cert.py`), set the three `PFGOD_TLS_*` lines in `.env`,
  restart the hub, and paste the printed pin into the app. Keep the plain-HTTP dev
  path documented alongside it.
- The setup/troubleshooting docs corrected in PR #24 (LAN, emulator, release HTTPS):
  update the release-HTTPS section from "required but not yet possible" to the real
  steps, and note that the release build now connects over `https://<lan-ip>:8000`.
- `docs/pathfinder-god-checklist.md`: record the B5 decision (HTTPS required, 11 Nov 2026)
  and this blueprint as the implementation; mark B5 closed as decided, implementation
  as the open item.
- `shared/openapi.yaml`: no change (same routes, same contract; only the scheme changes).

## 9. Rotation and recovery

- The cert is valid 10 years. If it expires or is lost: re-run the script with `--force`,
  paste the new pin into `HubTlsClient.kt`, rebuild the app, and restart the hub with
  the new files. The old app build will refuse the new cert until it is updated — that
  is by design (a rotated cert the old app still trusted would defeat pinning).
- If the pin in the app and the cert on the hub ever disagree, the symptom is a TLS
  handshake failure on every hub call in a release build (debug http still works).
  The fix is to re-check that the pin in the app matches the cert the hub is serving
  (`python scripts/make_hub_cert.py` prints the pin; compare it to the constant).
- Keep a backup of `data/tls/` with the hub's other laptop-only data. Never commit the
  key to the repo.

## 10. Verification gate (do not merge until all of it is true)

- Hub: full suite green (`pytest tests/ -q`), Ruff `check app/ tests/` clean.
- Spoke: JVM unit tests green (`./gradlew testDebugUnitTest`), `assembleDebug` green.
- CI on the PR head: Hub Tests, Hub Lint, Spoke Unit Tests, Spoke Build all success.
- Live (laptop + phone, Glenn/DeepSeek — not verifiable from this VM):
  1. Generate a real cert with the script; record the printed pin.
  2. Start the hub with `PFGOD_TLS_ENABLED=true`; `curl -k https://<lan-ip>:8000/health`
     returns 200; plain `curl http://<lan-ip>:8000/health` fails.
  3. Debug build on the phone: set the hub URL to `https://<lan-ip>:8000`, play a turn
     over the dashboard/SSE — it works.
  4. Release build on the phone: the same `https://` URL works; an `http://` URL is
     refused by the Settings gate with the requires-HTTPS error; the emulator
     `http://10.0.2.2:8000` still works on an emulator.
  5. `LanHubSmokeTest` gains a TLS variant (or a new release-mode smoke test) that
     asserts the release build reaches the hub over HTTPS — run it on the real device
     via `connectedDebugAndroidTest` (CI does not run it).

## 11. Build order (one sweep, in this order)

1. §1 cert script + `cryptography` dep. 2. §2 settings + uvicorn wiring + fail-fast.
   3. §3 mDNS `tls` flag. 4. §4 Dockerfile healthcheck. 5. §5 shared pinned client
   (REST + WebSocket). 6. §7 tests (hub first, then spoke). 7. §8 docs. 8. §10 gate.
   Do not open cleartext, do not trust user CAs, do not skip the pin.

## Files touched (complete list)

- New: `hub/scripts/make_hub_cert.py`, `hub/tests/test_tls_settings.py`,
  `hub/tests/test_make_hub_cert.py`, `hub/tests/test_tls_smoke.py`,
  `spoke_kt/app/src/main/java/com/pathfindergod/spoke/data/network/HubTlsClient.kt`,
  `spoke_kt/app/src/test/java/com/pathfindergod/spoke/data/network/HubTlsClientTest.kt`.
- Modified: `hub/requirements.txt` (+`cryptography`), `hub/app/config.py` (TLS settings),
  `hub/app/main.py` (uvicorn TLS + discovery flag), `hub/app/discovery.py` (`tls` param +
  TXT key), `hub/Dockerfile` (healthcheck), `hub/README.md`, docs corrected in PR #24,
  `docs/pathfinder-god-checklist.md`,
  `spoke_kt/app/src/main/java/com/pathfindergod/spoke/data/network/HubApiFactory.kt`
  (use shared client), `spoke_kt/app/src/main/java/com/pathfindergod/spoke/data/network/HubWebSocketClient.kt`
  (use shared client), `spoke_kt/app/src/test/java/com/pathfindergod/spoke/data/network/HubApiFactoryTest.kt`.
- Unchanged (deliberately): both `network_security_config.xml` files,
  `NetworkSecurityConfigTest.kt`, `SettingsScreen.kt`, `strings.xml`, `shared/openapi.yaml`.
