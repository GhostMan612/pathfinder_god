---
name: bp06-wp6-perf
description: Use when doing BP-06 WP-6 (list keys, OkHttp singleton, off-main-thread decode, Compose read-in-write, dice crit bug, dice pools, exploding dice, DiceViewModel) — gate G6-6, required test coverage, gate evidence.
---

# BP-06 WP-6 — Performance, leaks & dice correctness

WP-4 (Filament) assumes this landed. Land the correctness fixes and their tests **first** so a regression is bisectable; `DiceViewModel` extraction is last, not first.

## Leaks and perf
- Add `key` to the `DiceScreen.kt:213` history list; audit every other `items(...)` call.
- Hoist `HubApiFactory` to a process-scoped singleton sharing one `OkHttpClient`; shut down on exit. Removes per-tab TLS setup and the per-navigation leak.
- Move map Base64 decode off the main thread with `inSampleSize` downsampling.
- `CombatantCard.kt:181` — read `rise.value` **inside** `graphicsLayer`. Reading a `State` during write invalidates the entire recomposition scope.
- `DiceCanvas`: `remember` the `Paint` and `Path`; fix the inverted number scale; coordinate the drop and spin springs.
- Debounce FTS5 search ~250 ms. Fling + bounds clamping in the map viewer.

## Dice correctness
- **P-3**: nat-20 / nat-1 crit detection is wrong under advantage — an advantage crit is misclassified. Fix it.
- **P-4**: `impactLabel` separator.
- **P-5**: wire dice pools, modifiers, `kh` / `kl` into the UI.
- Pathfinder-appropriate exploding dice (`d6!!`) and 2e degree-of-success.
- Show dropped dice. Persist history to Room. Remove the dead `_history` / `history` duplication (P-6).
- **P-13**: extract `DiceViewModel` so `DiceScreen` stops owning engine + audio + state.

## Commands
```
pg-build { "action": "testAll" }
pg-build { "action": "assembleDebug" }
pg-gate  { "wp": 6 }
```

## Gate G6-6 evidence
```
G6-6: PASS
build:   BUILD SUCCESSFUL
tests:   DiceEngineTest covers advantage crits, pools, modifiers, exploding dice   (paste test names)
decode:  no main-thread image decode
scroll:  no per-roll history re-animation
```
A green build with **unchanged** tests is not a pass.
