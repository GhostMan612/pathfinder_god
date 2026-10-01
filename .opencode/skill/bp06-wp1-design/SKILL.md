---
name: bp06-wp1-design
description: Use when doing BP-06 WP-1 (God* design system, Dimens/Spacing, 28 M3 color roles, Haze GlassCard, strings.xml, migrating 25 rpgPanel call sites) — gate G6-1, component list, grep sweeps, gate evidence.
---

# BP-06 WP-1 — Design system: the `God*` component layer

Widest blast radius in BP-06: touches ~25 files across every tab. Migrate mechanically. Do not redesign screens here — that is WP-3.

## New package `ui/designsystem/`
`GodCard` (the slot-bearing successor to `rpgPanel`), `GodChip`, `GodPrimaryButton`, `GodTextField`, `GodFab`, `GodEmptyState`, `GodSectionHeader`, `GodBackLink`, `GodStatTile`, `GodStatusText`, `GodBadge`, `GodProgressBar`.

Also: `Dimens` / `Spacing` scale, complete `Shapes`, all 28 M3 color roles, `GlassCard` via Haze (`dev.chrisbanes.haze`, Apache 2.0) for the dashboard header, bundled SIL OFL serif display fonts.

`RpgModifiers.kt:18-47` becomes a thin delegating shim, then dies.

## Files in scope
- `spoke_kt/app/src/main/java/com/pathfindergod/spoke/ui/theme/RpgModifiers.kt`, `Theme.kt`, `Color.kt`.
- All 25 `rpgPanel()` call sites under `ui/`.
- `spoke_kt/app/src/main/res/values/strings.xml` (create) and every literal.
- `CampaignScreen.kt:60-64` — the mock LLM payload, plus hardcoded `"A ruined crypt"` and `"44,620"`.

## Known defects being closed
D-4…D-10 (ad-hoc panels, no slots, no type scale), D-13 (`surfaceTint`, `error` colors missing), plus the missing `strings.xml`.

## Commands
```
pg-gate  { "wp": 1 }
pg-build { "action": "assembleDebug" }
```
Gate sweeps:
```
rg -n "rpgPanel\(" spoke_kt/app/src/main/java/   # hits ONLY in ui/designsystem/
rg -n "Text\(\"" spoke_kt/app/src/main/java/com/pathfindergod/spoke/ui/   # 0 user-facing literals
```

## Haze risk
New dependency. If the build fails on it, ship a plain `GlassCard` without refraction rather than fighting the dependency. Do not bump other versions to accommodate it.

## Gate G6-1 evidence
```
G6-1: PASS
build:     BUILD SUCCESSFUL
sweep 1:   rpgPanel( hits only in ui/designsystem/   (paste count)
sweep 2:   0 hardcoded user-facing strings outside strings.xml   (paste output)
```
A partial migration fails the gate.
