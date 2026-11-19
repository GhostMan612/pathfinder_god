# Hooks

Two automation hooks are proposed for this chain. Both **propose**; a
human disposes. Neither commits, pushes, merges, or sends anything.

## Hook 1 — intent accepted → draft spec

- Trigger: an `intent/<slug>.md` file is accepted (status line set to
  accepted, or the user confirms acceptance in conversation).
- Action: run the spec-generation skill against that intent and save a
  draft to `spec/<slug>.md` marked DRAFT.
- Human step: approve or correct the spec. Nothing proceeds on a draft.

## Hook 2 — spec approved → draft plan

- Trigger: a `spec/<slug>.md` file is approved.
- Action: run the plan skill against the spec and save a draft to
  `plan/<slug>.md` marked DRAFT.
- Human step: approve the spec (which authorizes implementation task by
  task). The plan draft alone authorizes nothing.

## Hook 3 — gated edit → capture the decision

- Trigger: a file under `intent/`, `spec/`, or `plan/` is written or
  edited after its gate has passed.
- Action: remind the agent to record the change in
  `decisions/DECISIONS.md` via the `decision-capture` skill. The hook
  only reminds; the skill writes the entry, and the human still owns
  the decision.
- The example `hooks.json` in this folder covers hooks 1–3 in a single
  `PostToolUse` reminder: it notices edits under `intent/`, `spec/`,
  and `plan/` and prints the next-step reminder (draft the next
  artifact, or capture the decision).

## Wiring it up (Claude Code example)

`hooks.json` in this folder is an **example to adapt**, not a verified
configuration: it uses a `PostToolUse` hook that notices when a file
under `intent/`, `spec/`, or `plan/` is written and reminds the agent
to draft the next artifact or capture a changed decision.
Check it against the Claude Code hooks documentation for the version
installed — hook event names, matcher syntax, and the JSON the hook
receives on stdin can change between versions.

Manual equivalent, which always works: after accepting an intent, say
"draft the spec"; after approving a spec, say "draft the plan." The
skills in `skills/` are written to run on those prompts with no hook
wiring at all.

## Rules for any hook you add

- A hook may read and draft. It may not commit, push, merge, delete,
  send mail or messages, or spend money.
- A hook's output is a suggestion in the conversation, not an action
  taken. If a hook's suggestion is wrong, the human corrects it and the
  chain continues.
- Keep hooks small and observable: one trigger, one action, visible
  output.
