# Pathfinder God — Pull Request Workchain
> **Procedure, not an alternative policy.** Canonical source: [RULES.md](../RULES.md) §1.3. When this document differs from RULES.md, RULES.md wins.

## 1. Start a bounded change
1. Read RULES.md, AGENTS.md, the active mission brief, and the relevant source/tests.
2. Fetch current `origin/main`; create ONE scoped branch, e.g. `fix/gateway-deadlock`.
3. Define acceptance evidence, affected files, any dependent PRs and the exact regression test before coding.
4. Implement the complete agreed package; stage only explicit paths. No generated secrets/data or APKs.

## 2. Keep a single PR open through patches
1. Push the branch, open a PR targeting `main` (Draft until implementation and local gates are complete).
2. Attach the rationale, file scope, acceptance tests, results, unverified device evidence, dependency links and known risks.
3. Reviewer findings become new commits on **that same branch**. Do not delete/recreate the PR to clear review history.
4. Re-run the full relevant gates after patching; inspect the GitHub Actions run on the updated head SHA.
5. If another PR touches the same function/file, reconcile against the latest `main` and run the combined regression suite. Avoid force-push/rebase of published history.

## 3. Merge gate (repository owner only)
- Correct head/base branch and no unintended files.
- Hub: `Hub - Tests`, `Hub - Lint`; Android: `Spoke - Unit Tests`, `Spoke - Build Android (debug)`.
- Required checks are green for the current PR revision, with the branch updated against `main`.
- All blocking findings resolved and regression coverage reviewed.
- Cross-PR interactions verified. Native runtime changes require a recorded device smoke test or explicitly recorded waiver.
- Only the owner gives explicit merge approval; no silent direct pushes, auto-merge or deploy. Retain a rejected/unmerged PR for history; delete a merged branch only after confirming the merge and authorization.

## 4. GitHub ruleset (owner/admin action)
In **Settings → Rules → Rulesets**, create an **active branch ruleset** targeting the default branch `main`. Require a pull request; require the four check-run names above; require branches to be up-to-date before merging; require conversation resolution; block force pushes and deletion. Avoid bypass permissions unless deliberately granted and documented. For a solo-maintainer repo, do not require another human approval unless a separate eligible reviewer is available, or you may make merges impossible. The owner makes the final merge decision manually. `Docker Build & Push (Hub)` only runs on `main` pushes: do not require it before merge.

**Important:** Editing repository Markdown does not enforce GitHub branch protection. Verify ruleset enforcement in Settings before calling the workflow 'golden'.

## 5. Existing PR queue (11 November 2026)
PRs #3–#18 were opened independently from `main`, and are **not** all safe to bulk merge. Two direct file-overlap families are #5/#11 (`gateway.py`) and #10/#16 (`portability.py`); #8/#15 both touch combat-start logic. Re-check their current diffs and outcomes before acting; each green PR workflow is only evidence about that PR in isolation.
