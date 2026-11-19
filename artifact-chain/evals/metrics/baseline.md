# RSI baseline — batch 1

Started: 2026-11-18 (approved by Glenn; see `../RSI.md`).
Metric: **rework rounds per PR**. Secondary: first-review P0/P1 counts,
CI first-pass, gate dwell.

## Rules for this batch

- 3 PRs, change nothing in the chain. Metrics files only.
- A spotted fix goes in `decisions/DECISIONS.md` as a *proposed* change
  and waits for the learning pass after the batch.
- The pilot's two-full-turns bar still comes first: no chain change
  until the loop has proven itself with two full turns.

## PRs in this batch (0 of 3)

| PR | Opened | Rework rounds | First-review P0s | CI first-pass | Metrics file |
|----|--------|---------------|------------------|---------------|--------------|
| —  | —      | —             | —                | —             | —            |
| —  | —      | —             | —                | —             | —            |
| —  | —      | —             | —                | —             | —            |

## Excluded (not baseline data)

- PR #40 (Phase 2 character sheet sync) — merged 17 Nov 2026, before RSI started.
- PR #41 (pit material hardening) — merged 18 Nov 2026, before RSI started.
- PR #49 (Issue #33 Phases 3–4 offline sync) — merged 18 Nov 2026, before RSI started.
- PR #50 (pit prebuilt .filamat materials) — merged 18 Nov 2026, before RSI started.
- PR #51 (checklist merged records for #49/#50) — merged 18 Nov 2026, before RSI started.
- None ran through the council loop and none has a metrics file.
  Retrofitting numbers would be guessing, not measuring.

## After the batch

One learning pass: read the 3 findings files + 3 metrics files
together, propose **one** chain change as a diff on
`council-chain-pilot`, Glenn approves or rejects. Then measure the
next 3 PRs the same way and compare.
