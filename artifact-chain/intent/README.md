# intent/

One file per change: `intent/<slug>.md`.

The intent is the **why**: the problem, the proposed outcomes, the
affected users, the constraints, the open questions, and the non-goals.
It is written in plain language, readable by humans and actionable by
machines. Anyone can originate one.

Rules:

- Copy `templates/intent-template.md`. Don't write an intent from a
  blank page, and don't edit the template in place.
- One intent per change. A second change gets a second file.
- The intent is accepted at the Plan gate. Acceptance triggers the spec
  stage; it does not authorize implementation.
- After the first spec commit for this change, any edit to the intent
  is a **reversal**: append a dated entry (date, author, reason, what
  it supersedes). Never silently rewrite the old line.

See `examples/hello-version/intent.md` for a filled-in example.
