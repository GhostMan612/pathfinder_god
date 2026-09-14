# Spoke setup — the Android app (Moto G 5G 2025)

The spoke is the Flutter app that lives on your phone. It needs the hub running on your
laptop (see [`setup-hub-windows.md`](setup-hub-windows.md)).

## 1. Install Flutter (on the laptop, for building)

Follow <https://docs.flutter.dev/get-started/install>. Verify with `flutter doctor`
(you need the Android toolchain: Android SDK + a device or emulator).

## 2. Generate the Android project and fetch packages

The `android/` folder isn't committed — Flutter generates it. From the repo:

```bash
cd spoke
flutter create --platforms=android --org com.pathfindergod --project-name pathfinder_spoke .
git checkout -- pubspec.yaml lib test analysis_options.yaml   # in case flutter create touched them
flutter pub get
```

## 3. Allow LAN plain-HTTP

The hub is served over `http://` on your LAN, so enable cleartext traffic. In
`android/app/src/main/AndroidManifest.xml`, add to the `<application ...>` tag:

```xml
<application
    android:usesCleartextTraffic="true"
    ... >
```

For a **release** APK, also add this permission inside `<manifest>`:

```xml
<uses-permission android:name="android.permission.INTERNET"/>
```

## 4. Build and install

```bash
# quickest: run on a plugged-in phone (enable USB debugging first)
flutter run

# or build a release APK to sideload:
flutter build apk --release
# -> build/app/outputs/flutter-apk/app-release.apk  (copy to the phone and install)
```

## 5. Point the app at the hub

Open the app → **Setup** tab → set **Base URL** to your laptop's Wi-Fi IP, e.g.
`http://192.168.1.42:8000` → **Save & test connection**. A green card means you're linked to
the God (it shows the model and which databases were found).

> Android emulator on the same laptop as the hub? Use `http://10.0.2.2:8000` (the emulator's
> alias for the host machine) — this is the app's default.

## What works where

| Feature | Needs the hub? |
|---|---|
| Dice roller (incl. advantage/disadvantage) | No — fully offline |
| Character sheet (view/edit/save) | No — stored on the phone |
| "Forge full bio with the God" | Yes |
| GM chat (live streaming) | Yes |
| Rules & bestiary search | Yes |

## Troubleshooting

- **"Couldn't reach the God":** check the Setup URL, that the hub is running with
  `--host 0.0.0.0`, both devices on the same Wi-Fi, and the laptop firewall allows port 8000.
- **Chat connects but never streams:** some networks block WebSockets between clients — try a
  phone hotspot, or later set up Tailscale (see [`architecture.md`](architecture.md)).
