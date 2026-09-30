---
name: bp06-wp5-agdk
description: Use when doing BP-06 WP-5 (AGDK for real: AppCompat theme reparent, MainActivity extends GameActivity, explicit frame-rate request, Choreographer tuning) — gate G6-5, launch-crash prerequisite, device readout.
---

# BP-06 WP-5 — AGDK wiring

Requires WP-4 landed. AGDK is currently declared-but-unused, which is worse than absent. Wire it or remove it; the decision is to wire it.

## Launch-crash prerequisite — get this wrong and the app dies
`androidx.games:games-activity`'s `GameActivity` **extends `AppCompatActivity`**. AndroidX requires every such activity to be themed `Theme.AppCompat` or a descendant.

`spoke_kt/app/src/main/res/values/themes.xml:3` currently parents `android:Theme.Material.NoActionBar`. Adopting `GameActivity` without a reparent throws on launch:
```
IllegalStateException: You need to use a Theme.AppCompat theme (or descendant) with this activity
```

So: add `androidx.appcompat`, reparent to a `Theme.AppCompat.NoActionBar` descendant, and **verify on device.** A green build proves nothing here.

## Scope
- `spoke_kt/app/src/main/java/com/pathfindergod/spoke/MainActivity.kt` → `: GameActivity()`, keep `setContent{}`. Forward `onResume` / `onPause` to the pit.
- Request high refresh explicitly: `Window.setFrameRate(120f, FRAME_RATE_COMPATIBILITY_FIXED_SOURCE)` on API 30+, falling back to `Surface.setFrameRate`. **Required** — Android 15+ throttles games to 60 Hz by default unless explicitly asked, so the pit looks like a regression on a 120 Hz panel without it.
- Tune the `Choreographer` swap interval to the display's actual mode. `FrameTiming` / jank telemetry behind a debug flag.
- Update `AGENTS.md:66` and `KOTLIN_PORT_SPEC.md:157-158` to describe what is actually wired.

## No Swappy
Swappy is C++ and needs NDK/CMake, which this lane deliberately avoids. `Window.setFrameRate` achieves the same with zero new build machinery. Keep `androidx.games:games-activity:3.0.5` and `androidx.games:games-frame-pacing:2.1.2` as pinned.

## Never
`flutter` anything — the Flutter spoke is deleted.

## Commands
```
pg-build { "action": "assembleDebug" }
pg-gate  { "wp": 5 }
```

## Gate G6-5 evidence
```
G6-5: PASS
build:    BUILD SUCCESSFUL
launch:   [HUMAN] no IllegalStateException on device
refresh:  [HUMAN] pit holds display max refresh — paste `dumpsys display` / `dumpsys SurfaceFlinger`
docs:     AGENTS.md + KOTLIN_PORT_SPEC.md match code
```
