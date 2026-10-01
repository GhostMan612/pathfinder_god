---
description: Run a BP-06 gate (G6-0..G6-9) and return pass/fail evidence.
agent: bp06-orchestrator
---

Run the BP-06 gate for work package **$ARGUMENTS**.

1. Resolve the gate id: WP 0→`G6-0`, 1→`G6-1`, 2→`G6-2`, 3→`G6-3`, 4→`G6-4`, 5→`G6-5`, 6→`G6-6`, 7→`G6-7`, 8→`G6-8`, 9→`G6-9`.
2. Call `pg-gate` with that `wp` number. It runs the mechanical checks and returns a report.
3. Call `pg-repo-guard` for the repo-hygiene half of the gate.
4. Dispatch `verify` for independent evidence on anything `pg-gate` could not decide on its own.
5. Separate **mechanical** results from **human-only** results. These are human-only and must never be self-certified:
   - 6 solids, UV/number orientation, settle-to-face parity (G6-4)
   - app launch without `IllegalStateException`, max refresh rate (G6-5)
   - all 9 destinations in ≤2 taps, predictive back (G6-3)
   - `connectedDebugAndroidTest`, TalkBack announcements (G6-7)
   - crit vs fumble haptics distinguishable (G6-2)
6. Print the gate in this shape and nothing else:
```
G6-<n>: PASS | PARTIAL | FAIL
mechanical:  <one line per check, with the evidence line that proves it>
human:       <the exact list the human must confirm, or "none">
blocker:     <first failing check, or "none">
```
7. If the result is `PARTIAL` or `FAIL`, do not commit. Name the fix, do not start it unasked.
