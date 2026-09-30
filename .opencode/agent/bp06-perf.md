---
description: BP-06 WP-6 owner — performance, leaks and dice correctness: list keys, OkHttp singleton, off-main-thread image decode, Compose read-in-write, dice crit bug, dice pools, exploding dice, DiceViewModel. Use for BP-06 work package 6 / gate G6-6.
mode: subagent
color: "#FF8C00"
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

You own **BP-06 WP-6 — Performance, leaks & dice correctness**. Load the `bp06-wp6-perf` skill first. WP-4 (Filament) assumes this WP landed.

**Scope (BP-06 §3 WP-6):**
- Add `key` to the `DiceScreen.kt:213` history list; audit every other `items(...)` call for the same defect.
- Hoist `HubApiFactory` to a process-scoped singleton sharing one `OkHttpClient`; shut it down on exit. This removes per-tab TLS setup and the per-navigation leak that `NavigationShell` triggers.
- Move map Base64 decode off the main thread with `inSampleSize` downsampling.
- Fix `CombatantCard.kt:181` to read `rise.value` inside `graphicsLayer` — reading a `State` during write invalidates the whole recomposition scope.
- `remember` the `Paint` and `Path` in `DiceCanvas`; correct the inverted number scale; coordinate the drop and spin springs.
- Debounce FTS5 search (~250 ms); add fling and bounds clamping to the map viewer.
- **Dice correctness:** fix nat-20 / nat-1 crit detection under advantage (P-3 — the current logic misclassifies an advantage crit); fix the `impactLabel` separator (P-4); wire dice pools, modifiers, and `kh` / `kl` into the UI (P-5); add Pathfinder-appropriate exploding dice (`d6!!`) and 2e degree-of-success; show dropped dice; persist history to Room; remove the dead `_history` / `history` duplication (P-6).
- Extract `DiceViewModel` so `DiceScreen` stops owning engine + audio + state (P-13).

**Gate G6-6:** `pg-gate` with `wp: 6` green. `DiceEngineTest` must be extended to cover advantage crits, pools, modifiers, and exploding dice — a green build with unchanged tests is **not** a pass. Confirm no main-thread image decode and no per-roll history re-animation remain.

**Ordering note:** land the correctness fixes and their tests before the refactor-heavy items, so a regression is bisectable. `DiceViewModel` extraction is the last thing, not the first.

**Do not** commit or push yourself.
