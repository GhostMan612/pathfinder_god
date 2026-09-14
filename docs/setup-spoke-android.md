# Spoke setup — the Android app (Flutter)

The spoke is the Flutter app on your phone: dice, character sheet, God chat, and
the offline rulebook. It needs the hub running on your laptop
(see [`setup-hub-windows.md`](setup-hub-windows.md)) — but dice, characters, and
the rulebook work fully offline.

> Cloning? Install Git LFS **first** (`git lfs install`), or the bundled
> rulebook arrives as a useless pointer file.

## 1. Build it (Android Studio — recommended)

1. Open the `spoke/` folder in Android Studio.
2. Let Gradle sync, then press **Run** on your device/emulator.

That's it — `android/` is committed, no `flutter create` needed (running it would
overwrite the branded config: `com.pathfindergod`, icons, splash).

## 2. Command-line alternative

```bash
cd spoke
flutter pub get
flutter analyze        # must be clean
flutter test           # 21/21
flutter run            # NOT for commits — lane ends at analyze+test
```

Never commit APKs/AABs. If `flutter pub upgrade` wants `sqlite3_flutter_libs`
0.6.0, refuse it — stay on `^0.5.42` (0.6.0 is end-of-life upstream).

## 3. Allow LAN plain-HTTP

Already configured in the committed `AndroidManifest.xml`
(`android:usesCleartextTraffic="true"`). For a **release** build you must add:

```xml
<uses-permission android:name="android.permission.INTERNET"/>
```

## 4. Connect to the hub (no IP typing)

Open the app → **Setup → Find hub automatically** → tap your laptop when it
appears → green "Connected to the God" card (shows model + databases found).

Manual fallback: **Base URL** = `http://<laptop-lan-ip>:8000`
(emulator on the same machine: `http://10.0.2.2:8000`). **Never `:11450`** —
that's Ollama, and you'll get a confusing 404.

## What works where

| Feature | Needs the hub? |
|---|---|
| Dice (degrees of success, animated die, SFX/haptics) | No — fully offline |
| Character sheet (view/edit/save, export/import) | No — stored on the phone |
| Rules search + browse + Guide chatbot | No — 44,620 entries on-device |
| "Forge with the God", GM chat, generators | Yes |

## For developers

- Offline DB: `spoke/assets/rules/pathfinder_rag.db.gz` extracts on first launch
  to app storage (read-only FTS5). After re-bundling, bump
  `RulebookDb.bundleVersion` or devices keep the stale copy.
- Hub address persists per-device (`hub_base_url`); discovery writes it.
- Something broken? [`troubleshooting.md`](troubleshooting.md) first.
