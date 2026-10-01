---
name: bp06-wp9-docs
description: Use when doing BP-06 WP-9 (documentation truth pass: false native-render-surface claims, audio toggle claims, deleted Flutter spoke, three conflicting applicationId values) — gate G6-9, grep sweep, gitignored docs warning.
---

# BP-06 WP-9 — Documentation truth pass

Runs last. It documents what the other nine WPs actually built.

## False claims to correct
| Location | Claim | Reality after BP-06 |
|---|---|---|
| `KOTLIN_PORT_SPEC.md:141-164` | "no native render surface", "Filament deleted from the plan" | Filament ships, lit, with shadows |
| `AGENTS.md:35,66,74` | stale toolchain / AGDK wiring | per WP-0 and WP-5 |
| `RULES.md:102,123` | stale SDK + lane text | per WP-0 |
| `README.md` | Flutter-era framing | native Kotlin 9-tab app |
| `CHECKLIST.md` / `CHECKPOINTS.md` | audio + haptic toggles "exist" | never survived the Kotlin port |
| `INDEX.md`, `CURRENT_STATE.md`, `ROADMAP.md` | describe the deleted Flutter spoke | describe `spoke_kt/` |

Also reconcile the **three conflicting `applicationId` values** across the repo.

## Method
For every claim you change, cite the code that now proves it. A doc edit without a code reference is a guess. If you find a contradiction BP-06 did not cover, list it for the orchestrator — do not paper over it.

## Gitignored docs — do not force-add
`blueprints/` is ignored by `.gitignore:27` and `RULES.md` §1.3. These stay local and uncommitted:
- `blueprints/blueprint-sections/BP-06-professional-companion.md`
- `blueprints/SESSION_HANDOFF.md`
- `blueprints/CURRENT_STATE.md`, `CHECKPOINTS.md`, `CHECKLIST.md`, `CHANGELOG.md`

Say so in your report so the orchestrator does not attempt to commit them.

## Commands
```
pg-gate  { "wp": 9 }
```

## Gate G6-9 evidence
```
G6-9: PASS
sweep:  grep across README.md, AGENTS.md, RULES.md, KOTLIN_PORT_SPEC.md,
        CHECKLIST.md, CHECKPOINTS.md, INDEX.md, CURRENT_STATE.md, ROADMAP.md
        -> no document contradicts the codebase
```
Paste the sweep output.
