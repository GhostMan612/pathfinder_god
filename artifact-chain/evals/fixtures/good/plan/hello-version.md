# Plan: Add a --version flag to the CLI

Status: DRAFT (example)
Spec: `spec.md` in this folder. Intent: `intent.md` in this folder.

## Task order

### T1 — Read VERSION from the single source of truth (R3)
Files: `src/version.py` (example path)
- Expose the build config's `VERSION` constant through one accessor.
  No new literal anywhere.
- Done when: exactly one definition of the version string exists.
- Proof: A3.

### T2 — Wire --version / -v into argument parsing (R1, R2, R4)
Files: `src/cli.py` (example path)
- Add the flag; handle it before subcommand dispatch; print to stdout;
  exit 0.
- Done when: `--version`, `-v`, and `--version` with extra arguments
  all print the version and exit 0.
- Proof: A1, A2, A4.

### T3 — Tests (R1, R2, R3, R4)
Files: `tests/test_version.py` (example path)
- Assert printed output equals the `VERSION` constant; cover `-v` and
  extra-argument cases.
- Done when: the new tests pass and the suite stays green.
- Proof: A1–A4.

## Verification gate

- Run the project's test command; record result. (Example chain: no
  real run — this is a shape example, not a verified change.)
- Chain-consistency check: `./evals/check-chain.sh` over this folder
  passes: R1–R4 are all cited by T1–T3, and every task cites an R ID.

## Risks carried into the build

- None beyond R3 drift, owned by T1.
