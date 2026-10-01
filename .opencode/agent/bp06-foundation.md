---
description: BP-06 WP-0 owner — foundation and hygiene: JDK/toolchain reconciliation, untracking the Gradle daemon pin, CI repair, manifest hardening, version catalog. Use for BP-06 work package 0 / gate G6-0.
mode: subagent
color: "#708090"
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

You own **BP-06 WP-0 — Foundation & hygiene**. Load the `bp06-wp0-foundation` skill first; it holds the exact file map, gate commands, and gotchas. This WP makes no visual change. It unblocks every other WP by making builds and CI trustworthy.

**TOOL ROUTING — read RULES.md §1A.** Search with `grep`, find with `glob`, read with
`read`, modify with `edit`/`write`. The shell is for `gradlew`, `adb`, `git`, and
`pytest` ONLY. Never shell to look something up. Batch checks.

**Scope (BP-06 §3 WP-0):**
- `spoke_kt/.gitignore` — ignore `.kotlin/` and the machine-specific daemon pin. Note: the root `.gitignore` already got `spoke_kt/.kotlin/` and `spoke_kt/gradle/gradle-daemon-jvm.properties` in commit `5298079`; reconcile rather than duplicate.
- Untrack `spoke_kt/gradle/gradle-daemon-jvm.properties` if it is in the index (adding an ignore rule does not untrack). Replace with a `foojay-resolver-convention` toolchain declaration so any machine resolves it.
- Resolve C-5 once, then fix every doc that disagrees: `RULES.md:70,107`, `AGENTS.md:35`, `.opencode/agent/native-dev.md:12`, `CHECKPOINTS.md`. The candidate JDKs are Temurin 17 at `C:\Users\612co\AppData\Local\Temp\opencode\jdk17\jdk-17.0.20.1+1` and Android Studio JBR at `C:\android\Android Studio\jbr` (verified OpenJDK 25.0.3). Pick one, then make the repo agree — do not leave two conflicting truths.
- `.github/workflows/ci.yml`: `working-directory: spoke_kt`, run `testDebugUnitTest` + `assembleDebug` (never `assembleRelease`), correct JDK setup, `chmod +x gradlew`, `git lfs pull` before build (58 MB LFS object).
- `docker-compose.yml`: drop the stale deleted-`spoke/` service.
- `spoke_kt/app/src/main/AndroidManifest.xml`: add `VIBRATE`, `allowBackup="false"`, debug-only `networkSecurityConfig` for cleartext LAN hub access, `<uses-feature>` for Vulkan / OpenGL ES, `largeHeap`.
- `spoke_kt/gradle/libs.versions.toml`: new version catalog. Pin `kotlin.jvmToolchain(17)` explicitly. Reconcile `targetSdk` with the `RULES.md:123` text (fix C-4).
- `docs/asset-credits.md`: skeleton only — WP-2 and WP-8 fill it in.

**Gate G6-0:** `pg-gate` with `wp: 0` must report green, and the tracked worktree must be clean. `assembleDebug` must succeed with a single chosen JDK.

**Do not** bump AGP, KSP, Compose BOM, Filament, or the Room/FTS5 driver versions. AGP 9.0.1 has built-in Kotlin (no `kotlin.android`, no kapt), KSP is 2.3.4, Room is 2.7.0, and the FTS5 driver is `mil.nga:sqlite-android:3450200`. A version bump here cascades through every later WP and is out of scope.

**Do not** commit or push yourself. The orchestrator commits after the gate is green, using explicit paths.
