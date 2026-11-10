# Artifact Chain Scaffold

A drop-in starting point for building with an artifact chain. Copy this
whole folder into any new project folder and the chain is ready to run:
intent → spec → plan → diff + tests → review → next intent.

Adapted from Anthropic's AI-native SDLC playbook (published 21 August
2026). The core idea: every stage produces a version-controlled,
human-readable, machine-actionable Markdown artifact; acceptance of one
artifact triggers the next stage; human judgment concentrates at the
gates instead of spreading across every step.

## Quickstart

1. Copy this folder into the new project (at the root, or under
   `docs/` — pick one and stay consistent).
2. Rename the project placeholder in `CLAUDE.md` and fill in the
   project's real conventions, commands, and constraints.
3. Start a chain: run the **grilling** skill (`skills/grilling/SKILL.md`)
   or just talk through the change, then save the result as
   `intent/<slug>.md` using `templates/intent-template.md`.
4. Work the gates in `CHAIN.md`. Nothing is implemented until the spec
   is approved; nothing merges until the review thresholds pass.
5. See `examples/hello-version/` for one complete, tiny chain filled in,
   so the shape is visible before you write your own.

## What's inside

| Path | What it is |
|---|---|
| `CLAUDE.md` | Starter session brief. Claude Code reads it on session start: where the chain lives, what to read first, and the project's rules. Fill in the placeholders. |
| `CHAIN.md` | The loop: stages, artifacts, gates, reversal rule, evals, and the three chain variants with when to use each. |
| `intent/` | One file per change. The *why*. Nothing else lives here. |
| `spec/` | One file per change. The *what*: requirements and expected behavior. |
| `plan/` | One file per change. The *how*: files, order of work, proof per task. |
| `review/REVIEW.md` | Review passes, severity definitions (P0/P1/P2), merge thresholds. Written before the diff exists. |
| `decisions/` | Append-only decision log (`DECISIONS.md`), entry template, and rules. Reversals are events with a history, not silent rewrites. |
| `.github/workflows/chain-eval.yaml` | CI evals: consistency check on the live chain, golden-path/broken fixture proofs, placeholder and skill-frontmatter checks. Move to the repo root if the scaffold lives in a subfolder. |
| `.claude-plugin/` | Plugin manifest (`plugin.json`) and marketplace catalog (`marketplace.json`) for installing the scaffold as a Claude Code plugin. |
| `templates/` | Blank intent / spec / plan templates. Copy, don't edit in place. |
| `skills/` | Claude Code skills (SKILL.md format): grilling, spec-generation, plan-generation, review, decision-capture. Drop into `.claude/skills/` or your plugin to use them. |
| `hooks/` | The three proposed automation hooks (intent accepted → draft spec; spec approved → draft plan; gated edit → capture decision) plus an example `hooks.json` to adapt. Hooks propose; humans dispose. |
| `evals/` | Chain-consistency check, plus `fixtures/` (golden-path and broken chains that prove the checker bites). |
| `examples/hello-version/` | A complete worked example chain for a trivial feature. |

## Install as a Claude Code plugin

This folder is a plugin: `.claude-plugin/plugin.json` is the manifest
(name, version, description, author) and `.claude-plugin/marketplace.json`
is the marketplace catalog pointing at this folder (`"source": "./"`).
Only `plugin.json`/`marketplace.json` live inside `.claude-plugin/`;
skills, hooks, and everything else sit at the plugin root, which is
where Claude Code discovers them. Bump `version` in both files to ship
an update — installs only pick up a new version when the version
changes.

Three ways to use it, in order of setup cost:

1. **Skills-directory plugin (zero install).** Drop this folder under
   `~/.claude/skills/` (or `<project>/.claude/skills/`). Any folder
   there containing `.claude-plugin/plugin.json` loads as a plugin on
   the next session, no marketplace or install step. Skill edits apply
   immediately; hook changes need a reload or restart.
2. **Marketplace install.** Push this folder as a git repo (public, or
   one you have Git access to), then in Claude Code:
   `/plugin marketplace add <owner>/<repo>`, then
   `/plugin install artifact-chain@artifact-chain-marketplace`.
   Verify the exact commands against the Claude Code version installed —
   plugin commands and the catalog schema have moved between versions.
3. **Copy the folder.** The original path: copy it into a project and
   work from the files directly. The plugin files are inert in this
   mode and cost nothing.

Security note, from the plugin model itself: a plugin runs code as you
if it contains hooks, MCP servers, or `bin/`. This one ships a hooks
example only — read `hooks/hooks.json` before enabling it, as you
should with any plugin.

## Rules of the scaffold

- One intent per change. One spec per intent. One plan per spec.
- Acceptance is a gate, not a formality: intent accepted → spec;
  spec approved → plan and implementation; review passed → merge.
- A reversal is an event, not an edit: if an intent changes after the
  first spec commit, append a dated reversal entry (date, author,
  reason, what it supersedes) to `decisions/DECISIONS.md` via the
  `decision-capture` skill. Never silently rewrite the old line.
- No artifact authorizes what it doesn't say. An intent never
  authorizes implementation; a plan never authorizes a merge.
- Claims need the check named in the plan. A code review alone never
  proves behavior that only a run, test, or device can prove.
