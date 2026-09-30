---
name: bp06-wp3-nav
description: Use when doing BP-06 WP-3 (NavHost, 4-tab bar, HomeDashboardScreen, MoreSheet, NavigationSuiteScaffold, insets, deep links) in Pathfinder God spoke_kt — gate G6-3, tap-path check, gate evidence.
---

# BP-06 WP-3 — Navigation & Home dashboard

The original complaint. Requires WP-1 green first — build on `GodCard` / `GodSectionHeader` / `GodEmptyState`, never raw `rpgPanel`.

## Shape
- Adopt `androidx.navigation:navigation-compose`: real `NavHost`, real back stack, predictive back, first-class Hero/Map sub-routes instead of shadowed ids.
- Bottom bar: **Dice · Combat · Hero · Rules** (4 items). M3 caps nav bars at 3–5; 9 is out of spec. 4 items = ~90dp per tab vs 72dp at 5, on a 360dp phone.
- `HomeDashboardScreen`: party/turn status card, quick-roll launcher, active-encounter card, and cards for **Campaign · Map · Encounter · God · Setup**.
- `MoreSheet` for overflow.
- `NavigationSuiteScaffold` → rail on tablets/landscape automatically.
- Deep links from dashboard cards so old 9-way muscle memory still lands correctly.

## Cleanup
Delete `PlaceholderScreen` and the shadowed `selected`. Replace re-tap-to-back with a real back affordance. De-duplicate the double-collected `CharacterViewModel` state. Close the insets hole: consume `safeDrawing` properly instead of hiding bars with no compensation.

## Files in scope
- `spoke_kt/app/src/main/java/com/pathfindergod/spoke/ui/navigation/NavigationShell.kt` (9 items at ~69-93; index + `AnimatedContent` at ~96-167).
- `spoke_kt/app/src/main/java/com/pathfindergod/spoke/ui/navigation/NavigationItem.kt`.
- New `HomeDashboardScreen.kt`, `MoreSheet.kt`, nav graph.

## The leak you must not preserve
`NavigationShell.kt:96-167` constructs `HubApiFactory` per tab, leaking an OkHttp client on every navigation. WP-6 fixes the singleton. Your rewrite must not keep the per-tab construction pattern — but do **not** bundle the WP-6 refactor into this WP.

## Commands
```
pg-gate  { "wp": 3 }
pg-build { "action": "assembleDebug" }
```

## Gate G6-3 evidence
```
G6-3: PASS
build:    BUILD SUCCESSFUL
bar:      4 items
taps:     all 9 original destinations reachable in <=2 taps   [HUMAN — paste the tap list]
back:     predictive back works from every sub-screen          [HUMAN]
```
No screen may be reachable only via index arithmetic.
