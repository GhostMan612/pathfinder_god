# Pit materials (prebuilt `.filamat`)

The Filament dice pit expects three binary material packages here:

| File | Kind |
|------|------|
| `die-1.76.0-r3.filamat` | Lit die face (baseColor + normal + roughness/metallic) |
| `felt-1.76.0-r3.filamat` | Table felt |
| `shadow-1.76.0-r3.filamat` | Contact shadow (transparent, no depth write) |

**These files are currently missing.** That is the primary reason the screen shows
"Pit failed to ignite."

## Why they matter

`PitMaterial.prepare` loads from assets first, then the on-device cache, then
attempts a runtime `MaterialBuilder` compile. Runtime compile is fragile
(ABI, GPU driver, Filament version skew) and is the path that currently fails
silently on many devices.

Shipping the prebuilts removes the runtime compile path for production builds
and recovers ~33 MB by letting us drop `filamat-android` later.

## How to bake (on a machine with Filament tools)

1. Use the exact fragment shaders + MaterialBuilder setup in
   `ui/pit/PitMaterial.kt` (VERSION, sampler names, uniforms, blending).
2. Compile with the matching Filament / filamat host tools (currently 1.76.0).
3. Drop the three resulting `.filamat` files into this directory using the
   names above.
4. Bump `PitMaterial.VERSION` if the material program changes so the cache
   key rotates.

Until the binaries land, the app will keep attempting runtime compile and will
log the exact failure under the `PitMaterial` tag in Logcat.
