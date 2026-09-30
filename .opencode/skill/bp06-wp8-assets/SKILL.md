---
name: bp06-wp8-assets
description: Use when doing BP-06 WP-8 (free asset integration: Kenney CC0 icons, game-icons.net CC BY 3.0 iconography, Quaternius glTF props, procedural textures, asset credits) — gate G6-8, license tiers, deferral rule.
---

# BP-06 WP-8 — Free asset integration

Requires WP-2's in-app Audio Credits screen — that is where attribution surfaces to the user.

## Verified license tiers (BP-06 §4)
| Source | License | Action |
|---|---|---|
| Kenney icons / audio | CC0 | ship freely |
| Quaternius, Kenney 3D models | CC0 | ship freely |
| game-icons.net | **CC BY 3.0** | **must credit in-app** |
| Haze, Navigation Compose | Apache-2.0 | ship freely |
| Procedural textures | none | no licensing question |

Anything not on this list needs a license line **in-repo and in-app** before it ships.

## Scope
- Kenney CC0 icons (105 glyphs) replacing generic Material icons for the 9 destinations.
- game-icons.net CC BY 3.0 RPG iconography for loot / encounter / condition categories, credited in the WP-2 credits screen.
- Optionally Quaternius / Kenney CC0 low-poly props for map markers and encounter tokens via `gltfio-android` (Poly Pizza, no login, glTF/GLB).
- Procedurally generated parchment / felt textures — prefer these where they work.
- Complete `docs/asset-credits.md`.

## Discipline
Prefer CC0 and procedurally generated. Every fetch lands in the assets tree with recorded license, author, and source URL. **Never add an asset whose license you cannot state.** Nothing from a source requiring a login or account.

## Optional means optional
The Quaternius glTF props add a new native dependency and APK weight. If the core icon set's credit and license work is solid, stop and report the props as a deferral rather than destabilizing the build late in BP-06.

## Commands
```
pg-license {}
pg-build { "action": "assembleDebug" }
pg-gate  { "wp": 8 }
```

## Gate G6-8 evidence
```
G6-8: PASS
build:   BUILD SUCCESSFUL
license: pg-license -> 0 uncredited, 0 orphan media
credits: docs/asset-credits.md complete AND mirrored in-app
```
