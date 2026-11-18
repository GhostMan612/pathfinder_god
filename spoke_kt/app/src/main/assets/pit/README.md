# Pit materials (prebuilt `.filamat`)

The Filament dice pit expects three binary material packages here:

| File | Kind |
|------|------|
| `die-1.76.0-r3.filamat` | Lit die face (baseColor + normal + roughness/metallic) |
| `felt-1.76.0-r3.filamat` | Table felt |
| `shadow-1.76.0-r3.filamat` | Contact shadow (transparent, no depth write) |

**These files are baked and shipped.** `PitMaterial` loads them from assets
first, then the on-device cache, and only falls back to a runtime
`MaterialBuilder` compile when neither exists. The runtime path is verified
on the BLU B160V (`PitMaterialSmokeTest`), but it can fail on other devices
for ABI/driver/Filament-skew reasons — and before the diagnostics it failed
silently, leaving only the "Pit failed to ignite" screen.

## Why they matter

Shipping the prebuilts removes the runtime compile path for production builds
and recovers ~33 MB by letting us drop `filamat-android` later (34.3 MB of
`libfilamat-jni.so` across the four debug ABIs).

## Bake sources

The `.mat` files next to this README are the bake sources, ported 1:1 from
`ui/pit/PitMaterial.kt` (same fragment shaders, sampler/uniform names,
blending and culling). They ship in the APK as documentation — a few KB —
and are inert at runtime; only the `.filamat` files are loaded.

- `die.mat` — `DieFace`, lit, `baseColorMap` + `normalMap` samplers,
  `roughness` / `metallic` float uniforms.
- `felt.mat` — `FeltTable`, lit, `baseColorMap` only, roughness 0.94.
- `shadow.mat` — `ContactShadow`, lit, `baseColorMap` only, transparent
  blending, no culling, no depth write.

## How to re-bake

Baked with `matc` from Filament 1.76.0 (the exact version the app links —
a mismatch is exactly the skew this avoids). Repeatable via
`spoke_kt/scripts/bake-pit-materials.sh`, or by hand:

```sh
# Linux: download filament-1.76.0-linux.tgz from
# https://github.com/google/filament/releases/tag/v1.76.0
# (use the release-assets API endpoint — the github.com redirect URL 404s
# behind some proxies) and extract bin/matc.
matc -p mobile -a opengl -a vulkan -o die-1.76.0-r3.filamat die.mat
matc -p mobile -a opengl -a vulkan -o felt-1.76.0-r3.filamat felt.mat
matc -p mobile -a opengl -a vulkan -o shadow-1.76.0-r3.filamat shadow.mat
```

Windows: the same commands with `matc.exe` from
`filament-1.76.0-windows.tgz` (or Git Bash / WSL with the Linux tools).

Verify with `matinfo` (same release): each binary must report
`Version: 76`, its material name (`DieFace` / `FeltTable` /
`ContactShadow`), `lit` shading, and `-p mobile -a opengl -a vulkan`.
The die binary must list the `roughness` / `metallic` uniforms and both
samplers; the shadow binary must list `Culling: none`,
`Blending: transparent`, `Depth write: false`.

Drop the three resulting `.filamat` files into this directory using the
names above (`PitMaterial.fileName()` / `assetPath()` derive them from
`Kind` + `VERSION`). Bump `PitMaterial.VERSION` if the material program
changes so the cache key rotates.
