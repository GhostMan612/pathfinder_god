# decisions/

The append-only decision log. This is where reversals live.

## Why

An intent, spec, or plan is a decision frozen at a gate. When a later
edit changes a gated decision, editing the old line destroys the
reason the decision changed — and the reason is the part that matters
most the next time the same question comes up. So gated decisions are
never silently rewritten. The original artifact keeps its history in
version control; the *change of mind* gets an entry here.

## Rules

- **Append only.** New entries go at the end of `DECISIONS.md`. Never
  edit, reorder, or delete an existing entry. Fix a mistaken entry by
  appending a correction entry that references it.
- **One entry per decision.** A decision is one question, one answer,
  one reason — not a meeting's worth of conclusions.
- **Every reversal gets an entry.** If you edit an intent after the
  first spec commit, a spec after plan approval, or a plan after
  implementation starts, that edit is a reversal: append an entry
  before the edit lands, or in the same change.
- **IDs are sequential:** `D-0001`, `D-0002`, ... Take the next free
  number. Never reuse one.
- **Link, don't duplicate.** Entries reference artifacts by path and
  gate (e.g. `intent/hello-version.md`, Plan gate), and quote the old
  and new wording briefly. The full text stays in the artifact.

## Entry format

Copy `decision-template.md`. Each entry carries: ID, date, author,
artifact + gate, the question, the previous decision, the new
decision, the reason, and what it supersedes (entry ID or "none —
first decision").

## Example entry (illustrative, not a real decision)

```markdown
## D-0001 — 2026-11-02 — Glenn

- **Artifact / gate:** spec/hello-version.md, Design gate
- **Question:** Should `-v` be a short alias for `--version`?
- **Previous decision:** None — first decision.
- **New decision:** Yes; `-v` behaves identically to `--version`.
- **Reason:** No existing flag collides with `-v`, and users expect
  the short form for version checks.
- **Supersedes:** none.
```

## Capture

Use the `decision-capture` skill (`skills/decision-capture/SKILL.md`)
whenever a gated artifact changes. A hook reminder is wired in
`hooks/hooks.json` for edits under `intent/`, `spec/`, and `plan/`.
