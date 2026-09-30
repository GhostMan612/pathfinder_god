# Asset credits (visual, 3D, and fonts)

> **STATUS: SKELETON — populated by BP-06 WP-8.** Every table below is empty by
> design. The current shipped app contains no third-party *visual* assets, so
> there is nothing to credit yet. Do not delete a row that has no entry; add the
> row when the asset lands.

Companion register: **[`audio-credits.md`](audio-credits.md)** covers every
bundled sound. This file covers everything else. Both are licence obligations,
not decoration — a redistribution without them breaches CC BY.

## What is in scope here

- Launcher and in-app icons / iconography (Kenney CC0, game-icons.net CC BY 3.0)
- 3D props and models (Quaternius glTF, CC0)
- Textures (procedural or third-party)
- Fonts / typefaces
- The Filament d20 dice-pit mesh (`app/src/main/java/.../ui/pit/`) — generated
  procedurally in-repo, **not** third-party, but keep the row so that stays true

## Icons

| File | Author | License | Source |
|---|---|---|---|
| _(none yet — WP-8)_ | | | |

## 3D models and props

| File | Author | License | Source |
|---|---|---|---|
| _(none yet — WP-8)_ | | | |

## Textures

| File | Author | License | Source |
|---|---|---|---|
| _(none yet — WP-8)_ | | | |

## Fonts

| File | Author | License | Source |
|---|---|---|---|
| _(none yet — WP-8)_ | | | |

## First-party (no attribution required)

These are generated in-repo and are ours. Listed so that "is this credited
anywhere?" always has an answer, and so a future contributor does not go looking
for a licence that does not exist.

| Asset | Origin |
|---|---|
| `mipmap-*/ic_launcher*` | Pathfinder God — in-repo |
| Dice pit d20 mesh + atlas | Pathfinder God — procedural, `ui/pit/` |
| `assets/rules/pathfinder_rag.db` | Pathfinder God device extract of the house rules DB — LFS, in-repo |
| Dice engine SFX (`assets/audio/*`) | see `audio-credits.md` |

## Licence texts

- CC0: <https://creativecommons.org/publicdomain/zero/1.0/>
- CC BY 3.0: <https://creativecommons.org/licenses/by/3.0/>
- CC BY 4.0: <https://creativecommons.org/licenses/by/4.0/>
- OGL-3.0 (Quaternius): <https://creativecommons.org/licenses/ogl/3.0/>

## Rules for anyone adding an asset

1. Prefer **CC0** — no attribution burden, survives forks and remixes.
2. If the licence is **CC BY** anything, the entry is mandatory and the licence
   text must ship with the app (WP-2 adds the on-device credits screen).
3. If the licence is **anything else** — ND, NC, GPL — do not ship it. That is a
   blueprint decision, not a per-commit one.
4. Add the row in the same commit that adds the file. `pg-license` fails the
   gate on any shipped file with no entry here or in `audio-credits.md`.
