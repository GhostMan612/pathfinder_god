# Review guide

Written before the diff exists: review passes, severity definitions,
and merge thresholds. Tighten the thresholds for the project's real
risks — these defaults are a floor, not a ceiling.

## Severity definitions

- **P0 — merge blocker.** Wrong behavior that ships to the user, a
  safety or data-integrity violation, a red verification gate, a
  requirement with no implementation or no check. Fix in the same PR;
  no merge with an open P0.
- **P1 — fix before merge unless explicitly deferred** with a reason
  recorded in the PR. Wrong-but-contained behavior, missing tests for
  new behavior, docs describing behavior that changed.
- **P2 — fix or file.** Edge cases, hardening follow-ups, naming drift.
  If deferred, file it as a dated note in the PR or a new intent —
  never silently dropped.

## Review passes (in order)

1. **Spec trace.** Every spec requirement maps to code or a check;
   every code change maps to a requirement. Orphans are findings.
2. **Safety.** Any path that mutates, deletes, moves, charges, or
   shares real data or money is traced from trigger to effect. Assume
   inputs are wrong, misheard, or adversarial.
3. **Boundary.** Interface contracts match on both sides: function and
   endpoint names, argument keys, constants, and error shapes agree.
   Check both sides of every boundary the change touches.
4. **Failure behavior.** Every new failure mode is surfaced in words
   and leaves the system usable. Silent fallbacks and swallowed return
   values are findings.
5. **Docs.** The docs that describe the changed behavior match the
   shipped behavior. Stale wording is a P1.

## Merge thresholds

- No open P0. No red verification gate.
- Chain-consistency check passed: no orphan requirements, no orphan tasks.
- Verification claimed in the plan is recorded (command, result, and
  where it ran). A review alone never satisfies a runtime, device, or
  integration check.
- For high-cost changes (data mutation, money, security): independent
  review pass — reviewer pass is not the builder's pass.
- Project law honored: branching, staging, approval, and secrets rules
  from `CLAUDE.md`.

## What review does not do

Review does not re-decide the intent. If review finds the intent itself
wrong, that is a reversal: record it dated in the intent (reason, what
it supersedes) and re-run the gates; do not quietly rewrite the intent
mid-review.
