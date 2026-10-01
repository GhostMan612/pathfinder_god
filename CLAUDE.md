# Sovereign Mantle - Claude Code Guidelines

You are working on the Sovereign Mantle infrastructure. Absolute precision and architectural perfection are required. Because we are dealing with a massive codebase, deep graph structures, and large data files, **token conservation and context management are your top operational priorities.** 

Follow these workflow rules strictly to prevent context window overloads:

## 1. CLI Execution & Testing
> **RULES.md §1A is canonical.** It defines the intent→tool routing table, the three named traps
> ("just check it compiles", "one quick git status", "one probe"), the blocked-item escape hatch,
> and the PowerShell UTF-8 encoding law. Read it there; do not restate it here.
>
> This clause was the origin of the shell-per-edit habit and has been retired. Specifically
> withdrawn: the `bash run_tests.sh 2>&1 | grep …` recipe. Grepping is the `grep` tool's job, not
> the shell's — the shell is for builds, tests, git, and device commands, batched once per work
> package.

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
*   **NEVER run release builds.** `assembleRelease`, `bundleRelease` and `flutter build appbundle` are forbidden. The debug lane is the boundary; the human installs from Android Studio. Never commit an APK or AAB.
*   **My lane ends at source correctness:** `gradlew assembleDebug` and `gradlew testDebugUnitTest` (host-side) are permitted and expected as code-quality gates. Anything that emits a signed release artifact is out of scope.
*   **Verification hand-off:** After scaffolding code, state what the human should expect when they press Run in Android Studio (e.g., "analyze clean, tests pass; first Gradle sync will download X"). If a build breaks on their side, debug from their pasted error output, never by rebuilding locally.
*   Commit messages must not claim build success — only analyze/test status.