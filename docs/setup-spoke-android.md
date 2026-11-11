<!-- As Above, So Below. As Within, So Without. The Future Dictates the Past and the Past is Always Present. -->
# Native Android Spoke — build, Hub connection and device checks

The old Flutter spoke (`spoke/`) was retired in Phase 22. The supported app is
`spoke_kt/` (Kotlin, Jetpack Compose). Its current **Setup → Tether** UI contains
a manual **Hub URL** field and **CONNECT** button; it does not expose a
**Find hub automatically** picker. The laptop may advertise mDNS, but the
current Settings screen does not consume that discovery feed.

## Debug installation and first connection

1. Open `spoke_kt/` in Android Studio and deploy the **debug** app to a device,
   or run `./gradlew assembleDebug` inside `spoke_kt/`.
2. Start the Python Hub on your laptop and confirm
   `http://localhost:8000/health` returns JSON with `"status":"ok"`.
3. For an emulator on the same computer, use `http://10.0.2.2:8000`.
   **10.0.2.2 does not point to your laptop from a physical phone.**
4. On a phone connected to the same private Wi-Fi or laptop hotspot,
   enter `http://<current-laptop-LAN-IP>:8000` in **Setup → Tether** and press
   **CONNECT**. Allow inbound TCP 8000 in Windows Firewall (Private profile).
5. Verify the connection status. Test `http://<current-laptop-LAN-IP>:8000/health`
   in the phone's browser if the app cannot connect.

The debug variant permits cleartext LAN HTTP for development (`http://<current-laptop-LAN-IP>:8000`).
**Release builds require HTTPS**: they enforce release TLS pinned to the Hub's self-signed
certificate (`https://<current-laptop-LAN-IP>:8000`), with `10.0.2.2` as the sole cleartext
exception for emulator testing. To connect a release build:
1. Ensure the Hub is running with TLS enabled (`PFGOD_TLS_ENABLED=true` in `hub/.env`, with
   `hub-cert.pem` and `hub-key.pem` generated via `python hub/scripts/make_hub_cert.py`).
2. Verify that the app's `HUB_CERT_PIN` in `HubTlsClient.kt` matches the SHA-256 SPKI pin
   printed by `make_hub_cert.py`.
3. Enter `https://<current-laptop-LAN-IP>:8000` in **Setup → Tether** and connect.
Do not disable release network security to make a phone connect.

## Device smoke tests

CI compiles the `androidTest` APK, but **does not execute** instrumentation
tests on a physical device. Connect the phone with ADB authorization, bring up
a reachable Hub, and from `spoke_kt/` run:

```powershell
.\gradlew.bat connectedDebugAndroidTest --no-daemon --console=plain "-Pandroid.testInstrumentationRunnerArguments.hubBaseUrl=http://<current-laptop-LAN-IP>:8000"
```

Use a real, current laptop IP address in the command. Keep test credentials out
of logs. Save the device model, run result and Hub health response as review
evidence; a passing GitHub build or instrumentation **compilation** alone is
not a real-device PASS.

See [Windows Hub setup](setup-hub-windows.md) and
[troubleshooting](troubleshooting.md) for firewall and connectivity checks.
