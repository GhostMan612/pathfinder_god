// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.map

import android.content.Context
import android.util.Log
import com.google.android.filament.Filament
import com.google.android.filament.filamat.MaterialBuilder
import java.io.File

private const val TAG = "MapDioramaMaterial"

object MapDioramaMaterial {

    // Bump when the runtime material program changes; the file name is the cache key.
    const val VERSION = "1.76.0-r2"
    const val NAME = "MapSurface"
    const val FILE_NAME = "map-surface-$VERSION.filamat"

    fun fragmentShader(): String = """
        void material(inout MaterialInputs material) {
            prepareMaterial(material);
            material.baseColor = materialParams.baseColor;
            material.roughness = materialParams.roughness;
            material.metallic = materialParams.metallic;
        }
    """.trimIndent()

    fun prepare(context: Context): ByteArray? {
        synchronized(this) {
            val file = cacheFile(context)
            file.parentFile?.mkdirs()
            readFile(file)?.let { return it }
            val bytes = compile() ?: return null
            runCatching { file.writeBytes(bytes) }
            return bytes
        }
    }

    private fun cacheFile(context: Context): File =
        File(File(context.filesDir, "filament"), FILE_NAME)

    private fun readFile(file: File): ByteArray? = runCatching {
        if (file.exists()) file.readBytes().takeIf { it.isNotEmpty() } else null
    }.getOrNull()

    private fun compile(): ByteArray? {
        var initialised = false
        return try {
            runCatching { Filament.init() }
            MaterialBuilder.init()
            initialised = true
            val builder = MaterialBuilder()
                .platform(MaterialBuilder.Platform.MOBILE)
                .name(NAME)
                .shading(MaterialBuilder.Shading.LIT)
                .uniformParameter(MaterialBuilder.UniformType.FLOAT4, "baseColor")
                .uniformParameter(MaterialBuilder.UniformType.FLOAT, "roughness")
                .uniformParameter(MaterialBuilder.UniformType.FLOAT, "metallic")
                .culling(MaterialBuilder.CullingMode.NONE)
                .material(fragmentShader())
                .optimization(MaterialBuilder.Optimization.NONE)
            val pack = builder.build()
            if (!pack.isValid) {
                null
            } else {
                val buffer = pack.buffer
                ByteArray(buffer.remaining()).also { buffer.get(it) }
            }
        } catch (t: Throwable) {
            Log.e(TAG, "compile threw", t)
            null
        } finally {
            if (initialised) {
                runCatching { MaterialBuilder.shutdown() }
            }
        }
    }
}

object MapPalette {

    fun parseColor(hex: String): FloatArray? {
        val text = hex.trim().removePrefix("#")
        if (text.length != 6) return null
        val value = text.toIntOrNull(16) ?: return null
        return floatArrayOf(
            ((value shr 16) and 0xFF) / 255f,
            ((value shr 8) and 0xFF) / 255f,
            (value and 0xFF) / 255f,
        )
    }

    fun colorFor(kind: MapSurfaceKind): FloatArray = when (kind) {
        MapSurfaceKind.GROUND -> floatArrayOf(0.055f, 0.062f, 0.075f)
        MapSurfaceKind.FLOOR_STONE -> floatArrayOf(0.42f, 0.38f, 0.33f)
        MapSurfaceKind.FLOOR_VAULT -> floatArrayOf(0.32f, 0.36f, 0.44f)
        MapSurfaceKind.FLOOR_TAVERN -> floatArrayOf(0.50f, 0.38f, 0.27f)
        MapSurfaceKind.WALL -> floatArrayOf(0.24f, 0.26f, 0.30f)
        MapSurfaceKind.WOOD -> floatArrayOf(0.40f, 0.26f, 0.15f)
        MapSurfaceKind.STONE -> floatArrayOf(0.56f, 0.53f, 0.48f)
        MapSurfaceKind.METAL -> floatArrayOf(0.36f, 0.38f, 0.41f)
        MapSurfaceKind.FLAME -> floatArrayOf(1.0f, 0.48f, 0.10f)
    }

    fun roughnessFor(kind: MapSurfaceKind): Float = when (kind) {
        MapSurfaceKind.METAL -> 0.42f
        MapSurfaceKind.FLAME -> 0.55f
        MapSurfaceKind.WOOD -> 0.78f
        MapSurfaceKind.GROUND -> 0.95f
        else -> 0.90f
    }

    fun metallicFor(kind: MapSurfaceKind): Float = when (kind) {
        MapSurfaceKind.METAL -> 0.65f
        else -> 0f
    }
}
