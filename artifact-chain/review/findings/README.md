# review/findings/

One file per review pass, written by the reviewer — never by the
builder of the diff under review.

- Filename: `<YYYY-MM-DD>-<author>.md` (the `sovereign-chain` server
  writes this shape via `chain_review_submit`; on a collision it
  appends `-2`, `-3`, …).
- Findings are immutable: fix them in the same PR, or record a
  deferral with a reason in the decision log. Never edit or delete a
  finding file — deleting one is a P0.
- Severity and merge thresholds live in `review/REVIEW.md`.
- Note: this README *does* appear in the server's `chain_status`
  listing under `review/findings` (the findings listing, unlike the
  other categories, does not exclude README files). It is a note, not
  a finding — real findings are dated `<YYYY-MM-DD>-<author>.md`
  files.

The laptop watcher (`tools/chain-watcher.ps1`) watches this directory:
a new file here is the signal for Glenn to hand the findings to
OpenCode.
