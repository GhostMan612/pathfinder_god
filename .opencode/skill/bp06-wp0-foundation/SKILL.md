---
name: bp06-wp0-foundation
description: Use when doing BP-06 WP-0 (foundation, toolchain, CI, manifest, version catalog) in Pathfinder God spoke_kt — gate G6-0, exact files, JDK decision, CI repair steps, and gate evidence format.
---

# BP-06 WP-0 — Foundation & hygiene

No visual change. Makes every later WP's build and CI trustworthy.

## Files in scope
- `spoke_kt/.gitignore` (create) — but root `.gitignore` already got `spoke_kt/.kotlin/` and `spoke_kt/gradle/gradle-daemon-jvm.properties` in commit `5298079`. Reconcile, do not duplicate.
- `spoke_kt/gradle/gradle-daemon-jvm.properties` — untrack if indexed; an ignore rule does not untrack. Check with `git ls-files spoke_kt/gradle/gradle-daemon-jvm.properties`.
- `spoke_kt/gradle/libs.versions.toml` (create).
- `spoke_kt/build.gradle.kts`, `spoke_kt/app/build.gradle.kts`.
- `spoke_kt/app/src/main/AndroidManifest.xml`.
- `.github/workflows/ci.yml` lines ~30-58.
- `docker-compose.yml` — drop the stale deleted-`spoke/` service.
- `docs/asset-credits.md` (skeleton only).
- Docs to correct after the JDK decision: `RULES.md:70,107,123`, `AGENTS.md:35`, `.opencode/agent/native-dev.md:12`, `CHECKPOINTS.md`.

## Tasks
1. Ignore hygiene: `.kotlin/`, the daemon pin.
2. Untrack the daemon pin; replace with `foojay-resolver-convention` so any machine resolves the toolchain.
3. Resolve the JDK contradiction **once**, then make all four docs agree. Candidates: Temurin 17 at `C:\Users\612co\AppData\Local\Temp\opencode\jdk17\jdk-17.0.20.1+1`, or Android Studio JBR at `C:\android\Android Studio\jbr` (verified OpenJDK 25.0.3). Do not leave two conflicting truths.
4. CI: `working-directory: spoke_kt`; run `testDebugUnitTest` + `assembleDebug`; **never** `assembleRelease`; correct JDK setup; `chmod +x gradlew`; `git lfs pull` before build (58 MB LFS object).
5. Manifest: add `VIBRATE`; `allowBackup="false"`; debug-only `networkSecurityConfig` for cleartext LAN hub; `<uses-feature>` Vulkan / OpenGL ES; `largeHeap`.
6. Version catalog + explicit `kotlin.jvmToolchain(17)`; reconcile `targetSdk` with `RULES.md:123` (audit C-4).
7. `docs/asset-credits.md` skeleton.

## Commands
```
pg-gate      { "wp": 0 }
pg-build     { "action": "assembleDebug" }
pg-build     { "action": "testDebugUnitTest" }
pg-repo-guard
```

## Do not bump
AGP 9.0.1 (built-in Kotlin — no `kotlin.android`, no kapt), KSP 2.3.4, Room 2.7.0 (2.6.1's processor crashes on new Kotlin), Compose BOM 2024.10.01, Filament 1.76.0, `mil.nga:sqlite-android:3450200` (`io.requery:sqlite-android` does not exist on Central). Min SDK 26.

## Gotchas
- `spoke_kt/local.properties` is gitignored and holds `sdk.dir=C:\android\sdk`. Never commit it.
- The manifest keeps `tools:replace="android:label"` because the sqlite-android AAR declares its own label. Preserve it.
- Gradle daemons get reaped in this shell; always `--no-daemon`.

## Gate G6-0 evidence
```
G6-0: PASS
build:      BUILD SUCCESSFUL (assembleDebug, single chosen JDK)
tests:      testDebugUnitTest green
ci:         Android job green on spoke_kt
tree:       no untracked files, tracked worktree clean
```
