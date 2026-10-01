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

## 1A. CONTEXT, TOOL ROUTING & OUTPUT DISCIPLINE (canonical — CLAUDE.md and every agent prompt defer to this section)

This section is the single source of truth for tool routing and verification timing. If another file
restates it and disagrees, this section wins. Do not copy the table into other files — link here.

> **Legacy section aliases.** Agent frontmatter and comment blocks written before this numbering
> still cite `§1A.0` and `§1A.3a`. Those map to **`§1A.1`** (intent → tool) and **`§1A.5`**
> (encoding hazard) respectively. Treat a `§1A.0` or `§1A.3a` citation as pointing at those two
> sections; no such section exists.

### §1A.1 — Intent → tool. A shell is a build tool, not a search tool.

Decide by **intent**, not by convenience. Map the intent to the tool before touching anything.

| Intent | Tool | Forbidden equivalent |
|---|---|---|
| Search file contents | `grep` | `Select-String`, `grep`, `rg`, `findstr` in a shell |
| Find files by name/pattern | `glob` | `Get-ChildItem`, `ls`, `dir`, `Test-Path` |
| Read a file | `read` | `cat`, `type`, `Get-Content`, `head`, `more`, `tail` |
| Modify a file | `edit` / `write` | `Set-Content`, `Add-Content`, `Out-File`, `sed`, `echo >` |
| Build / unit test / lint | **shell** `gradlew` | — |
| Instrumented test, device | **shell** `adb` | — |
| Version control | **shell** `git` | — |
| Gate tools | `pg-gate`, `pg-repo-guard`, `pg-license`, `pg-build` | — |
| Hub tests | **shell** `pytest` | — |

A shell process is **never** justified for an answer `grep`, `glob`, or `read` can return.

### §1A.2 — The three named traps

These are the exact thoughts that precede a wasted shell call. Each one is a refusal.

1. **"Let me just check it compiles."** — Verification happens **once per work package**, not per
   edit, not mid-implementation. Implement the whole package, then gate it. A build after one edit
   is forbidden. This is not a style preference: BP-06 shipped a work package that did not compile
   precisely because each owner was expected to self-check and none of them could.
2. **"One quick `git status` to see where I am."** — Git is batched at the end of a work package,
   alongside the commit. Not used to re-orient mid-task; you already know what you just edited.
3. **"One probe to see what's going on."** — No `curl`, no live HTTP probe, no `pg-hub-probe`, no
   adb logcat, while implementing. If you believe a probe is required to make progress, that is a
   **blocked item** (§1A.4), not a command to run.

### §1A.3 — Batching

One shell call that checks five related things beats five shell calls. Three failed attempts at a
lookup means the wrong tool was chosen — stop and re-read §1A.1.

### §1A.4 — Blocked-item escape hatch

If a work package genuinely cannot be completed without mid-flight verification, the correct action
is: **write down the blocked item, stop, and report it for a decision.** Do not run the command to
unstick yourself. A reported blocker costs minutes. An unauthorised build costs the lane its
verification discipline and produces unverifiable code that has to be re-derived.

Format: `BLOCKED: <what is blocked> · <the exact command needed> · <why editing alone cannot resolve it>`

### §1A.5 — Encoding hazard (PowerShell 5.1 and friends)

Three common shell habits silently corrupt source on this platform:

- `Get-Content | Set-Content` — round-trips through the console code page (cp1252), turning UTF-8
  box-drawing and em-dashes into mojibake.
- `sed -i` — rewrites line endings and can re-encode the whole file.
- `python -c "..."` piped through PowerShell — the script itself is re-encoded before Python sees it.

**Required instead:** use `edit` / `write` for all source changes. If a Python script is genuinely
needed, write it to `%TEMP%` with `write` and invoke it by path, and inside it always pass
`encoding="utf-8"` and `newline="\n"` explicitly. Never rely on the locale default.

Known live instances of the anti-pattern, fixed by this law rather than by habit:
- `scripts/gen_spec_sheet.py:142` — `gw.read_text()` with no `encoding=`
- `hub/app/db/repository.py:129` — `schema_path.read_text()` with no `encoding=` (reads `schema.sql`,
  which contains non-ASCII; this is a latent crash or corruption on a cp1252 host)

### §1A.6 — Output discipline

- Filter all terminal output; ingest failures only, never passing noise.
- No massive file reads — probe large JSON/data files with short Python scripts instead.
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
- **Spoke** (`spoke_kt/`) — native Kotlin Android app (Jetpack Compose 2D). Owns ViewModels + rendering only: dice, roster, ladder, vaults, journal, oracle. No LLM, no rules logic beyond the bundled FTS5 read path.
- **Contract** (`shared/openapi.yaml`) — Single source of truth for API. Both sides generate from this.

### 5.2 Data & Build Boundaries
- **500MB+ rules DBs** live in `data/` on laptop ONLY. Git-ignored. Never committed — except the raw device extract at `spoke_kt/app/src/main/assets/rules/pathfinder_rag.db` (Git LFS), which ships inside the APK by design.
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
- State via `ViewModel` + `StateFlow`, observed with `collectAsStateWithLifecycle()`; screens organized `ui/<feature>/`, `ui/viewmodel/`, `ui/navigation/`, `ui/theme/`, `data/local/`, `data/network/`, `data/repository/`, `service/`.
- No DI framework: manual constructor injection, screens self-supply ViewModels through `ViewModelProvider.Factory` helpers.
- Retrofit endpoints and WS frames must match `shared/openapi.yaml` byte-for-byte. Hub at `http://10.0.2.2:8000` (emulator) or laptop LAN IP (device) — never `127.0.0.1:11450` (Ollama, laptop-only).
- Theme: `PathfinderGodTheme` + `rpgPanel` (gold/crimson/parchment palette, serif display type).
- Single `:app` module. AGP 9.0.1 built-in Kotlin (no `kotlin.android` plugin, no kapt), KSP 2.3.4 + Room 2.7.0, compile 37 / target 34 / min 26, jvmToolchain 17. `compileSdk` is 37 while `targetSdk` is deliberately held at 34 — they are not required to match, and "compile/target 34" was wrong (BP-06 C-4). All pinned versions live in `gradle/libs.versions.toml`.

### 5.5 API Versioning
- `shared/openapi.yaml` is the contract. Hand-write `@Serializable` Retrofit models in `HubApi.kt` if schema changes; regenerate the doc table in `docs/api.md` to match.
- Backward-compatible additions only. Breaking changes = new versioned endpoint.

---

(End of file)