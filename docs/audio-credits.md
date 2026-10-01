# Audio credits (royalty-free)

Every bundled sound is either CC0 (no attribution required, credited anyway)
or CC-BY (attribution required — given here **and** in the app's
**Setup → Audio Credits** screen). Personal use is fine under all of them;
keep this file with any redistribution.

This register is the in-repo half of the CC BY obligation. The in-app half is
`spoke_kt/app/src/main/java/com/pathfindergod/spoke/ui/settings/AudioCreditsScreen.kt`,
reachable from **Setup → AUDIO CREDITS**. The two must stay in step: a credit
that exists in only one of them does not discharge the licence.

## Background music (Spoke)

| File | Track | Author | License | Source |
|---|---|---|---|---|
| `spoke_kt/app/src/main/assets/audio/bgm_tavern.mp3` | "The Old Tower Inn" | RandomMind | CC0 1.0 | <https://opengameart.org/content/medieval-the-old-tower-inn> |
| `spoke_kt/app/src/main/assets/audio/bgm_inn.mp3` | "Inn Music" | tcarisland | **CC BY 4.0 — attribution required** | <https://opengameart.org/content/inn-music> |

## Sound effects (Spoke + Command Center)

| File | Role in app | From | Author | License | Source |
|---|---|---|---|---|---|
| `spoke_kt/app/src/main/assets/audio/dice_roll.ogg` | dice clatter | 80 CC0 RPG SFX | via OpenGameArt.org contributors | CC0 1.0 | <https://opengameart.org/content/80-cc0-rpg-sfx> |
| `spoke_kt/app/src/main/assets/audio/dice_fail.ogg` | critical failure | 80 CC0 RPG SFX | via OpenGameArt.org contributors | CC0 1.0 | <https://opengameart.org/content/80-cc0-rpg-sfx> |
| `spoke_kt/app/src/main/assets/audio/error.ogg` | validation error, combat damage | 100 CC0 SFX | via OpenGameArt.org contributors | CC0 1.0 | <https://opengameart.org/content/100-cc0-sfx> |
| `spoke_kt/app/src/main/assets/audio/dice_crit.wav` | critical success | RPG Sound Pack (Heroes of Hawks Haven) | Tuomo Untinen | **CC BY 3.0 — attribution required** | <https://opengameart.org/content/rpg-sound-pack> |
| `spoke_kt/app/src/main/assets/audio/tap.wav` | UI clicks, tab change | RPG Sound Pack (Heroes of Hawks Haven) | Tuomo Untinen | **CC BY 3.0 — attribution required** | <https://opengameart.org/content/rpg-sound-pack> |

## Modifications

All seven files are bundled byte-for-byte as published. Modifications happen at
playback only: the background tracks are looped, crossfaded between selection and
volume-ducked under sound effects; the effects are replayed at a randomised
pitch (within ±8%, scaled by die size). No file has been edited, trimmed or
re-encoded.

## License texts

- CC0 1.0 Universal: <https://creativecommons.org/publicdomain/zero/1.0/>
- CC BY 4.0: <https://creativecommons.org/licenses/by/4.0/>
- CC BY 3.0: <https://creativecommons.org/licenses/by/3.0/>

## Retired tooling

The synthesized WAVs that `tools/gen_audio.py` used to produce were replaced by
the licensed tracks above, and both `tools/gen_audio.py` and
`tools/fetch_audio.py` were deleted in BP-06 WP-2. Neither is needed to
regenerate anything, and `fetch_audio.py` in particular wrote plain-text URL
bytes under audio extensions and appended credit lines for files that were never
created — the false Pixabay/Freesound entries this register used to carry.

**Do not re-add a credit line for a file that is not in
`spoke_kt/app/src/main/assets/audio/`.** A credit for an absent asset is a false
attribution, which is worse than a missing one. Run `pg-license` after any audio
change; it reports uncredited and orphan media.
