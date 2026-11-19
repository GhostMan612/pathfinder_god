# Council chain pilot — Pathfinder God

Plain-words version of the loop. The full rules live in `../COUNCIL.md`;
this file is the one to read first.

## The loop

1. **OpenCode builds.** On Glenn's laptop, OpenCode works a task on a
   branch and pushes the branch to GitHub. It never merges, never
   touches `main`.
2. **Phoenix reviews.** A scheduled check on the Muse side looks at
   the new push, reviews the diff against the spec and
   `artifact-chain/review/REVIEW.md`, and writes its findings as a
   dated file in `artifact-chain/review/findings/` — never by editing
   the code under review.
3. **The laptop watcher notices.** `tools/chain-watcher.ps1`, running
   on Glenn's laptop, sees the new findings file and prints the exact
   `opencode` command to run.
4. **Glenn hands the findings to OpenCode.** One command; OpenCode
   reads the findings, fixes them in the same PR branch, runs the
   tests, and pushes again. Back to step 2.
5. **Glenn merges.** When the findings are closed and the gates are
   green, Phoenix presents the PR and Glenn — the only merge
   authority — merges it. No agent merges, ever.

## Why the repo is the wire

Muse and OpenCode do not share memory, a chat, or a private channel.
The only thing both can read and write is this repo: chain artifacts,
the decision log, branches, and PRs. That is deliberate — everything
either agent does is visible in git, and either side can pick the loop
up from the recorded state if the other goes quiet.

## What is installed (pilot)

- `artifact-chain/` — the chain scaffold: `CHAIN.md` (with status
  board), `intent/`, `spec/`, `plan/`, `review/` (guide + findings),
  `decisions/` (log, seeded with D-0001), `templates/`, `evals/`
  (consistency check + fixtures), `hooks/` (proposed hooks, inert).
- `tools/chain-mcp/server.py` — the `sovereign-chain` MCP server,
  byte-identical to the council reference. Six tools: `chain_status`,
  `chain_read`, `chain_append_decision`, `chain_check`,
  `chain_propose`, `chain_review_submit`. See
  `tools/chain-mcp/SPEC.md`.
- `.opencode/opencode.jsonc` — registers `sovereign-chain` alongside
  the existing `pf` (local-grunt) server. OpenCode: `opencode mcp list`
  to verify. Note: the registration uses `python3`, matching the
  council SPEC; on Glenn's Windows laptop, if `python3` is not on
  PATH, change that one word to `python` (the `pf` server already
  uses `python`).
- `tools/chain-watcher.ps1` — laptop-side watcher (script only; run
  it on Glenn's laptop, never from here).
- `COUNCIL.md` (repo root) — roles, turn order, gate rules, and
  bounded autonomy, adapted to this repo.

## What was deliberately NOT installed

- The overlay's blank code skeletons (`skeletons/`) — the repo already
  has its own Kotlin/Python structure.
- The overlay's cold-start triple (`RULES.md`, `SESSION_HANDOFF.md`,
  `CLAUDE.md` templates) — the repo already has `AGENTS.md`,
  `RULES.md`, and `blueprints/`; the overlay versions are blank
  templates with placeholders.
- The chain skills (`skills/`) and `.claude-plugin/` — written for
  Claude Code; this pilot's partners are Muse and OpenCode.
- The CI workflow (`.github/workflows/chain-eval.yaml`) — no workflow
  changes without Glenn's explicit approval (council rule).
- `.mcp.json` / `codex.toml.snippet` — no Claude Code / Codex partner
  in this pilot.

## Triggers — the honest limit

AIs cannot wake each other unaided. This pilot has two triggers and
one fallback:

- **Scheduled poll (Phoenix side).** A cron checks the repo for new
  pushes / open findings and runs the review pass. Coarse interval;
  the check is cheap (`chain_status` + `chain_check`).
- **Laptop watcher (OpenCode side).** `tools/chain-watcher.ps1`
  watches `artifact-chain/review/findings/` and tells Glenn what to
  run. It does not start OpenCode by itself.
- **Human handoff (always works).** Glenn pastes or names the next
  step in chat. The loop must never require anything else to make
  progress.

There is no webhook trigger yet — that is a later pilot step, and it
needs Glenn's approval (it changes repo settings).

## Pilot success criteria

Two full turns with no unsigned contributions, no gate bypassed, no
message sent on Glenn's behalf, and the presentation step delivered
before any merge is requested. The decision log is the evidence.
