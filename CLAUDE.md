# Pathfinder God - Claude Code Guidelines

> ⚠️ This file previously identified itself as "Sovereign Mantle" and referred
> to "unrelated tagger work" — a copy-paste from a sibling repo that was never
> retitled. It is the file the strongest lane rule lives in, so anything loading
> it was getting a wrong-project self-identification on line 1. Fixed 2026-09-30.

You are working on **Pathfinder God** (hub + `spoke_kt/`). Absolute precision and architectural perfection are required. Because we are dealing with a large codebase, deep graph structures, and large data files, **token conservation and context management are your top operational priorities.**

Follow these workflow rules strictly to prevent context window overloads:

## 1. Tool Routing & CLI Execution
> **A shell is a build tool, not a search tool.** Every wasted process is wasted wall-clock and the human's patience. The rule below is ranked and absolute.

*   **RANK 1 — native file tools. These are NOT optional. Use them for ~95% of all work:**
    *   `grep` — ALL content searching. Never `Select-String`, `grep`, or `findstr` inside a shell command.
    *   `glob` — ALL file discovery and path patterns. Never `Get-ChildItem`, `ls`, or `dir` in a shell.
    *   `read` — ALL file reading. Never `cat`, `type`, `Get-Content`, or `head`.
    *   `edit` / `write` — ALL modifications. Never `sed`, `Set-Content`, or heredoc redirection.
*   **RANK 2 — the shell is ONLY for processes with no file-tool equivalent:**
    *   `gradlew` (builds, tests, lint)
    *   `adb` (device)
    *   `git` (status, diff, log, add, commit, push)
    *   `python -m pytest`, `pg-*` gate tools
    *   Network fetches that genuinely need a client.
*   **A shell process is never justified for an answer a `grep`/`glob`/`read` call can return.** If you catch yourself running a shell to look something up, stop and use the tool.
*   **Batch ruthlessly.** One shell call that checks five related things beats five shell calls. Three failing calls is a pattern, not bad luck — re-read the rule above.
*   **Filter All Terminal Output:** Never read massive CLI outputs, full test logs, or raw JSON payloads directly into the main context window. Pipe build output through a failure filter and ingest only the errors.
*   **Stop Reactive Auto-Testing:** Do NOT run the test suite after every minor edit. Build and test verification happens ONCE at the end of a work package, not per edit. Only run the full suite when a phase is complete and staged.

## 2. Context Window & Token Management
*   **Use Native Subagents:** For deep file exploration, large file analysis, or complex stack-trace debugging, you MUST spawn a built-in subagent. Let the subagent isolate the heavy reading and return only a concise, synthesized summary to the main thread.
*   **Proactive Compacting:** Do not wait to be asked. Automatically execute `/compact` to clear dead context after successfully verifying and committing a distinct phase of work, before starting the next commit.
*   **Model Tiering:** Default to the fastest appropriate model (e.g., Sonnet) for routine file edits, standard coding tasks, and CLI commands. Reserve Opus strictly for high-level architectural reasoning and complex refactoring.

## 3. Data Handling
*   **No Massive File Reads:** Do not `cat` or `read` large JSON files (like the legacy master trunk) directly into context. Write and execute short Python scripts to probe, count, and survey data shapes instead.
*   **Synthetic Data Only:** Never include real operator family names or personal data in committed source code or tests. Use synthetic names (e.g., `SAMPLE ANCESTOR A`).

## 4. Git Workflow
*   **Explicit Commits:** Only commit by explicit path (e.g., `git add core/engine/edge_store.py`). Never use `git add .` or `git add -A` to avoid pulling in unrelated tagger work.
*   **Approval:** Wait for explicit approval before running `git commit` and `git push`, unless executing a strictly pre-approved sequential plan.

## 5. Build Boundary — HARD RULE
*   **NEVER run full release builds.** Do not execute `gradlew assembleRelease`, `bundleRelease`, `assembleRelease`/`installRelease`, or any command that produces a signed release artifact. The human runs Install/Run in Android Studio.
*   **My lane ends at a green debug compile.** `./gradlew assembleDebug` in `spoke_kt/` with Temurin 17 via `$env:JAVA_HOME` and `--no-daemon` (daemons get reaped in this shell), plus `./gradlew testDebugUnitTest` for the JVM lane. Instrumented tests (`src/androidTest`) need a device and are HUMAN territory. This mirrors RULES.md §5.2.
*   **Hub lane ends at `pytest hub/tests/`.**
*   **Verification hand-off:** After scaffolding code, state what the human should expect when they press Run in Android Studio (e.g., "assembleDebug green; first launch copies the 19MB rulebook out of assets"). If a build breaks on their side, debug from their pasted error output, never by rebuilding release locally.
*   **Green compile is not a working app.** Device-only contracts (AppCompat theme under `GameActivity`, high-refresh request, Filament pit attach, live-region announcements) are checked on hardware, not in CI. Report them as HUMAN, never as verified.
*   Commit messages must not claim build success — only compile/test status.