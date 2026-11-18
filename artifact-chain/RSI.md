# RSI — Recursive Self-Improvement for the council chain pilot

Status: **approved by Glenn 18 Nov 2026** (RSI = Recursive Self-Improvement).
This file is the RSI spec for the Pathfinder God pilot. It changes no
product code and no chain rule by itself — it records what Glenn
approved, and every actual chain change still goes through its own
diff on `council-chain-pilot` with Glenn's approval.

## The idea in one line

The council loop already produces code. RSI adds a second loop: the
outcome of each run feeds back into the *machinery* — the skills,
templates, review thresholds, and evals — so the chain gets better
at producing mergeable work first time.

## The loop (one turn)

1. **Run.** Builder works one plan on a branch, opens a PR.
2. **Measure.** Evals and gates run; numbers go in a metrics file —
   `artifact-chain/evals/metrics/<date>-pr<nn>.md` (see `evals/metrics/README.md`).
   No metrics file, no RSI: without it you are changing the chain on anecdotes.
3. **Review.** Independent reviewer checks the diff against the spec,
   writes findings to `artifact-chain/review/findings/<date>-<author>.md`.
4. **Learn.** A separate pass asks what in the *chain* caused the
   outcome. Vague spec? Template missing a field? Threshold wrong?
5. **Change the chain.** One bounded edit to the machinery itself —
   a skill, a template, a threshold, an eval fixture — on the pilot
   branch only.
6. **Next run.** The next feature run uses the changed chain, and the
   same metric is measured again.

Steps 4–5 are the self-improvement. Without them this is just the
same chain running repeatedly.

## The metric (one, and only one)

**Rework rounds per PR** — how many review → fix cycles a PR takes
before it is mergeable. Tracked alongside it, judged second:
first-review P0 count, first-review P1 count, CI first-pass, gate dwell.

- A rework round is one findings file followed by a fix push that
  still leaves findings open. A PR that merges after the first
  review with zero findings is 0 rounds.
- The metric is an outcome, not a checklist. `check-chain.sh`
  passing is necessary but not sufficient — it is gameable by wording.
  Rework rounds, P0s escaping review, and CI first-pass are not.

## Baseline

- **Batch 1 = the next 3 PRs, change nothing.** Run the council loop
  exactly as built; the only new thing is the metrics file per PR.
  No chain changes during baseline, even if an obvious fix is spotted
  — log it in `decisions/DECISIONS.md` as a *proposed* change and wait.
- PRs #40 and #41 merged before RSI started (17–18 Nov 2026) and are
  **not** baseline data: the loop never ran on them and no metrics
  file exists for them. Baseline starts with the next PR.
- **First live turn first.** The pilot's own bar (two full turns, no
  unsigned contributions, no gate bypassed, nothing sent on Glenn's
  behalf, presentation before any merge request) still comes before
  any chain change. Until those two turns exist, there is a loop to
  prove, not a loop to improve.

## Budgets (Glenn-approved, 18 Nov 2026)

- Max **1 chain change per batch of 3 PRs**.
- **One variable per turn.** If the spec template *and* the review
  thresholds change in the same turn, nobody can tell which one moved
  the metric.
- **Revert on 2 consecutive worsening batches.** If rework rounds go
  up for two batches in a row, revert the last chain change (git
  revert on the pilot branch, decision-log entry saying why) and stop
  proposing changes until Glenn says go.
- Max 2 self-improvement turns per feature PR is the standing cap;
  the batch budget above is the tighter binding rule during the pilot.

## Separations (non-negotiable)

1. **Builder ≠ reviewer ≠ chain-changer.** Three different passes.
   The reviewer never edits the code under review; the pass that
   proposes a chain change never grades its own change — the next
   run's metrics grade it.
2. **Chain changes are code-reviewed like product changes.** A change
   to a skill, template, threshold, or eval goes through a diff on the
   pilot branch, with its own findings file, and Glenn approves it.
   If the chain can rewrite its own rules without a gate, that is
   drift, not RSI.
3. **No self-grading.** The agent that proposes a chain change does
   not write its metrics file. Metrics come from CI + the reviewer +
   the recorded run.

## Guardrails

- A self-improvement turn may only touch chain files
  (`artifact-chain/skills/`, `templates/`, `review/`, `evals/`,
  `CHAIN.md`, `decisions/`, this file). It may not touch product code,
  and it may not touch `main` — pilot branch only.
- **Golden tests for the checker.** `evals/fixtures/good/` must pass,
  `evals/fixtures/broken/` must fail, on every run. A checker change
  with no fixture change is unproven. The same rule extends to any
  skill/template change: it ships with an example of what it should
  now catch and what it must still accept.
- **Reversal rule, applied to the chain too.** A change after its gate
  is a dated `DECISIONS.md` entry (date, author, reason, what it
  supersedes) — never a silent rewrite. The old wording stays in git
  history; the *reason* for changing your mind is what gets recorded.
- **No auto-commit / auto-push / auto-merge, ever.** The loop proposes
  diffs; Glenn disposes.
- **Scope stays out.** A chain change may not widen permissions, add a
  workflow, change repo settings, or touch `sovereign_mantle` (off
  limits for direct work — only Claude Code / Opus 5.5 there).

## Failure mode to watch

**Reward hacking** — the chain learning to pass the eval instead of
doing good work (e.g. specs whose requirements are trivially
traceable but meaningless). The defence is the outcome metric above:
rework rounds and P0s cannot be gamed by wording alone.

## What proves it is improving, not churning

- A falling trend over 5–10 PRs, not one good PR. Baseline average
  of (say) 2.5 rounds falling to 1.5 and staying there counts; one
  PR with zero rounds proves nothing.
- Every change has a before/after pair: baseline metrics → one change
  → new metrics. A chain change with no metrics on either side is
  churn, and the decision log should say so.
- Reversals are visible, not hidden. A reverted chain change is a
  successful experiment (something was learned), not a failure — as
  long as it is in `DECISIONS.md` with the reason.
- Gate dwell is a secondary signal. If rework rounds fall but
  intent→merge time rises, one bottleneck was traded for another.
  Watch both; judge on rework rounds first.
- If rework rounds do not move after 2–3 chain changes, the honest
  conclusion is the chain is not the bottleneck — the work is — and
  self-improvement turns stop.
