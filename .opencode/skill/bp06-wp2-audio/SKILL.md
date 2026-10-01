---
name: bp06-wp2-audio
description: Use when doing BP-06 WP-2 (audio licensing compliance, Audio Credits screen, orphan sound wiring, VibrationEffect haptics, settings toggles) in Pathfinder God — gate G6-2, license obligations, exact assets, gate evidence.
---

# BP-06 WP-2 — Audio licensing compliance + sound/haptic wiring

**First among all feature WPs.** This discharges unmet license terms, not polish.

## Obligations
| Asset | License | Obligation |
|---|---|---|
| `bgm_inn.mp3` | CC BY 4.0 | attribution in-app |
| `dice_crit.wav` | CC BY 3.0 | attribution in-app |
| `tap.wav` | CC BY 3.0 | attribution in-app |

`docs/audio-credits.md` already promises an in-app `Setup → Audio Credits` screen. It does not exist. **Build it first.**

## Files in scope
- `spoke_kt/app/src/main/java/com/pathfindergod/spoke/service/AudioService.kt` (orphans at ~16-21).
- New `Setup → Audio Credits` screen rendering `docs/audio-credits.md`.
- `spoke_kt/app/src/main/res/raw/` — `dice_fail.ogg`, `error.ogg`, `tap.wav`, `bgm_tavern.mp3`, `bgm_inn.mp3`.
- Settings storage — `NetworkPreferences.kt` currently holds one key; add music / SFX / haptics toggles.
- `docs/audio-credits.md`.
- `tools/gen_audio.py`, `tools/fetch_audio.py` (delete or repair — audit A-9, A-10; stale paths, one writes unsafe output).
- Manifest `VIBRATE` comes from WP-0. If it is missing, stop and report.

## The 5 orphans
`tap.wav` → UI clicks, `USAGE_ASSISTANCE_SONIFICATION`. `dice_fail.ogg` → fumble. `error.ogg` → validation. Plus a BGM track picker with crossfade, ducking, and `AudioFocusRequest`.

## Also required
- `OnLoadCompleteListener` so sound never races the roll.
- Randomize pitch ±8%; vary by die size; cascade roll for pools.
- Replace `HapticFeedbackType` misuse with `VibrationEffect` — distinct waveforms for light tick / impact / crit / fumble, honoring the system haptics setting. Add tab-change, button-press, combat-damage feedback.
- Fetch CC0 audio (Kenney, Freesound CC0-filtered, OpenGameArt) and credit it.

## Constraints
Framework `SoundPool` + `MediaPlayer` only. No Oboe. No cloud audio, no API keys.

## Commands
```
pg-gate    { "wp": 2 }
pg-license {}
pg-build   { "action": "assembleDebug" }
```

## Gate G6-2 evidence
```
G6-2: PASS
build:    BUILD SUCCESSFUL
license:  pg-license -> 0 uncredited, 0 orphan media
device:   crit and fumble haptics distinguishable   [HUMAN — mark partial until confirmed]
```
Both in-repo and in-app credit lines are required. One without the other fails.
