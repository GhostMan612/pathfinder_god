// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.pit

import android.content.Context
import com.google.android.filament.Filament
import com.google.android.filament.filamat.MaterialBuilder
import java.io.File

object PitMaterial {

    const val VERSION = "1.76.0"
    const val CACHE_DIR = "filament"
    const val ASSET_DIR = "pit"
    const val NAME = "DieFace"

    const val ROUGHNESS = 0.52f
    const val METALLIC = 0.04f
    const val FELT_ROUGHNESS = 0.94f

    enum class Kind { DIE, FELT, SHADOW }

    fun fileName(kind: Kind): String = "${kind.name.lowercase()}-$VERSION.filamat"

    fun assetPath(kind: Kind): String = "$ASSET_DIR/${fileName(kind)}"

    fun definition(kind: Kind): String = when (kind) {
        Kind.DIE -> """
            material {
                name : $NAME,
                shadingModel : lit,
            }
            fragment {
                void material(inout MaterialInputs material) {
                    material.baseColor = vec3(0.8, 0.8, 0.8);
                }
            }
        """.trimIndent()
        Kind.FELT -> """
            material {
                name : FeltTable,
                shadingModel : lit,
            }
            fragment {
                void material(inout MaterialInputs material) {
                    material.baseColor = vec3(0.5, 0.5, 0.5);
                }
            }
        """.trimIndent()
        Kind.SHADOW -> """
            material {
                name : ContactShadow,
                shadingModel : lit,
                blending : transparent,
                culling : none,
            }
            fragment {
                void material(inout MaterialInputs material) {
                    material.baseColor = vec3(0.0, 0.0, 0.0, 0.5);
                }
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
            } else {
                missing.add(kind)
            }
        }
        if (missing.isNotEmpty() && !compile(context, missing, resolved)) {
            return emptyMap()
        }
        return resolved
    }

    fun readAsset(context: Context, kind: Kind): ByteArray? = try {
        context.assets.open(assetPath(kind)).use { stream ->
            val bytes = stream.readBytes()
            if (bytes.isEmpty()) null else bytes
        }
    } catch (_: Exception) {
        null
    }

    fun readCache(context: Context, kind: Kind): ByteArray? = try {
        val file = cacheFile(context, kind)
        if (!file.exists()) {
            null
        } else {
            file.readBytes().takeIf { it.isNotEmpty() }
        }
    } catch (_: Exception) {
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
                val bytes = compileOne(kind) ?: return false
                runCatching { File(dir, fileName(kind)).writeBytes(bytes) }
                resolved[kind] = bytes
            }
            true
        } catch (_: Throwable) {
            false
        } finally {
            if (initialised) {
                runCatching { MaterialBuilder.shutdown() }
            }
        }
    }

    private fun compileOne(kind: Kind): ByteArray? = try {
        val builder = MaterialBuilder()
        builder.name(nameOf(kind))
        builder.material(definition(kind))
        val pack = builder.build()
        if (!pack.isValid) {
            null
        } else {
            val buffer = pack.buffer
            val bytes = ByteArray(buffer.remaining())
            buffer.get(bytes)
            bytes
        }
    } catch (_: Throwable) {
        null
    }

    private fun nameOf(kind: Kind): String = when (kind) {
        Kind.DIE -> NAME
        Kind.FELT -> "FeltTable"
        Kind.SHADOW -> "ContactShadow"
    }
}
