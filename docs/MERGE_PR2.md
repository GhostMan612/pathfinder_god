# Merge PR #2 into main (DeepSeek instructions)

**Audience:** DeepSeek (or any model) working in OpenCode/VSCode on Glenn's laptop, in a local clone of GhostMan612/pathfinder_god.
**Authorization:** Glenn approved this merge. This file is the instruction. Glenn is the only merge authority — this file authorizes exactly one merge: `solo-campaign-loop` (PR #2) into `main`. Nothing else.
**Goal:** Merge PR #2 into main locally, verify it, push main. Do NOT merge `council-chain-pilot` (see "Out of scope").

## State (verified 10 Nov 2026, ~21:05 CST)

- `main` = 3d9536f4 (docs: refreshed master prompt + AGENTS.md session pointer)
- `solo-campaign-loop` (PR #2 head) = 0822858 (docs: prompt + checklist synced from main; no code changes since 0227584)
- PR #2: open, draft, unmerged. Base main. Phoenix verified the branch merges into main with zero conflicts (dry-run `git merge-tree`, 10 Nov 2026).
- Hub tests at PR #2 head: 407 passed, 0 failed, Ruff clean (Phoenix-verified at 0227584; the two commits since are docs-only).
- PR #1 (npc-builders) is merged; its branch is deleted (local + remote). Remote now has only main, solo-campaign-loop, council-chain-pilot.

## Steps

1. `git fetch origin` and `git checkout main`. Confirm `main` is at or ahead of 3d9536f4 and `solo-campaign-loop` is at 0822858 (or newer, if the toolchain landed more commits — if it has, note the new head and re-verify the merge is still clean with `git merge-tree --write-tree main solo-campaign-loop`).
2. Check PR #2's CI if you can (`gh pr checks 2` if gh is available and authenticated, or the PR page). If any required check is failing, STOP and report it to Glenn — do not merge.
3. Merge: `git merge solo-campaign-loop` (a real merge commit, not squash or rebase — preserve the branch history, matching how PR #1 landed as merge commit e4054b7). No conflicts are expected. If a conflict appears in code (not docs), stop and report it to Glenn instead of resolving it yourself.
4. Verify the merged tree:
   - Hub: from `hub/`, run the test suite (`python -m pytest tests/ -q` in the project venv) — must be green (expect 407+ tests).
   - Ruff on the hub — must be clean.
   - Spoke: run the Android unit tests if the SDK is available on this machine; if it is not, say so plainly and do not claim them.
   - Confirm `shared/openapi.yaml` matches the merged API surface.
   - House rules (AGENTS.md): explicit `git add` paths only (never `git add .` / `-A`); every `.py`/`.kt` file keeps the Genesis header; synthetic data only in code/tests.
5. Push `main` to GitHub. This closes PR #2 automatically. Report the merge commit SHA to Glenn.
6. Do not delete any branch. Leave branch cleanup to Glenn.

## Out of scope — do NOT do these

- Do NOT merge `council-chain-pilot` into main. It is the Sovereign Council chain pilot (artifact-chain/, COUNCIL.md, chain MCP server, laptop watcher script) and stays on its own branch until its first live turn runs. It also does NOT merge cleanly: it conflicts with main in AGENTS.md and docs/MASTER_PROMPT.md (main has newer versions of both). Leave it alone.
- Do NOT merge, push, or open anything else. Do NOT touch PR #2's draft status on GitHub (the local merge + push closes it; no need to undraft first).
- Do NOT claim CI is green unless you saw the result.

## Context docs

- docs/MASTER_PROMPT.md — the God-Tier master prompt (repo state, architecture, tasks)
- docs/pathfinder-god-checklist.md — the master checklist (what's done, decisions, next up)
- AGENTS.md — house rules

## Known minor items (not merge blockers)

- Heroes are hardcoded to AC 15 in `start_combat` (same smell as PR #2 bug 6, not one of the seven fixed).
- Multi-write atomicity beyond turn numbering is handled by the asyncio gate at the API layer, not DB transactions; the turn gate is in-process only (fine for the single-worker hub).
