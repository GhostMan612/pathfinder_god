# Asset credits (visual, 3D, and fonts)

This is the in-repo half of the licence obligation for everything the app
**draws** rather than plays. The in-app half is the **Setup → Credits** screen,
`spoke_kt/app/src/main/java/com/pathfindergod/spoke/ui/settings/AudioCreditsScreen.kt`,
reachable from **Setup → CREDITS**. The two must stay in step: a credit that
exists in only one of them does not discharge the licence.

Companion register: **[`audio-credits.md`](audio-credits.md)** covers every
bundled sound.

> **Every row below was verified against a file that physically exists in the
> assets/drawable tree before the row was written.** A credit for an absent
> asset is a false attribution, which is worse than a missing one. Run
> `pg-license` after any asset change; it reports uncredited and orphan media.

## Icons

Source: **game-icons.net**, which publishes its own work under
**Creative Commons Attribution 3.0** (`<https://game-icons.net/>`, footer reads
"License CC BY 3"). The canonical SVG repository is
`game-icons/icons` on GitHub; each file below was fetched from that repository
at the `master` branch. Upstream additionally asks for the literal phrase
"Icons made by *{author}*", which both this register and the in-app screen use.

Attribution required. Do not drop these rows without dropping the icons.

| File | Upstream icon | Author | Licence | Source page |
|---|---|---|---|---|
| `spoke_kt/app/src/main/res/drawable/gi_loot_coins.xml` | coins | Delapouite | CC BY 3.0 | <https://game-icons.net/1x1/delapouite/coins.html> |
| `spoke_kt/app/src/main/res/drawable/gi_loot_fire_gem.xml` | fire-gem | Delapouite | CC BY 3.0 | <https://game-icons.net/1x1/delapouite/fire-gem.html> |
| `spoke_kt/app/src/main/res/drawable/gi_loot_glowing_artifact.xml` | glowing-artifact | Delapouite | CC BY 3.0 | <https://game-icons.net/1x1/delapouite/glowing-artifact.html> |
| `spoke_kt/app/src/main/res/drawable/gi_loot_chest.xml` | chest | Delapouite | CC BY 3.0 | <https://game-icons.net/1x1/delapouite/chest.html> |
| `spoke_kt/app/src/main/res/drawable/gi_enc_trivial.xml` | peace-dove | Delapouite | CC BY 3.0 | <https://game-icons.net/1x1/delapouite/peace-dove.html> |
| `spoke_kt/app/src/main/res/drawable/gi_enc_low.xml` | weight-scale | Delapouite | CC BY 3.0 | <https://game-icons.net/1x1/delapouite/weight-scale.html> |
| `spoke_kt/app/src/main/res/drawable/gi_enc_moderate.xml` | axe-sword | Delapouite | CC BY 3.0 | <https://game-icons.net/1x1/delapouite/axe-sword.html> |
| `spoke_kt/app/src/main/res/drawable/gi_enc_severe.xml` | slime | Delapouite | CC BY 3.0 | <https://game-icons.net/1x1/delapouite/slime.html> |
| `spoke_kt/app/src/main/res/drawable/gi_enc_extreme.xml` | t-rex-skull | Delapouite | CC BY 3.0 | <https://game-icons.net/1x1/delapouite/t-rex-skull.html> |
| `spoke_kt/app/src/main/res/drawable/gi_cond_prone.xml` | knocked-out-stars | Delapouite | CC BY 3.0 | <https://game-icons.net/1x1/delapouite/knocked-out-stars.html> |
| `spoke_kt/app/src/main/res/drawable/gi_loot_crystal_cluster.xml` | crystal-cluster | Lorc | CC BY 3.0 | <https://game-icons.net/1x1/lorc/crystal-cluster.html> |
| `spoke_kt/app/src/main/res/drawable/gi_loot_crystal_shine.xml` | crystal-shine | Lorc | CC BY 3.0 | <https://game-icons.net/1x1/lorc/crystal-shine.html> |
| `spoke_kt/app/src/main/res/drawable/gi_cond_frightened.xml` | ghost | Lorc | CC BY 3.0 | <https://game-icons.net/1x1/lorc/ghost.html> |
| `spoke_kt/app/src/main/res/drawable/gi_cond_sickened.xml` | poison-bottle | Lorc | CC BY 3.0 | <https://game-icons.net/1x1/lorc/poison-bottle.html> |

### Where each icon is used

The mapping from app concept to drawable is one file, so it is the thing to
read first:

`spoke_kt/app/src/main/java/com/pathfindergod/spoke/ui/icons/CategoryIcons.kt`

| Drawable | App concept | Surface |
|---|---|---|
| `gi_loot_coins`, `gi_loot_crystal_cluster`, `gi_loot_fire_gem`, `gi_loot_crystal_shine`, `gi_loot_glowing_artifact`, `gi_loot_chest` | loot rarity ladder | `ui/loot/LootCard.kt` |
| `gi_enc_trivial`, `gi_enc_low`, `gi_enc_moderate`, `gi_enc_severe`, `gi_enc_extreme` | encounter difficulty ladder | `ui/encounter/EncounterScreen.kt` |
| `gi_cond_frightened`, `gi_cond_prone`, `gi_cond_sickened` | combat conditions | `ui/combat/CombatantCard.kt` |

### Modifications

The upstream SVGs are 512x512 with an opaque black background path covering the
whole square, followed by the white glyph path. Each file is an Android
`VectorDrawable` in which:

- the opaque background path is dropped, so the glyph tints with the theme;
- the glyph's `pathData` is transcribed **verbatim** — no geometry, colour,
  scale or proportion is altered;
- the intrinsic size is set to `24dp` x `24dp`, with the `512x512` viewport kept
  intact so path coordinates are unchanged;
- an XML comment in each drawable records the author and the exact source URL.

That is the complete list of changes, and it is what the in-app "Changes" line
says too. The upstream `.svg` files are **not** shipped — only the converted
drawables are — because an unreferenced file in the asset tree is exactly what
`pg-license` flags as an orphan.

## Navigation icons (Kenney, CC0)

Source: **Kenney — Board Game Icons** (v1.1, created 22-07-2024),
<https://kenney.nl/assets/board-game-icons>. The pack's own `License.txt`
inside the downloaded `.zip` reads:

> License: (Creative Commons Zero, CC0)
> <http://creativecommons.org/publicdomain/zero/1.0/>

CC0 is a public-domain dedication, so **no attribution is legally required**.
Kenney asks for a credit as a courtesy, and it is given here and in the in-app
credits screen anyway. Author: **Kenney (Kenney Vleugels)**.

| File | Upstream glyph | Destination | Licence |
|---|---|---|---|
| `spoke_kt/app/src/main/res/drawable/ki_home.xml` | `structure_house` | Home | CC0 1.0 |
| `spoke_kt/app/src/main/res/drawable/ki_dice.xml` | `d20` | Dice | CC0 1.0 |
| `spoke_kt/app/src/main/res/drawable/ki_combat.xml` | `sword` | Combat | CC0 1.0 |
| `spoke_kt/app/src/main/res/drawable/ki_hero.xml` | `character` | Hero | CC0 1.0 |
| `spoke_kt/app/src/main/res/drawable/ki_rules.xml` | `book_open` | Rules | CC0 1.0 |
| `spoke_kt/app/src/main/res/drawable/ki_campaign.xml` | `flag_square` | Campaign | CC0 1.0 |
| `spoke_kt/app/src/main/res/drawable/ki_map.xml` | `hexagon_tile` | Map | CC0 1.0 |
| `spoke_kt/app/src/main/res/drawable/ki_encounter.xml` | `skull` | Encounter | CC0 1.0 |
| `spoke_kt/app/src/main/res/drawable/ki_god.xml` | `pouch` | God (loot) | CC0 1.0 |
| `spoke_kt/app/src/main/res/drawable/ki_setup.xml` | `puzzle` | Setup | CC0 1.0 |
| `spoke_kt/app/src/main/res/drawable/ki_credits.xml` | `book_closed` | Audio Credits | CC0 1.0 |

`Destination.iconRes` in
`spoke_kt/app/src/main/java/com/pathfindergod/spoke/ui/navigation/NavigationItem.kt`
is the one place these are bound. `heroDetail` reuses `ki_hero` and `mapViewer`
reuses `ki_map`, which is why the table has 11 rows for 9 navigation
destinations plus Home and Audio Credits.

### Modifications

Kenney ships each glyph as a single-path SVG (`Vector/Icons/<name>.svg`) in a
coordinate space centred on the origin. Each file is an Android
`VectorDrawable` in which:

- the glyph's `pathData` is transcribed **verbatim** — no geometry, proportion,
  scale or colour is altered;
- the viewport is Kenney's own **64x64** tile size (from the pack's
  `Tilesheet/Tilesheet.txt`), so the glyph sits exactly where Kenney lays it
  out;
- the only transform is a `<group android:translateX/translateY>` of
  approximately `(32, 32)`, computed per glyph from its bounding box so that
  the path — authored around the origin — lands inside that tile. Values differ
  slightly per glyph (e.g. `ki_god` uses `28.25, 31.72`) purely for
  centring;
- the fill is `#FFFFFFFF` and the intrinsic size is `24dp` x `24dp`, so the
  glyph tints with the theme via Compose `Icon`;
- an XML comment in each drawable records the author, the pack URL and the
  exact source glyph.

The upstream `.svg` files are **not** shipped — only the converted drawables —
because an unreferenced file in the asset tree is exactly what `pg-license`
flags as an orphan.

## Textures

No third-party texture is shipped. Both surfaces are generated at runtime in
this repository from a fixed integer seed, so there is nothing to attribute and
nothing to license.

| Surface | Generator | Used by |
|---|---|---|
| Parchment grain (96px tile, warm speckle, seamless) | `ui/designsystem/GodTexture.kt` | `ui/loot/LootScreen.kt` |
| Felt weave (96px tile, cool speckle, seamless) | `ui/designsystem/GodTexture.kt` | `ui/combat/CombatTrackerScreen.kt` |

The Filament dice-pit surfaces are a separate, older generator and are not
listed here: see `ui/pit/DieTexture.kt` under first-party below.

## 3D models and props

| File | Author | License | Source |
|---|---|---|---|
| _(none shipped — see "Deferred" below)_ | | | |

No glTF/GLB file is bundled, so `gltfio-android` is **not** a dependency of
this lane. Nothing to credit.

## Fonts

| File | Author | License | Source |
|---|---|---|---|
| _(none shipped — the app uses the platform typeface)_ | | | |

## First-party (no attribution required)

Generated in-repo and ours. Listed so that "is this credited anywhere?" always
has an answer, and so a future contributor does not go looking for a licence
that does not exist.

| Asset | Origin |
|---|---|
| `mipmap-*/ic_launcher*` | Pathfinder God — in-repo |
| Dice pit d20 mesh + atlas | Pathfinder God — procedural, `ui/pit/` |
| Dice pit felt / contact-shadow pixels | Pathfinder God — procedural, `ui/pit/DieTexture.kt` |
| Parchment and felt Compose surfaces | Pathfinder God — procedural, `ui/designsystem/GodTexture.kt` |
| `assets/rules/pathfinder_rag.db` | Pathfinder God device extract of the house rules DB — LFS, in-repo |
| Dice engine SFX (`assets/audio/*`) | see `audio-credits.md` |

## Licence texts

- CC0 1.0: <https://creativecommons.org/publicdomain/zero/1.0/>
- CC BY 3.0: <https://creativecommons.org/licenses/by/3.0/>
- CC BY 4.0: <https://creativecommons.org/licenses/by/4.0/>
- Apache-2.0 (Haze, Navigation Compose): <https://www.apache.org/licenses/LICENSE-2.0>
- OGL-3.0 (Quaternius, if a future pack ever needs it): <https://creativecommons.org/licenses/ogl/3.0/>

## Deferred in BP-06 WP-8

Recorded so the next person does not re-attempt the same dead ends.

- **Kenney CC0 icon packs** — **resolved in this pass.** The earlier note here
  claimed the download list was unreachable because it is rendered by
  JavaScript. That was wrong: the direct `.zip` link is present in the served
  HTML, inside the "Consider a donation" modal, and is written with
  **single-quoted** attributes. A search for `href="…"` misses it; a search for
  `href='…'` finds it. Both relevant packs were downloaded and their licence
  files read directly:

  ```powershell
  (Invoke-WebRequest 'https://kenney.nl/assets/<slug>' -UseBasicParsing).Content |
    Select-String -Pattern "href='(https://kenney\.nl/media/[^']*\.zip)'" -AllMatches
  ```

  - **Board Game Icons** (250 assets) — shipped, see above.
  - **Game Icons** (105 assets, the pack BP-06 §3 names) — **examined and
    rejected on fit, not on licence.** It is generic UI chrome: arrows, button
    faces, media transport, gamepads, shopping carts. It has no dice, sword,
    shield, map, chest or book, so it cannot carry the nine thematic
    destinations — using `gamepad` for Dice or `shoppingCart` for loot would be
    a semantic regression. Its `Vector/` folder also holds one merged
    path-per-sheet SVG with no per-icon `<symbol>` elements, so extracting
    individual glyphs would mean segmenting sub-paths blind, with no way to
    confirm the result renders correctly. Not used.
  - **UI Pack (RPG Expansion)** (85 assets) — also generic UI chrome (cursors,
    bars, panels, button states). Not used.

- **Quaternius / Kenney low-poly props** via `gltfio-android` — not attempted.
  BP-06 §3 makes them optional, and adding a native glTF dependency plus APK
  weight this late was not worth the build risk.

## Rules for anyone adding an asset

1. Prefer **CC0** — no attribution burden, survives forks and remixes.
2. Prefer **procedurally generated** — no licence, no fetch, no provenance to
   get wrong.
3. If the licence is **CC BY** anything, the entry is mandatory in **both** this
   file and the in-app credits screen, and the licence text must ship with the
   app.
4. If the licence is **anything else** — ND, NC, GPL — do not ship it. That is a
   blueprint decision, not a per-commit one.
5. Add the row in the same commit that adds the file, and **verify the file
   exists first**. `pg-license` fails the gate on any shipped file with no entry
   here or in `audio-credits.md`.