# spec/

One file per change: `spec/<slug>.md`, matching its intent's slug.

The spec is the **what**: technical requirements and expected behavior,
decisions required, acceptance criteria, risks, and explicit
non-changes. It is generated from the accepted intent — by the
spec-generation skill, a prompt, or an agent — applying the project's
constraints as hard generation requirements.

Rules:

- Copy `templates/spec-template.md`. Don't write a spec from a blank page.
- If the intent and the spec disagree, the intent wins and the spec is
  revised. Record the disagreement; don't quietly pick a side.
- The spec is approved at the Design gate. Approval authorizes the plan
  stage and, through it, implementation.
- Every requirement gets an ID (R1, R2, ...) so the plan and the
  chain-consistency check can trace it.

See `examples/hello-version/spec.md` for a filled-in example.
