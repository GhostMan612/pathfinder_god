# Pit materials (prebuilt `.filamat`)

The Filament dice pit expects three binary material packages here:

| File | Kind |
|------|------|
| `die-1.76.0-r3.filamat` | Lit die face (baseColor + normal + roughness/metallic) |
| `felt-1.76.0-r3.filamat` | Table felt |
| `shadow-1.76.0-r3.filamat` | Contact shadow (transparent, no depth write) |

**These files are currently missing.** Until they are baked, `PitMaterial`
falls back to compiling the same programs at runtime. That path is verified on
the BLU B160V (`PitMaterialSmokeTest`), but it can fail on other devices for
ABI/driver/Filament-skew reasons — and before the diagnostics in this change it
failed silently, leaving only the "Pit failed to ignite" screen. Missing
prebuilts are a common cause, not a universal one.

## Why they matter

`PitMaterial.prepare` loads from assets first, then the on-device cache, then
attempts a runtime `MaterialBuilder` compile. Runtime compile is fragile
(ABI, GPU driver, Filament version skew) and can fail silently.

Shipping the prebuilts removes the runtime compile path for production builds
and recovers ~33 MB by letting us drop `filamat-android` later (34.3 MB of
`libfilamat-jni.so` across the four debug ABIs).

## How to bake (on a machine with Filament tools)

1. Port the three fragment shaders to Filament `.mat` files, preserving the
   sampler (`baseColorMap`, `normalMap`) and uniform (`roughness`, `metallic`)
   names, blending and culling from `ui/pit/PitMaterial.kt`. The runtime
   `materialParams_*` names are what `FilamentPit` binds.
2. Compile each with `matc` from the matching Filament 1.76.0 release for the
   shipping backends/API levels. A prebuilt must target the same Filament
   version the app links; a mismatch is exactly the skew this avoids.
3. Drop the three resulting `.filamat` files into this directory using the
   names above (`PitMaterial.fileName()` / `assetPath()` derive them from
   `Kind` + `VERSION`).
4. Bump `PitMaterial.VERSION` if the material program changes so the cache
   key rotates.

Until the binaries land, the app will keep attempting runtime compile and will
log the exact failure under the `PitMaterial` tag in Logcat.
