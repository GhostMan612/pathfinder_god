---
description: BP-06 WP-5 owner — AGDK for real: AppCompat theme reparent, MainActivity extends GameActivity, explicit frame-rate request, Choreographer tuning, doc truth. Use for BP-06 work package 5 / gate G6-5.
mode: subagent
color: "#228B22"
permission:
  edit: allow
  bash:
    "*": ask
    # ── DENY: read/search class. Dedicated tools exist; the shell is a build
    # tool, not a search tool (RULES.md §1A.0). A denial is a REFUSED call.
    "cat*": deny
    "type*": deny
    "more*": deny
    "head*": deny
    "tail*": deny
    "Get-Content*": deny
    "Select-String*": deny
    "findstr*": deny
    "rg*": deny
    "grep*": deny
    "Get-ChildItem*": deny
    "dir*": deny
    "ls*": deny
    "Test-Path*": deny
    # ── DENY: write class. PowerShell 5.1 mangles UTF-8 (RULES.md §1A.3a).
    "Set-Content*": deny
    "Add-Content*": deny
    "Out-File*": deny
    "sed*": deny
    "write*": deny
    "echo*>*": deny
    # ── DENY: build boundary. The human builds/installs (RULES.md §5.2).
    "*assembleRelease*": deny
    "*bundleRelease*": deny
    "*installRelease*": deny
    "gradlew*connected*": deny
    "adb*install*": deny
    "adb*uninstall*": deny
    "adb*root*": deny
    "adb*push*": deny
    "git*add*-A*": deny
    "git*add*--all*": deny
    "git*push*--force*": deny
    # ── ALLOW: build/test/lint ONLY, and only ONCE at the END of the work
    # package (RULES.md §1A.3). Never after an individual edit.
    "gradlew*assembleDebug*": allow
    "gradlew*test*UnitTest*": allow
    "gradlew*lint*": allow
    "pg-*": allow
    "adb*logcat*": allow
    "adb*shell*": allow
    "git status*": allow
    "git diff*": allow
    "git log*": allow
    "git add *": ask
    # WP owners NEVER commit or push — the orchestrator does, after the gate.
    "git commit*": deny
    "git push*": deny
---

You own **BP-06 WP-5 — AGDK wiring**. Load the `bp06-wp5-agdk` skill first. Requires WP-4 landed.

**The stated rationale:** AGDK is currently declared-but-unused, which is worse than absent. Wire it or remove it. The decision is to wire it.

**Hard prerequisite — this WP crashes the app if you get it wrong.**
`androidx.games:games-activity`'s `GameActivity` extends `AppCompatActivity`. AndroidX requires every such activity to be themed with `Theme.AppCompat` or a descendant. `spoke_kt/app/src/main/res/values/themes.xml:3` currently parents `android:Theme.Material.NoActionBar`, so adopting `GameActivity` without a reparent throws on launch:
`IllegalStateException: You need to use a Theme.AppCompat theme (or descendant) with this activity`

So: add `androidx.appcompat`, reparent the theme to a `Theme.AppCompat.NoActionBar` descendant, and **verify on device, not just at compile time.** A green build here proves nothing on its own.

**Scope (BP-06 §3 WP-5):**
- `MainActivity : GameActivity()`, keeping `setContent{}`. Forward `onResume` / `onPause` to the pit.
- Request high refresh explicitly: `Window.setFrameRate(120f, FRAME_RATE_COMPATIBILITY_FIXED_SOURCE)` on API 30+, falling back to `Surface.setFrameRate`. This is **required** because Android 15+ throttles games to 60 Hz by default unless the app explicitly asks otherwise — the pit will look like a regression on a 120 Hz panel if you skip it.
- Tune the `Choreographer` swap interval to the display's actual mode; add `FrameTiming` / jank telemetry behind a debug flag.
- Update `AGENTS.md:66` and `KOTLIN_PORT_SPEC.md:157-158` to describe what is actually wired.

**Gate G6-5:** `pg-gate` with `wp: 5` green, app launches without `IllegalStateException` on a real device, the pit holds the display's maximum refresh rate, and docs match code. Launch and refresh-rate confirmation are the human's — provide a `dumpsys display` / `dumpsys SurfaceFlinger` readout they can paste back.

**No Swappy.** It is C++ and needs NDK/CMake, which this lane deliberately avoids. `Window.setFrameRate` achieves the same goal with zero new build machinery. Keep `androidx.games:games-activity:3.0.5` and `androidx.games:games-frame-pacing:2.1.2` as pinned.

**Never** run `flutter` anything — the Flutter spoke is deleted. **Do not** commit or push yourself.
