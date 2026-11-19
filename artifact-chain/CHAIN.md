# The artifact chain

Adapted from Anthropic's AI-native SDLC playbook: each stage produces a
version-controlled, human-readable, machine-actionable Markdown artifact,
acceptance of one artifact triggers the next stage, and human judgment
concentrates at the decision gates.

## Status board

Pilot: Sovereign Council chain in `pathfinder_god` (branch
`council-chain-pilot`, off `main` at `33a969a`). Partners: Muse
(Phoenix, reviewer/gatekeeper) and OpenCode on Glenn's laptop
(builder). Glenn is the only merge authority; nothing merges without
his explicit approval. PR #2 (solo campaign loop) stays draft until he
says otherwise. Current step: pilot install — chain scaffold,
`sovereign-chain` MCP server, and laptop watcher in place; first live
turn not yet run. Next: a real change goes through the loop
(intent → spec → plan → build → review → present) and the decision
log records it. See `PILOT.md` for the loop in plain words and
`../COUNCIL.md` for the roles and gate rules.

## Stages

| Stage | Input | Output artifact | Gate |
|---|---|---|---|
| Plan | Idea, ticket, or alert | `intent/<slug>.md` | Originator accepts the intent |
| Design | Accepted `intent/<slug>.md` | `spec/<slug>.md` | Spec approved |
| Build | Approved `spec/<slug>.md` | `plan/<slug>.md` + diff / PR | Approval authorizes implementation |
| Test | Code changes | Verified diff | Tests / checks named in the plan pass |
| Deploy | PR | Merged commit + record | Review thresholds pass |
| Maintain | Field report / anomaly | New `intent/<slug>.md` | Anomaly exceeds the control band |

Six artifacts in all: intent, spec, plan, the diff with its tests, the
PR with its review findings, and the incident record that opens the
next intent. Version history is the audit trail.

## What each artifact is

- **Intent — the why.** Problem, proposed outcomes, affected users,
  constraints, open questions, non-goals. Anyone can originate one:
  developer, PM, user filing a bug. One per change.
- **Spec — the what.** Technical requirements and expected behavior,
  decisions required, acceptance criteria, risks, explicit non-changes.
  Generated from the intent (by prompt, skill, or agent), applying the
  project's constraints as hard generation requirements.
- **Plan — the how.** Files to change and where, order of work, proof
  per task. The agent works the plan until the checks pass. No
  one-size-fits-all template; the plan template here is a starting shape.

## Three chain variants, and when to use each

1. **SDLC loop (this scaffold, default).** Feature work with real users
   and real verification. Use when the change has a user-facing outcome
   and a checkable result.
2. **dig → clarify → decomposition.** When the requirement itself is
   ambiguous. Artifacts: `decisions.md` → `specification.md` → todos.
   Use to scope something fuzzy before writing a spec; do not jump a
   fuzzy idea straight to implementation.
3. **Plan / Build / Review separation.** Verification-heavy work, or
   changes where a mistake is costly (data mutation, money, deletion,
   security boundaries). Builder and reviewer are different passes; the
   reviewer checks the diff against the spec, not against the builder's
   intentions.

## Skills and hooks

- **Grilling skill** — interviews the originator decision-tree by
  decision-tree until intent and agent share an understanding, then
  writes the intent file. Trigger at the end of the interview.
- **Spec-generation skill** — reads the intent, applies project
  constraints, writes the spec. Trigger: intent accepted.
- **Plan skill** — reads intent + spec, interviews about the repo,
  writes the plan. Trigger: spec approved.
- **Review skill** — applies `review/REVIEW.md`. Trigger: diff ready.
- **Hooks (proposed, see `hooks/`)** — on intent acceptance, draft the
  spec; on spec approval, draft the plan. Hooks propose; humans dispose.
  Nothing here auto-commits, auto-pushes, or auto-merges.

Pilot note: the five chain skills (`skills/`) are NOT installed in
this repo — the pilot partners are Muse and OpenCode, and OpenCode
reads its own skills from `.opencode/skill/`. The review passes
themselves live in `review/REVIEW.md`, which is installed. The
`decision-capture` skill is likewise not installed; reversals are
recorded by hand in `decisions/DECISIONS.md` following
`decisions/README.md`.

## Evals: does the chain still work?

- **Chain-consistency check** (run before any merge; see `evals/`):
  every spec requirement traces to at least one plan task and one check;
  every plan task traces to a spec requirement. Orphans on either side
  are findings. The check runs in CI (`.github/workflows/chain-eval.yaml`)
  against the live chain and against golden-path/broken fixtures, so the
  checker itself is proven on every run.
- **Reversal rule:** an intent edit made after the first spec commit is
  a reversal. Append a dated entry to `decisions/DECISIONS.md` (date,
  author, reason, what it supersedes) via the `decision-capture` skill.
  Do not silently rewrite the old line — the reason for the change of
  mind is the part that gets lost. The original artifact keeps its
  history in version control; the log keeps the history of the mind
  changing.
- **Verification rule:** a claim is only as strong as the check named
  for it in the plan. Code review alone never proves runtime, device,
  or integration behavior.

## Adapting this scaffold

- Put the chain where the project will actually use it: repo root, or
  `docs/artifact-chain/`. Pick one place; don't split the chain.
- Fill in `../COUNCIL.md` with the project's real partners and pilot
  scope (done for this repo — see `PILOT.md`).
- Tighten `review/REVIEW.md` thresholds for the project's real risks
  (data loss, money, safety) — the defaults here are a floor, not a
  ceiling.
- Add project-specific skills under `skills/`; keep shared chain skills
  generic.
- **Install as a plugin instead of copying the folder:** this scaffold
  is packaged as a Claude Code plugin (`.claude-plugin/plugin.json`,
  marketplace catalog at `.claude-plugin/marketplace.json`). Not
  installed in this pilot — no Claude Code partner in this loop.
  See the plugin section in `README.md` for install paths, including
  the zero-install skills-directory option.
