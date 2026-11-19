# Spec: Add a --version flag to the CLI

Status: APPROVED (example)
Intent: `intent.md` in this folder (example chain).

## What this spec defines

A `--version` / `-v` flag that prints the CLI version and exits.

## Current behavior

No version flag exists. The version string lives only in the build
config (`VERSION` constant, single source of truth — verified in the
example repo layout).

## Requirements

- **R1** — `mycli --version` prints the version string to stdout and
  exits with code 0.
- **R2** — `mycli -v` behaves identically to `--version`.
- **R3** — The printed string is the build config's `VERSION` constant.
  No duplicated literal.
- **R4** — The flag works before any other argument parsing; it never
  requires a subcommand or config file.

## Decisions required (Design gate)

- **D1** — Output format: plain version string only (recommended and
  used here), vs. `mycli 1.2.3`. Decided: plain string.

## Acceptance criteria

- **A1** — `--version` prints the exact `VERSION` value, exit 0.
- **A2** — `-v` prints the same output, exit 0.
- **A3** — A test asserts the printed output equals the `VERSION`
  constant (not a hardcoded copy).
- **A4** — `--version` with extra arguments still prints the version
  and exits 0.

## Risks

- Low. The only drift risk is a duplicated version literal; R3 forbids it.

## Explicitly not changed

- All other flags and subcommands. Build config. Help text beyond
  listing the new flag.
