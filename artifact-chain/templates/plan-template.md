# Plan: <name>

Status: DRAFT — awaiting spec approval (Build gate)
Spec: <link>. Intent: <link>.
No implementation is authorized by this plan alone; approval of the
spec authorizes implementation, task by task, with review per
`review/REVIEW.md`.

## Task order

### T1 — <task>
Files: <exact paths>
- <What changes, concretely.>
- Done when: <observable completion condition.>
- Proof: <acceptance criterion ID, test, or run.>

### T2 — <task>
<Repeat. Order tasks by dependency: foundations before the features
that depend on them. Note parallelizable tasks and why.>

## Verification gate

- Host/CI: <commands to run, and where they run — never claim a run
  that did not happen.>
- Chain-consistency check: every requirement traces to a task and a
  check; no orphan tasks.
- Runtime/device/integration: <checks, environment, and where results
  are recorded.>

## Risks carried into the build

<What the build must still resolve, and which task owns each item.>
