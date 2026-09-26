// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.pit

import android.content.Context
import com.google.android.filament.filamat.MaterialBuilder
import java.io.File

object PitMaterial {
    const val VERSION = "1.76.0"
    const val FILE_NAME = "die-1.76.0.filamat"

    fun definition(): String = """
        material {
            name : DieFace,
            parameters : [
                {
                    type : sampler2d,
                    name : baseColorMap
                }
            ],
            requires : [
                uv0
            ],
            shadingModel : unlit,
            blending : opaque
        }

        fragment {
            void material(inout MaterialInputs material) {
                prepareMaterial(material);
                material.baseColor = texture(materialParams_baseColorMap, getUV0());
            }
        }
    """.trimIndent()

    fun buildOrLoad(context: Context): ByteArray? {
        val dir = File(context.filesDir, "filament").apply { mkdirs() }
        val cached = File(dir, FILE_NAME)
        if (cached.exists()) {
            return try {
                cached.readBytes().takeIf { it.isNotEmpty() }
            } catch (_: Exception) {
                null
            }
        }
        return try {
            MaterialBuilder.init()
            val builder = MaterialBuilder()
            builder.name("DieFace")
            builder.material(definition())
            builder.shading(MaterialBuilder.Shading.UNLIT)
            builder.platform(MaterialBuilder.Platform.ALL)
            builder.targetApi(MaterialBuilder.TargetApi.ALL)
            val pack = builder.build()
            MaterialBuilder.shutdown()
            if (!pack.isValid) return null
            val buffer = pack.buffer
            val bytes = ByteArray(buffer.remaining())
            buffer.get(bytes)
            try {
                cached.writeBytes(bytes)
            } catch (_: Exception) {
            }
            bytes
        } catch (_: Exception) {
            null
        }
    }
}
