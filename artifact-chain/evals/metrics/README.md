# evals/metrics/

One small Markdown file per PR, same shape every time. This is the
record the RSI loop learns from — see `../RSI.md`.

- Filename: `<YYYY-MM-DD>-pr<nn>.md`
- Written by the reviewer / from CI + the recorded run — never by the
  agent that proposed a chain change (no self-grading).
- Copy `_template.md` for each new PR; do not edit the template to fit
  one PR — if the template is wrong, that is a chain change, and it
  goes through the RSI gate like any other.
- Baseline batch 1 is tracked in `baseline.md`: the next 3 PRs,
  change nothing, metrics only.
