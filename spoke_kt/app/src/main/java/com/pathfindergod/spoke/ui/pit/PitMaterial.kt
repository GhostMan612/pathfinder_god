// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.pit

import android.content.Context
import android.util.Log
import com.google.android.filament.Filament
import com.google.android.filament.filamat.MaterialBuilder
import java.io.File

object PitMaterial {

    private const val TAG = "PitMaterial"

    // Bump when the runtime material program changes; the file name is the cache key.
    const val VERSION = "1.76.0-r3"
    const val CACHE_DIR = "filament"
    const val ASSET_DIR = "pit"
    const val NAME = "DieFace"

    const val ROUGHNESS = 0.52f
    const val METALLIC = 0.04f
    const val FELT_ROUGHNESS = 0.94f

    enum class Kind { DIE, FELT, SHADOW }

    fun fileName(kind: Kind): String = "${kind.name.lowercase()}-$VERSION.filamat"

    fun assetPath(kind: Kind): String = "$ASSET_DIR/${fileName(kind)}"

    /**
     * MaterialBuilder in filamat-android compiles a fragment function, not a `.mat`
     * source file. Keep the uniforms and UV requirement explicit here.
     */
    fun fragmentShader(kind: Kind): String = when (kind) {
        Kind.DIE -> """
            void material(inout MaterialInputs material) {
                prepareMaterial(material);
                material.baseColor = texture(materialParams_baseColorMap, getUV0());
                // Sample normal map in tangent space; Filament expects the vector in material.normal
                // after prepareMaterial has set up the TBN basis.
                vec3 n = texture(materialParams_normalMap, getUV0()).xyz * 2.0 - 1.0;
                material.normal = n;
                material.roughness = materialParams.roughness;
                material.metallic = materialParams.metallic;
            }
        """.trimIndent()
        Kind.FELT -> """
            void material(inout MaterialInputs material) {
                prepareMaterial(material);
                material.baseColor = texture(materialParams_baseColorMap, getUV0());
                material.roughness = $FELT_ROUGHNESS;
                material.metallic = 0.0;
            }
        """.trimIndent()
        Kind.SHADOW -> """
            void material(inout MaterialInputs material) {
                prepareMaterial(material);
                material.baseColor = texture(materialParams_baseColorMap, getUV0());
            }
        """.trimIndent()
    }

    fun prepare(context: Context, kinds: List<Kind>): Map<Kind, ByteArray> {
        val resolved = LinkedHashMap<Kind, ByteArray>()
        val missing = ArrayList<Kind>()
        kinds.distinct().forEach { kind ->
            val shipped = readAsset(context, kind)
            val cached = readCache(context, kind)
            val bytes = shipped ?: cached
            if (bytes != null) {
                resolved[kind] = bytes
                Log.d(TAG, "loaded ${kind.name} from ${if (shipped != null) "assets" else "cache"} (${bytes.size} B)")
            } else {
                missing.add(kind)
                Log.w(TAG, "no prebuilt/cache for ${kind.name}; will attempt runtime compile")
            }
        }
        if (missing.isNotEmpty()) {
            val ok = compile(context, missing, resolved)
            if (!ok) {
                Log.e(TAG, "runtime compile failed for: ${missing.joinToString { it.name }}")
                return emptyMap()
            }
        }
        return resolved
    }

    fun readAsset(context: Context, kind: Kind): ByteArray? = try {
        context.assets.open(assetPath(kind)).use { stream ->
            val bytes = stream.readBytes()
            if (bytes.isEmpty()) null else bytes
        }
    } catch (e: Exception) {
        Log.d(TAG, "asset miss ${assetPath(kind)}: ${e.message}")
        null
    }

    fun readCache(context: Context, kind: Kind): ByteArray? = try {
        val file = cacheFile(context, kind)
        if (!file.exists()) {
            null
        } else {
            file.readBytes().takeIf { it.isNotEmpty() }
        }
    } catch (e: Exception) {
        Log.d(TAG, "cache miss ${fileName(kind)}: ${e.message}")
        null
    }

    fun cacheFile(context: Context, kind: Kind): File =
        File(File(context.filesDir, CACHE_DIR), fileName(kind))

    private fun compile(
        context: Context,
        missing: List<Kind>,
        resolved: MutableMap<Kind, ByteArray>,
    ): Boolean {
        var initialised = false
        return try {
            runCatching { Filament.init() }
            MaterialBuilder.init()
            initialised = true
            val dir = File(context.filesDir, CACHE_DIR).apply { mkdirs() }
            missing.forEach { kind ->
                val bytes = compileOne(kind)
                if (bytes == null) {
                    Log.e(TAG, "compileOne(${kind.name}) returned null")
                    return false
                }
                runCatching { File(dir, fileName(kind)).writeBytes(bytes) }
                    .onFailure { Log.w(TAG, "failed to write cache for ${kind.name}", it) }
                resolved[kind] = bytes
                Log.i(TAG, "compiled ${kind.name} (${bytes.size} B)")
            }
            true
        } catch (t: Throwable) {
            Log.e(TAG, "MaterialBuilder compile path threw", t)
            false
        } finally {
            if (initialised) {
                runCatching { MaterialBuilder.shutdown() }
            }
        }
    }

    private fun compileOne(kind: Kind): ByteArray? = try {
        val builder = MaterialBuilder()
            .platform(MaterialBuilder.Platform.MOBILE)
            .name(nameOf(kind))
            .shading(MaterialBuilder.Shading.LIT)
            .require(MaterialBuilder.VertexAttribute.UV0)
            .samplerParameter(
                MaterialBuilder.SamplerType.SAMPLER_2D,
                MaterialBuilder.SamplerFormat.FLOAT,
                MaterialBuilder.ParameterPrecision.DEFAULT,
                "baseColorMap",
            )
            .material(fragmentShader(kind))
            .optimization(MaterialBuilder.Optimization.NONE)

        when (kind) {
            Kind.DIE -> {
                builder
                    .samplerParameter(
                        MaterialBuilder.SamplerType.SAMPLER_2D,
                        MaterialBuilder.SamplerFormat.FLOAT,
                        MaterialBuilder.ParameterPrecision.DEFAULT,
                        "normalMap",
                    )
                    .uniformParameter(MaterialBuilder.UniformType.FLOAT, "roughness")
                    .uniformParameter(MaterialBuilder.UniformType.FLOAT, "metallic")
            }
            Kind.SHADOW -> {
                builder
                    .blending(MaterialBuilder.BlendingMode.TRANSPARENT)
                    .culling(MaterialBuilder.CullingMode.NONE)
                    .depthWrite(false)
            }
            Kind.FELT -> builder
        }

        val pack = builder.build()
        if (!pack.isValid) {
            Log.e(TAG, "MaterialBuilder.build() invalid for ${kind.name}")
            null
        } else {
            val buffer = pack.buffer
            val bytes = ByteArray(buffer.remaining())
            buffer.get(bytes)
            bytes
        }
    } catch (t: Throwable) {
        Log.e(TAG, "compileOne(${kind.name}) exception", t)
        null
    }

    private fun nameOf(kind: Kind): String = when (kind) {
        Kind.DIE -> NAME
        Kind.FELT -> "FeltTable"
        Kind.SHADOW -> "ContactShadow"
    }
}
