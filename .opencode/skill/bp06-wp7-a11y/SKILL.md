---
name: bp06-wp7-a11y
description: Use when doing BP-06 WP-7 (accessibility: contentDescription, Role/stateDescription, live regions for rolls and HP, 48dp targets, testTags, androidTest source set, RTL) — gate G6-7, device-only limits.
---

# BP-06 WP-7 — Accessibility

## Baseline today
Eight `contentDescription` calls in the whole app. No semantics, no `testTag`s, no `androidTest` source set. ~14 interactive controls under 48dp.

## Scope
- `contentDescription` on every interactive element. `Role` and `stateDescription` on expandable cards.
- **`LiveRegion` announcements for rolls, crits, and HP changes — highest-value item in this WP.** A blind player must *hear* a roll outcome and a damage number, not see it.
- Fix all ~14 sub-48dp targets.
- `WindowInsets` / `safeDrawing`; enable predictive back (WP-3 lays groundwork, you verify everywhere).
- `testTag` throughout; create the `androidTest` source set with Compose UI tests.
- Correct directional glyphs for RTL.

## Sweep, don't sample
WP-3 and WP-1 have just rewritten navigation and every card component. Fix descriptions and targets at the **component** level in `ui/designsystem/` where possible. A per-screen audit will miss the new screens.

## Do not
Restructure layouts to fix sizing — that is WP-1's job. Prefer padding and `minimumInteractiveComponentSize` over layout rewrites.

## Commands
```
pg-build { "action": "assembleDebug" }
pg-gate  { "wp": 7 }
```

## Gate G6-7 evidence
```
G6-7: PASS
build:      BUILD SUCCESSFUL
targets:    0 interactive controls under 48dp
instrumented: [HUMAN] connectedDebugAndroidTest green
talkback:   [HUMAN] announces every roll and damage change
```
You cannot run `connectedDebugAndroidTest` without human hardware. Prepare the tests, give the exact command, mark the gate partial.
