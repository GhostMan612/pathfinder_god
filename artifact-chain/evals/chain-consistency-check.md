# Evals: chain-consistency check

Run before any merge. The question it answers: does every spec
requirement trace to a plan task and a check, and does every plan task
trace to a requirement?

## What it checks

1. Every requirement ID (`R1`, `R2`, ...) appearing in `spec/*.md`
   appears somewhere in `plan/*.md` (the task that implements it).
2. Every plan task heading (`T1`, `T2`, ...) is followed, within its
   task block, by at least one requirement ID — the task cites what it
   implements.
3. Spec and plan files exist in matching slugs: a `spec/<slug>.md`
   without a `plan/<slug>.md` (or vice versa) is reported, not failed,
   so a chain mid-flight isn't punished for being mid-flight.

## Running it

```sh
./evals/check-chain.sh [chain-root]
```

Chain root defaults to the current directory. README files are
ignored. Exit code 0 means the checks passed; non-zero lists the
orphans. It is a heuristic over Markdown conventions, not a proof: a
requirement mentioned in passing counts as traced, and the check can't
tell whether the implementation is correct. The review skill is still
the correctness gate.

## Running in CI

`.github/workflows/chain-eval.yaml` runs this check on every pull
request and push to `main` that touches chain artifacts. It also runs
the check against the fixtures in `evals/fixtures/` — the golden-path
chain must pass, the broken chain must fail — so the checker itself is
proven on every run, and it fails on unfilled template placeholders and
skills missing `name`/`description` frontmatter. If the scaffold lives
in a subfolder, move the workflow to the repo root and set `CHAIN_ROOT`
to the scaffold folder.

## Fixtures

See `evals/fixtures/README.md`. When the checker changes, update the
fixtures first: the fault the new check should catch goes in `broken/`,
the valid shape it must accept goes in `good/`. A checker change with
no fixture change is unproven.

## Other evals worth adding per project

- **Reversal count:** intent edits after the first spec commit, counted
  from version history. A rising count means the intent stage is being
  rushed.
- **Gate dwell:** time between intent acceptance and spec approval, and
  between spec approval and merge. Long dwells point at the real
  bottleneck.
- **Verification coverage:** share of acceptance criteria with a
  recorded run (command, result, environment) vs. criteria closed by
  review alone.
