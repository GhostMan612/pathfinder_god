# plan/

One file per change: `plan/<slug>.md`, matching its intent's and spec's
slug.

The plan is the **how**: files to change and where, order of work,
risks, and proof per task. The agent works the plan until the checks
pass. There is no one-size-fits-all plan shape; the template here is a
starting point, and the plan may carry whatever structure the change
needs as long as every task names its files, its done-condition, and
its proof.

Rules:

- Copy `templates/plan-template.md`. Don't write a plan from a blank page.
- Order tasks by dependency: foundations before the features that
  depend on them. Note which tasks can run in parallel and why.
- Every task cites the requirement ID(s) it implements (R1, R2, ...).
  The chain-consistency check enforces this.
- No implementation is authorized by the plan alone. The spec's
  approval authorizes implementation, task by task, with review.
- If a task's diff grows past one reviewable change, split it.

See `examples/hello-version/plan.md` for a filled-in example.
