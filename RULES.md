# RULES.md — Pathfinder God Operating Law
> **CANONICAL RULESET.** Every session MUST read this file before doing any work.
> If any other document contradicts this file, THIS FILE WINS.

---

## 1. ABSOLUTE RULES (never violated, no exceptions)

### 1.1 External directories are READ-ONLY
Never create, modify, move, or delete ANYTHING under these paths:
```
C:\sovereign_tagger_bak
C:\Recovery for All
C:\Sovereign Nodes
C:\sovereign_mantle
C:\sovereign_tagger_2
```
- Reading and copying FROM them into `C:\pathfinder_god` is allowed.
- Approved Python environment: use `C:\venv-hub` AS-IS (`C:\venv-hub\venv\Scripts\python.exe`, Python 3.14.6) — never copy it into the project; installing packages INTO it is allowed.
- The ONLY writable work area is `C:\pathfinder_god` (plus user-approved tool homes: `C:\Doom Shit`, usage of `C:\android`, `C:\ZDaemon`, `%USERPROFILE%\.gradle` caches).
- When in doubt: copy out, edit inside.

### 1.2 Secrets and commercial data never enter the repo
- Never commit: `.env`, API keys, keystores (`*.keystore`, `debug.keystore`), `local.properties`.
- Commercial IWADs (DOOM2.WAD etc.) live ONLY outside the repo at `C:\Doom Shit\IWADs\`. Never copy them into `C:\pathfinder_god`.

### 1.3 Git discipline
- **Stage by explicit path only.** `git add -A` / `git add .` are FORBIDDEN — they pull in unrelated work.
- Commits happen as part of an approved session workflow; never force-push, rebase public history, or delete branches unless explicitly asked.
- `blueprints\` and `_archive\` are intentionally gitignored — do not "fix" this.

### 1.4 Synthetic data only
Never include real operator family names or personal data in committed source code, tests, or fixtures. Use synthetic placeholders (e.g., `SAMPLE ANCESTOR A`). Real genealogy JSON under `MantleBridge\` (events/graph/ledger/game_state.json) is **gitignored** — it exists on disk for the game to read, never in history.

### 1.5 Nothing outside the project without approval
Do not install software, modify system settings, or write to new locations outside `C:\pathfinder_god` / approved tool homes without asking the user first.

---

## 1A. CONTEXT, TOOL ROUTING & OUTPUT DISCIPLINE (from CLAUDE.md)

**§1A.0 — ⛔ THE SHELL GATE. Read this before you touch anything.**

Added 2026-09-30 after a full audit found this repo's agent library *teaching*
mid-plan shelling in four places at once. Three of them were live, dispatchable
agent definitions. **The problem was never discipline — it was that the
documents said the wrong thing.** An agent following this file literally was
being told to run a gate after every edit, and then being told elsewhere not to.

**The rule, and it is a hard gate:**

> **During a plan, the shell must not be called at all.**
> Not once. Not "just to check one thing". Not "to see if it compiles".
>
> The plan is not finished, so there is nothing to verify *for*. Verification is
> an **end-of-plan** activity. Calling it early does not make the work safer —
> it makes it slower, and it produces **stale signal** that you then have to
> re-derive when the plan actually ends.

**Route every intent to a tool. There is no judgment call here:**

| You want to… | Use | NEVER |
|---|---|---|
| See a file, a block, line numbers, a value | `read` | `type`, `cat`, `Get-Content`, `head`, `tail` |
| Find where a symbol is defined or used | `grep` | `Select-String`, `rg`, `grep`, `findstr` |
| Find a file by name | `glob` | `Get-ChildItem`, `ls`, `dir` |
| Change text in a file | `edit` | `Set-Content`, `sed -i`, `Out-File`, `>>` |
| Create a file | `write` | `New-Item`, heredoc, `echo >` |
| Audit the repo for a pattern | `grep` + subagents | shell loops |
| Check whether a directory exists | `glob` / just `read` it | `Test-Path` |
| **Does it compile? Do tests pass?** | **NOTHING — queue it** | the shell |
| **`git status` / `diff` / `commit`** | **NOTHING — queue it** | the shell |
| **`adb` / screenshots / device probes** | **NOTHING — queue it** | the shell |
| **`pg-hub-probe` / any probe tool** | **NOTHING — queue it** | the shell |

**The three traps, named — because all three happened here:**

1. **"Let me just check it compiles."** It tells you nothing you cannot get by
   `read`ing the enclosing block, and it costs 20–90s *every* time. The compiler
   is blind to the bug classes this repo actually has (a wrong string, a shadowed
   listener, a two-owner state value). It has never caught one.
2. **"One quick `git status`."** Git is a shell command, and the answer does not
   change the next edit. Batch it into the single end-of-plan commit.
3. **"One probe to see what's going on."** Every probe tool — `pg-hub-probe`,
   `atlas_*`, adb — is *verification*, and verification is end-of-plan. Queue the
   whole checklist, then do it once in one pass.

**Batching is the entire point.** A correct plan in this repo is:
`read → edit → read → edit … for the whole WP`, then **one** shell block at the
end containing the gate, the repo guard, the device checklist, and the commit.

**The escape hatch, so the rule can never create a deadlock:**
> If the rule feels like it is costing correctness — a plan that genuinely cannot
> be completed without mid-flight verification — **that is the signal to report a
> blocked item and wait for the operator, not to run the command.**

**Machine-enforced, not just prose:** `.opencode/opencode.json` (or the agent
frontmatter `bash:` block) must `deny` the read/search/edit shell commands above.
A denial means the call is *refused*, not that a warning prints. Prose without a
deny is a suggestion.

**§1A.1 — A shell is a build tool, not a search tool.** This is ranked and absolute:

| Need | Use | NEVER |
|---|---|---|
| Search file contents | `grep` tool | `Select-String`, `grep` in a shell |
| Find files by pattern | `glob` tool | `Get-ChildItem`, `ls`, `dir` |
| Read a file | `read` tool | `cat`, `type`, `Get-Content`, `head` |
| Modify a file | `edit` / `write` | `sed`, `Set-Content`, heredoc |
| Build / test / lint | **shell** (`gradlew`) | — |
| Device | **shell** (`adb`) | — |
| Git | **shell** (`git`) | — |
| Hub tests | **shell** (`pytest`) | — |

A shell process is **never** justified for an answer that `grep`, `glob`, or `read` can
return. Three failed attempts at a lookup means the wrong tool was chosen.

**§1A.2 — Batch.** One shell call checking five related things beats five shell calls.
Batching is not optional; it is the difference between minutes and hours.

**§1A.3 — Verification timing. THIS IS THE RULE THAT WAS BEING UNDERMINED.**

Build, test, and lint run **once at the end of a work package** — never after an
individual edit, and never mid-implementation. Implement a whole WP first, then
gate it. Do not interleave builds with edits.

Why this matters more than it looks: this repo shipped a **whole work package
non-compiling** because the WP owner wrote `NavigationGraph.kt` without compiler
feedback. The temporal rule was right; nothing told the agent *what to do instead*
of shelling mid-flight. So, explicitly:

- Fix what you can see with `read`/`grep`/`edit` first. Then gate once.
- A gate failure is **one batch of errors**. Read all of it, fix all of it, gate again.
  Re-running the gate to inspect a single line is the most expensive habit here.
- If a plan cannot be self-verified without a mid-flight build, **say so and wait**
  (§1A.0 escape hatch). Do not quietly shell.

**§1A.3a — ⛔ Never round-trip source through a shell.**

PowerShell 5.1 decodes UTF-8 as ANSI when there is no BOM, then writes it back
double-encoded. This silently destroys `—`, `·`, `•`, `✓`, and emoji in any file
it touches. The console showing `Ã°Å¸` afterwards is **display-only** — the file on
disk is already corrupt.

- **NEVER** edit source via `Get-Content | -replace | Set-Content`, `Out-File`,
  `Add-Content`, `sed -i`, or `[IO.File]::WriteAllText` re-encoding. Banned.
- Bulk edits go through `edit`, or a `write` of the whole file.
- If you must script it: write a `.py` to the temp dir and run it with explicit
  `io.open(..., encoding="utf-8", newline="\n")`.
- **Do NOT write `python -c "..."` through PowerShell.** The quoting gets mangled by
  the outer shell and the file gets corrupted. This is not a theoretical risk.
- `python -c` is fine for *reading/probing* (line counts, keyword frequency) where
  nothing is written. It is banned for anything that *writes*.
- Verify with a strict Python read, not with the terminal.

**§1A.4 — Output discipline.**
- Filter all terminal output; ingest failures only, never passing noise.
- No massive file reads — probe large JSON/data files with short Python scripts.
- Spawn subagents for deep exploration; return summaries, not raw dumps.
- Proactively compact context after each verified+committed phase.

---

## 2. PROJECT CONVENTIONS (The Sovereign Directives)

1. **Full code only** — no partial snippets, no TODO stubs.
2. **No comments in code** — except the Genesis header every `.py`/`.kt` file must carry:
   ```
   // ============================================================
   // As Above, So Below. As Within, So Without.
   // The Future Dictates the Past and the Past is Always Present.
   // ============================================================
   ```
   (Use `#` for Python files.)
3. **Deterministic tables are canon** for gameplay numbers (hub XP/DC/rune/adjustment tables, never LLM memory); lore/systems flavor follows `docs\WHITEPAPER_ARCHITECTURE_v1.md`.

---

## 3. TECHNICAL LAWS (learned the hard way — see CHECKPOINTS/gotchas G1–G20)

| Law | Rule |
|-----|------|
| Long builds | Launch DETACHED (no `-Wait`) and poll logs — tool timeouts kill child processes. `Start-Process` on `.bat` may throw a cosmetic harness error; poll logs, don't trust it. |
| Native builds | Build via user's env (`local.properties` → `C:\android\sdk`, cached Gradle dists, Temurin JDK 17 in temp). **Temurin 17 is THE lane JDK**, pinned in `app/build.gradle.kts` via `kotlin.jvmToolchain(17)` and resolved on any machine by the foojay resolver in `settings.gradle.kts`. Correction (BP-06 C-5): Android Studio's bundled JBR is **not** stripped — `C:\android\Android Studio\jbr\bin\java.exe` is a working OpenJDK 25.0.3. It is still not the lane JDK, because Temurin 17 is what the lane and CI actually use; the point is that JBR works and is a *choice*, not a *forbidden path*. |
| API names | Verify API/artifact names against package sources, not memory (`io.requery:sqlite-android` does not exist on Central; the maintained fork is `mil.nga:sqlite-android`). |
| SQLite platform gap | Android's platform SQLite has no FTS5 — offline rules search must go through an FTS5-capable driver (native: NGA bindings via `NgaSQLiteOpenHelperFactory`), never the platform default. |
| Green compile ≠ working app | Some contracts are only checked on device. `Theme.PathfinderGod` parenting an AppCompat theme while `MainActivity : GameActivity` throws `IllegalStateException` on launch, not at compile. Anything that reads a theme, a window, a display mode, or a sensor is **HUMAN/DEVICE territory** — say so in the gate rather than claiming `assembleDebug` proves it. |

---

## 4. WORKFLOW LAW

### 4.1 Cold start (every session, in order)
1. Read `blueprints\SESSION_HANDOFF.md`
2. Read THIS file (`RULES.md`)
3. Read `blueprints\CURRENT_STATE.md` → `CHECKLIST.md`
4. Work from the relevant `blueprints\blueprint-sections\BP-*.md`

### 4.2 Session end (every session)
1. Update `blueprints\CHANGELOG.md` (top entry, dated)
2. Tick `blueprints\CHECKLIST.md`; flip gates in `blueprints\CHECKPOINTS.md`
3. Refresh `blueprints\CURRENT_STATE.md`; rewrite handoff "Where we are" + "Next actions"
4. Commit code with a descriptive message (never commit `blueprints\`)

### 4.3 Verification law
No checklist item is done until its checkpoint gate passes (see `blueprints\CHECKPOINTS.md`). Evidence before status flips. New work → define its gate first.

### 4.4 Scope law
Big dreams go into blueprint sections with phased plans first. Ship vertical slices; never let polish precede a passing play-test gate.

---

## 5. PROJECT-SPECIFIC LAWS (Pathfinder God)

### 5.1 Hub-Spoke Architecture
- **Hub** (`hub/`) — Python FastAPI + Ollama + RAG service. Runs on laptop. Heavy lifting (LLM + retrieval).
- **Spoke** (`spoke_kt/`) — native Kotlin Android app. Jetpack Compose UI plus **one** first-party native render surface: the Filament dice pit (`ui/pit/`, WP-4 — lit shading, directional key light + IBL, shadow-mapped ground). Everything else is Compose. Owns ViewModels + rendering only: dice, roster, ladder, vaults, journal, oracle. No LLM, no rules logic beyond the bundled FTS5 read path.
- **Contract** (`shared/openapi.yaml`) — Single source of truth for API, **26 paths**. Both sides build against this.

### 5.2 Data & Build Boundaries
- **500MB+ rules DBs** live in `data/` on laptop ONLY. Git-ignored. Never committed — except the raw device extract at `spoke_kt/app/src/main/assets/rules/pathfinder_rag.db` (Git LFS), which ships inside the APK by design. It is a **raw `.db`, never `.gz`**: AGP decompresses gzipped assets at build time and renames the entry, which breaks `DatabaseAssetManager`'s runtime open path.
- **Native lane verification is `./gradlew assembleDebug`** in `spoke_kt/` (Temurin 17 via `$env:JAVA_HOME`, always `--no-daemon` — daemons get reaped in this shell). It is required before any native commit. Lane JDK is Temurin 17 at `C:\Users\612co\AppData\Local\Temp\opencode\jdk17\jdk-17.0.20.1+1`, pinned in `app/build.gradle.kts` (`kotlin.jvmToolchain(17)`) and auto-resolved by foojay on any machine. The machine-generated `gradle/gradle-daemon-jvm.properties` is gitignored and untracked — never commit it.
- **No release artifacts.** Never commit APKs/AABs. The human runs Install/Run in Android Studio; agents stop at a green debug compile.
- **Verification hand-off:** After scaffolding code, state what the human should expect when they press Run in Android Studio (e.g., "assembleDebug green; first launch extracts the 20MB rulebook"). If a build breaks on their side, debug from their pasted error output, never by rebuilding release locally.

### 5.3 Python Hub Conventions
- FastAPI + `uvicorn` for serving.
- Local-only 2-tier LLM fallback, in order: local Ollama → raw FTS5 excerpts (always works, no LLM). No cloud tiers — no API keys leave the laptop.
- SQLite for campaign state; SQLite FTS5 (`data/pathfinder_rag.db`) for rules RAG. No vector store — do not add Chroma/Qdrant without a blueprint gate.
- All hub code under `hub/` — keep it separate from the spokes.
- New endpoints must not be shadowed by earlier-registered routes (FastAPI matches in order — see the `/generate/loot` vs `/{kind}` outage).

### 5.4 Native Kotlin Spoke Conventions
- State via `ViewModel` + `StateFlow`, observed with `collectAsStateWithLifecycle()`; screens organized `ui/<feature>/`, `ui/viewmodel/`, `ui/navigation/`, `ui/theme/`, `ui/designsystem/`, `data/local/`, `data/network/`, `data/repository/`, `service/`.
- **UI primitives are the `God*` design system** in `ui/designsystem/` (BP-06 WP-1): `GodCard` / `GodChip` / `GodTextField` / `GodPrimaryButton` / `GodFab` / `GodBackLink` / `GodBadge` / `GodSectionHeader` / `GodStatusText` / `GodStatTile` / `GodProgressBar` / `GodEmptyState` / `GodLiveRegion`, plus `Dimens`/`Spacing`. **`Modifier.rpgPanel` is a deprecated shim with zero call sites — do not use it.** Haze was evaluated and rejected (it would drag the pinned Compose BOM forward); `GlassCard` ships Haze-free. User-facing text lives in `res/values/strings.xml` — no hardcoded literals.
- **Accessibility is part of the contract** (BP-06 WP-7): 48dp touch floors via `Dimens`, `pg:<area>:<element>` `testTag`s from `GodTags`, `Role`/`stateDescription` on cards/chips/switches, and `GodLiveRegion` for the 17 events that change without a focus change (roll outcome, crit success/failure, 2e degree, damage, heal, HP-0, turn/round, screen change, encounter mustered, loot forged, search results, map count, hub link state).
- No DI framework: manual constructor injection, screens self-supply ViewModels through `ViewModelProvider.Factory` helpers. `HubApiFactory` is a process singleton over one shared `OkHttpClient`.
- Retrofit endpoints and WS frames must match `shared/openapi.yaml` byte-for-byte. Hub at `http://10.0.2.2:8000` (emulator) or laptop LAN IP (device) — never `127.0.0.1:11450` (Ollama, laptop-only).
- **Theme:** `PathfinderGodTheme` (gold/crimson/parchment, serif display type) over `ui/designsystem/` and `ui/theme/`. `Theme.PathfinderGod` must parent a **`Theme.AppCompat` descendant** in both `res/values/themes.xml` and `res/values-v31/themes.xml` while `MainActivity : GameActivity` (BP-06 WP-5) — a platform `android:Theme.Material` parent compiles clean and then throws `IllegalStateException` on launch. **A green `assembleDebug` does not prove this.**
- Single `:app` module. AGP 9.0.1 built-in Kotlin (no `kotlin.android` plugin, no kapt), KSP 2.3.4 + Room 2.7.0, compile 37 / target 34 / min 26, jvmToolchain 17. `compileSdk` is 37 while `targetSdk` is deliberately held at 34 — they are not required to match, and "compile/target 34" was wrong (BP-06 C-4). All pinned versions live in `gradle/libs.versions.toml`.
- **Unit tests are JUnit 4** (`junit 4.13.2`, `testImplementation(libs.junit)`). There is **no** Turbine, Robolectric, MockWebServer or JUnit 5 in this lane — do not write a gate that assumes them. Instrumented tests live in `src/androidTest` and need a device/emulator.

### 5.5 API Versioning
- `shared/openapi.yaml` is the contract. Hand-write `@Serializable` Retrofit models in `HubApi.kt` if schema changes; regenerate the doc table in `docs/api.md` to match.
- Backward-compatible additions only. Breaking changes = new versioned endpoint.

---

(End of file)