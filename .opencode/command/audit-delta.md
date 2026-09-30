---
description: Re-audit the files a BP-06 work package touched and report drift from the blueprint.
agent: bp06-orchestrator
---

Audit-drift for BP-06 work package **$ARGUMENTS**.

1. Get the files the WP was supposed to touch from `blueprints/blueprint-sections/BP-06-professional-companion.md` §3, and the defects it was supposed to close from §1.
2. `git diff --stat` and `git diff` against the commit the WP started from. Read only the diff — do not re-audit the whole repo.
3. Dispatch `rules-auditor` over the diff. Genesis header on every new/changed `.kt`, no comments, explicit-path git discipline, no secrets, no synthetic-data violations, no build artifacts, no release config.
4. Dispatch the WP's own owner subagent with the diff and ask it to answer one question per §1 defect it owned: **closed, partially closed, or still open — with the file:line that proves it.**
5. Report drift in this shape:
```
WP-<n> drift
closed:      <defect ids, file:line>
partial:     <defect id, what is missing>
still open:  <defect id>
out of scope: <changes the WP made that BP-06 did not ask for>
```
6. Anything the WP changed that BP-06 did not authorize is a finding, not a bonus. Flag it for the orchestrator to accept or revert — do not silently keep it.
