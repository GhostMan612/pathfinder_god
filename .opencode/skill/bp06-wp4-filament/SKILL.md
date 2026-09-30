---
name: bp06-wp4-filament
description: Use when doing BP-06 WP-4 (3D pit: lit shading, key light + IBL, shadows, MSAA/mipmaps, settle-to-face with centroid-normal tests, UI-thread and lifecycle fixes, prebuilt filamat) — gate G6-4, test-first rule, device checklist.
---

# BP-06 WP-4 — 3D pit

Requires WP-6 landed. Keep Filament `1.76.0`. No NDK, no CMake, no Swappy.

## Test-first rule
If the centroid-normal tests do not pass, you do not get an animation. Nail the geometry truth first.

## Files in scope
- `spoke_kt/app/src/main/java/com/pathfindergod/spoke/ui/pit/FilamentPit.kt`
- `spoke_kt/app/src/main/java/com/pathfindergod/spoke/ui/pit/PitMaterial.kt` (`unlit` at ~28)
- `spoke_kt/app/src/main/java/com/pathfindergod/spoke/ui/pit/DieTexture.kt`
- `spoke_kt/app/src/main/java/com/pathfindergod/spoke/ui/pit/DieMesh.kt`
- `spoke_kt/app/src/test/java/com/pathfindergod/spoke/ui/pit/DieMeshTest.kt`
- `spoke_kt/app/src/main/java/com/pathfindergod/spoke/ui/dice/DiceScreen.kt:80-86`

## Scope
- `PitMaterial`: `shadingModel: lit`, roughness/metallic, normal map for bevels. Today it is `unlit` with no lights at all, so the pit reads as flat cutouts.
- `LightManager` directional key light + IBL ambient. Felt-table ground plane with `castShadows` / `receiveShadows`. Contact shadow.
- MSAA via `SurfaceSwapChainConfig` with samples; mipmaps; aniso filtering; tone mapping + dithering. **Fix the UVs so `culling(false)` can be re-enabled** — it is a crutch, not a fix.
- **Settle-to-face:** capture each face's centroid normal at build time, animate the die so the *rolled* face points at the camera. `DiceScreen.kt:80-86` passes the die but not the rolled face, so 2D and 3D disagree. Extend `DieMeshTest` with per-face centroid-normal assertions **before** writing the animation.
- Perf/lifecycle (R-5…R-11): build meshes and textures off the UI thread (12.8 MB currently on it); shrink the atlas; retry `attach()`; full teardown including `flushAndWait()`; `LifecycleEventObserver` to pause rendering when backgrounded; camera orbit + pinch.
- Make **Pit the default**; move the Canvas/Pit toggle into Settings.
- ABI splits; ship a prebuilt `.filamat`, drop `filamat-android` → ~33 MB recovered.

## Commands
```
pg-build { "action": "testPit" }
pg-build { "action": "assembleDebug" }
pg-gate  { "wp": 4 }
```

## Gate G6-4 evidence
```
G6-4: PASS
build:   BUILD SUCCESSFUL
tests:   4 existing DieMeshTest cases + new per-face centroid-normal cases   (paste names)
device:  [HUMAN] all 6 solids
device:  [HUMAN] UV / number orientation correct
device:  [HUMAN] settle-to-face matches the 2D readout
device:  [HUMAN] pit holds display refresh rate
```
Never self-certify the device checks — mark the gate partial and hand the human the list.
