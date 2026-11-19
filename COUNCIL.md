# The Sovereign Council — Pathfinder God pilot

Version: 0.1.0 (council design). Companion: `tools/chain-mcp/SPEC.md`
(the wire) and `artifact-chain/PILOT.md` (the loop in plain words).
This is the council loop adapted to this repo. Nothing here changes
the chain's gates; it assigns the passes to different agents and
states what each pass may do alone.

## The partners

- **Muse (Phoenix)** — reviewer and gatekeeper. Reviews diffs,
  writes findings, runs the machine gates, presents to Glenn.
- **OpenCode on Glenn's laptop** — builder (and drafter). Implements
  approved plans on branches, fixes findings in the same PR.
- **Glenn** — the only merge authority, and the only approver of
  specs. Nothing merges, pushes to `main`, or ships without his
  explicit say-so.

No partner shares memory, state, or a chat session with any other.
The only shared state is the repo: chain artifacts, decision log,
branches, and PRs. That is deliberate — shared files are the one
medium every partner already reads and writes, on any device, offline
included.

Notion is not part of this loop. It may mirror a finalized chain later
as a read-only board; it is never the source of truth.

## Pilot scope

This repo only. Pilot branch: `council-chain-pilot`. Live work stays
where it is: **PR #2 (solo campaign loop) stays draft until Glenn says
otherwise**, and the pilot does not touch Atlas PR #1 or Tagger `main`
— those are explicitly out of scope for any council pilot.

## Roles

Four roles. A role is a pass with a job and a signature, not a person
or a fixed model. The same model may fill different roles on different
passes, but never two roles on the same pass.

- **Drafter.** Writes the next artifact: intent from an idea, spec
  from an accepted intent, plan from an approved spec. Works only from
  the governing artifact and cited evidence. Signs every file it
  writes.
- **Reviewer.** Checks a finished artifact or diff against the
  governing artifact and `artifact-chain/review/REVIEW.md`. Writes
  findings only — dated files under `artifact-chain/review/findings/`
  via `chain_review_submit` (or the equivalent manual path). Never
  edits the artifact under review, never edits `REVIEW.md` itself,
  never approves its own review.
- **Builder.** Implements an approved plan, task by task, fixing
  reviewer findings in the same PR. Owns the diff and its tests.
- **Gatekeeper.** Runs the machine gates (`chain_check`, CI evals)
  and assembles the presentation. Usually the agent closest to Glenn
  (the one presenting), and it never approves its own build.

**The reviewer pass must differ from the builder pass.** Different
agent session, different model, or different harness — at minimum a
fresh context that has read the spec and the diff but did not write
the diff. A builder reviewing its own work is not a review; it is a
re-read.

## Turn order

One change, one chain, in order. No step starts until the previous
gate is recorded.

1. **Originate.** Any partner (or Glenn) opens an intent with
   `chain_propose` or the equivalent manual write. Status DRAFT.
   Glenn accepts the intent, or the drafter records why it is
   deferred. Acceptance is a human act.
2. **Draft spec.** Drafter writes `spec/<slug>.md` (DRAFT). Reviewer
   checks it against the intent: every problem addressed, every
   constraint honored, decisions required listed, acceptance criteria
   checkable. Findings go to `review/findings/`. Builder fixes.
3. **Approve spec.** Glenn approves the spec. Approval authorizes
   implementation task by task; the plan draft alone authorizes
   nothing.
4. **Draft plan.** Drafter writes `plan/<slug>.md` (DRAFT). Reviewer
   checks traceability (`chain_check` green is necessary, not
   sufficient) and proof per task. Findings, fixes, same loop.
5. **Build.** Builder implements on a branch, in a PR, fixing
   findings in the same PR. The machine gates run: `chain_check` and
   the repo's own gates (`pytest hub/tests/` green for hub work,
   `assembleDebug` green for native work — see `AGENTS.md`).
6. **Review the diff.** Reviewer pass (different from builder) checks
   the diff against the spec, the safety paths, the native boundary,
   failure behavior, and docs — the `review/REVIEW.md` passes. P0
   findings block. P1 findings block unless Glenn defers one with a
   recorded reason. P2 findings are fixed or filed as a dated note.
7. **Present.** Gatekeeper assembles the PR plus a chat summary:
   what changed, what was verified and how, what is still unproven,
   what needs Glenn. Glenn is the merge gate. Nothing merges on a
   green check alone.
8. **Maintain.** A field report or anomaly opens a new intent. The
   loop restarts; the old chain stays readable in version history.

Re-entries: any partner may re-enter at the step whose artifact is
stale, but must say which step and why in the decision log. Silent
re-entry is a finding.

## Triggers — the honest limit

AIs cannot wake each other unaided. Every autonomous step needs a
trigger, and the trigger must be built, not assumed:

- **Scheduled poll (this pilot).** A cron on the Muse side checks the
  repo for new pushes / open findings and runs the review pass. Keep
  the interval coarse and the check cheap (`chain_status` +
  `chain_check` only).
- **Laptop watcher (this pilot).** `tools/chain-watcher.ps1` watches
  `artifact-chain/review/findings/` on Glenn's laptop and prints the
  exact `opencode` command to hand the findings to OpenCode. It does
  not start OpenCode by itself.
- **Human handoff (always available).** Glenn pastes, forwards, or
  names the next step in chat. This is the trigger that always works,
  including on mobile, and the loop must never require anything else
  to make progress.
- **GitHub event (later pilot step).** A push, PR open/synchronize,
  or review comment fires a webhook or scheduled workflow that wakes
  an agent with the event payload. Not built yet — it changes repo
  settings and needs Glenn's approval first.

What is NOT a trigger: one AI sending another AI a message in some
private channel. No such channel exists in this build, and inventing
one would hide the audit trail. Everything a partner does must be
visible in the repo or in Glenn's chat.

## Signing convention

Every contribution carries three facts, in the artifact and in the
decision log: **Author** (e.g. `muse`, `opencode`, `Glenn`),
**Model** (as reported by the harness; `unknown` is honest when the
harness does not report one — inventing a model name is a finding),
**Timestamp** (UTC, ISO 8601). The decision log's `Signature:` bullet
is the canonical record; the `sovereign-chain` server writes it
automatically on `chain_append_decision`. A contribution without a
signature is unsigned evidence: readable, but not counted toward any
gate.

## Gate rules

- `chain_check` green is required before a plan is built and before a
  PR merges. A red gate blocks; it is never waved through by the agent
  that produced the red state.
- All review findings are closed or explicitly deferred by Glenn with
  a reason recorded in the decision log. "Deferred" without a reason
  is open.
- Glenn approves the merge. No agent merges, pushes to `main`,
  force-pushes, or approves its own PR.
- The chain's own rules still apply: explicit-path git only, no
  committed secrets, synthetic data only in fixtures, Genesis header
  on new `.py`/`.kt` files, and "prove the gate can go red" — every
  new check ships with a fixture or case that fails without it.
  - One exception, recorded here: `tools/chain-mcp/server.py` is
    byte-identical to the council reference implementation and
    carries no Genesis header, because adding one would break the
    byte-identity the SPEC requires. The file's own header is its
    stdlib docstring.
- A red gate, a failed check, or a reviewer finding never deletes
  work. Findings are fixed in the same PR or recorded as deferred
  with a reason. Deleting a finding file is a P0.

## Bounded autonomy

AIs may do alone, without asking Glenn:

- Draft intents, specs, and plans; run checks; write findings.
- Open draft PRs on branches; push branch commits the PR needs.
- Fix reviewer findings in the same PR.
- Record decisions that the evidence compels (a check result, a
  verification outcome), signed.

AIs must not do without Glenn's explicit approval:

- Merge, approve, or close a PR; push to `main`; change a workflow
  file; change CI, permissions, billing, subscriptions, or account
  access.
- Send a message, email, or comment to any person on Glenn's behalf.
- Spend money, install software on Glenn's devices, or change device
  settings.
- Decide a destructive or irreversible action (delete, overwrite,
  share, publish) — those always confirm first.
- Present a plan or blueprint as final. Final means Glenn has seen
  the presentation and accepted it.

When a step needs Glenn and he is unavailable, the loop parks: the
state is recorded (status board, decision log, PR), the agent stops,
and the next trigger resumes it. Parking is not failure; silent
progress past a gate is.

## Presentation step

A finalized plan or blueprint is presented, not just merged. The
presentation is a PR plus a chat summary containing:

1. What changed, in one paragraph, in Glenn's words where possible.
2. What was verified, with the command or check and its result —
   never "verified" without the evidence.
3. What is still unproven or unverified, stated plainly.
4. The decisions taken, with decision-log IDs.
5. What Glenn is being asked to approve, exactly.

Glenn approves, corrects, or rejects. A correction is a new turn of
the loop, not an edit to the presented record: the record stands and
the correction is appended.

## Failure handling

- **Red gate.** The loop stops at the gate. The builder fixes in the
  same PR; the reviewer re-checks. If the gate itself is wrong, that
  is a finding against the gate, fixed with a failing-first fixture
  proving the gate can go red.
- **Reviewer finds the intent itself wrong.** That is a reversal, not
  a rewrite. The reviewer records a dated decision-log entry (what
  changed, why, what it supersedes) and the loop re-runs the gates
  from the intent. The old wording stays in version history.
- **A partner goes silent or errors.** Any other partner may pick up
  the next turn from the recorded state. State lives in the repo, so
  no partner's memory is load-bearing. The pickup is recorded as a
  signed decision-log entry noting the handoff.
- **Conflicting findings.** Two reviewers disagree: both findings
  stand, the conflict is recorded, and Glenn decides. Agents do not
  resolve reviewer conflicts by editing each other's findings.
- **Trigger storm.** If a poll or watcher wakes agents repeatedly
  with no new state, the trigger is disabled and the loop parks to
  human handoff until the trigger is fixed. Autonomy that spams is
  worse than no autonomy.

## Pilot success criteria

Two full turns completed with no unsigned contributions, no gate
bypassed, no message sent on Glenn's behalf, and the presentation
step delivered before any merge was requested. The decision log is
the evidence. If any step needed silent human repair, that is a
finding against the loop, fixed before graduation — not worked around.

## What this design deliberately does not include

- No HTTP MCP server, no hosted service, no shared inbox, no bot
  accounts. The wire is local stdio; the table is git.
- No autonomous merging, spending, messaging, or publishing.
- No Notion dependency.
- No new permissions model: the harness's existing read/write
  approvals govern every action, and the server adds no privilege —
  it can only write draft intents, decision entries, and finding
  files inside the chain root.
