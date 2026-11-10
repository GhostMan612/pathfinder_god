# Eval fixtures

Fixtures prove the checker itself works. The CI workflow
(`.github/workflows/chain-eval.yaml`) runs `check-chain.sh` against
both; the same commands run locally.

- `good/` — the hello-version example chain, laid out as `spec/` +
  `plan/`. Every requirement is cited by a task; every task cites a
  requirement. `check-chain.sh` must exit 0.
- `broken/` — the same chain with two deliberate faults: requirement
  R5 in the spec is cited by no plan task, and task T2 cites no
  requirement. `check-chain.sh` must exit 1 and name both.

Run locally:

```sh
bash evals/check-chain.sh evals/fixtures/good    # expect OK, exit 0
bash evals/check-chain.sh evals/fixtures/broken  # expect 2 findings, exit 1
```

When the checker changes, update the fixtures first: add the fault the
new check should catch to `broken/`, and the valid shape it must accept
to `good/`, then change the checker. A checker change with no fixture
change is unproven.
