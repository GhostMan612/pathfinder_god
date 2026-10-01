// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.pit

import kotlin.math.ceil
import kotlin.math.sqrt

data class DieAtlasGrid(
    val cols: Int,
    val rows: Int,
    val tile: Int,
) {
    val width: Int get() = cols * tile
    val height: Int get() = rows * tile
    val levels: Int get() = DieAtlas.levelCount(width, height)
    val slots: Int get() = cols * rows

    fun colOf(face: Int): Int = face % cols

    fun rowOf(face: Int): Int = face / cols

    fun tileOf(face: Int): DieAtlasTile = DieAtlasTile(this, face)
}

class DieAtlasTile(val grid: DieAtlasGrid, val face: Int) {
    val col: Int get() = grid.colOf(face)
    val row: Int get() = grid.rowOf(face)
    val left: Int get() = col * grid.tile
    val top: Int get() = row * grid.tile
    val centreX: Int get() = left + grid.tile / 2
    val centreY: Int get() = top + grid.tile / 2

    fun uvX(local: Float): Float = (col + local) / grid.cols

    fun uvY(local: Float): Float = 1f - (row + local) / grid.rows
}

class PitQuad(
    val positions: FloatArray,
    val uvs: FloatArray,
    val indices: ShortArray,
)

object PitRenderConfig {
    const val MSAA_SAMPLES = 4
    const val ANISOTROPY = 8f
    const val SHADOW_MAP_SIZE = 1024
    const val SHADOW_STEP_COUNT = 8
    const val FELT_SIZE = 128
    const val SHADOW_SIZE = 128
    const val DISCARDS_ON_DIE_CHANGE = true
}

object PitWorld {
    const val DIE_Y = 0.15f
    const val GROUND_Y = -1.30f
    const val DISC_Y = -1.285f
    const val GROUND_HALF = 5.5f
    const val DISC_RADIUS = 1.15f
    const val DISC_SEGMENTS = 48
    const val GROUND_TILES = 3f
    const val FOCUS_Y = 0.05f
    const val MIN_DISTANCE = 2.7f
    const val MAX_DISTANCE = 7.0f
    const val MIN_PITCH = 0.05f
    const val MAX_PITCH = 1.25f
    const val DEFAULT_YAW = 0.62f
    const val DEFAULT_PITCH = 0.40f
    const val DEFAULT_DISTANCE = 4.5f
    const val DIE_RADIUS = 1.08f

    fun eye(yaw: Float, pitch: Float, distance: Float): FloatArray {
        val cp = kotlin.math.cos(pitch)
        val sp = kotlin.math.sin(pitch)
        return floatArrayOf(
            distance * cp * kotlin.math.sin(yaw),
            FOCUS_Y + distance * sp,
            distance * cp * kotlin.math.cos(yaw),
        )
    }

    fun toDieDirection(eye: FloatArray): FloatArray = floatArrayOf(
        eye[0],
        eye[1] - DIE_Y,
        eye[2],
    )
}


object DieAtlas {

    const val TILE = 128
    const val BEVEL_BAND = 0.06f
    const val BEVEL_STRENGTH = 0.62f
    const val FLAT_XY = 0x7F80
    const val FLAT_Z = 0xFF

    fun gridFor(faces: Int, tile: Int = TILE): DieAtlasGrid {
        val cols = ceil(sqrt(faces.toDouble())).toInt().coerceAtLeast(1)
        val rows = ceil(faces.toDouble() / cols).toInt().coerceAtLeast(1)
        return DieAtlasGrid(cols, rows, tile)
    }

    fun levelCount(width: Int, height: Int): Int {
        var extent = maxOf(width, height)
        var levels = 1
        while (extent > 1) {
            extent = extent shr 1
            levels++
        }
        return levels
    }

    fun downsample(source: IntArray, width: Int, height: Int): IntArray {
        val w = maxOf(1, width shr 1)
        val h = maxOf(1, height shr 1)
        val out = IntArray(w * h)
        for (y in 0 until h) {
            val y0 = (y * 2).coerceAtMost(height - 1)
            val y1 = (y * 2 + 1).coerceAtMost(height - 1)
            for (x in 0 until w) {
                val x0 = (x * 2).coerceAtMost(width - 1)
                val x1 = (x * 2 + 1).coerceAtMost(width - 1)
                val a = source[y0 * width + x0]
                val b = source[y0 * width + x1]
                val c = source[y1 * width + x0]
                val d = source[y1 * width + x1]
                out[y * w + x] = pack(
                    averageChannel(a, b, c, d, 24),
                    averageChannel(a, b, c, d, 16),
                    averageChannel(a, b, c, d, 8),
                    averageChannel(a, b, c, d, 0),
                )
            }
        }
        return out
    }

    fun bevelNormals(
        faces: Int,
        kinds: IntArray,
        grid: DieAtlasGrid,
    ): IntArray {
        val pixels = IntArray(grid.width * grid.height) { flatNormal() }
        for (face in 0 until faces) {
            val kind = kinds[face]
            val count = cornerCount(kind)
            val corners = tileCorners(kind)
            val left = grid.colOf(face) * grid.tile
            val top = grid.rowOf(face) * grid.tile
            for (py in top until top + grid.tile) {
                for (px in left until left + grid.tile) {
                    val fx = (px - left + 0.5f) / grid.tile
                    val fy = (py - top + 0.5f) / grid.tile
                    if (!inside(corners, count, fx, fy)) continue
                    var best = Float.MAX_VALUE
                    var bx = 0f
                    var by = 0f
                    for (i in 0 until count) {
                        val j = (i + 1) % count
                        val ax = corners[i * 2]
                        val ay = corners[i * 2 + 1]
                        val ex = corners[j * 2] - ax
                        val ey = corners[j * 2 + 1] - ay
                        val len = ex * ex + ey * ey
                        val raw = if (len < 1e-12f) {
                            0f
                        } else {
                            ((fx - ax) * ex + (fy - ay) * ey) / len
                        }
                        val t = raw.coerceIn(0f, 1f)
                        val qx = fx - (ax + ex * t)
                        val qy = fy - (ay + ey * t)
                        val d2 = qx * qx + qy * qy
                        if (d2 < best) {
                            best = d2
                            bx = qx
                            by = qy
                        }
                    }
                    val d = sqrt(best)
                    if (d < 1e-5f) continue
                    val falloff = (1f - d / BEVEL_BAND).coerceIn(0f, 1f)
                    if (falloff <= 0f) continue
                    pixels[py * grid.width + px] = encodeNormal(
                        -bx / d * BEVEL_STRENGTH * falloff,
                        by / d * BEVEL_STRENGTH * falloff,
                    )
                }
            }
        }
        return pixels
    }

    fun feltPixels(size: Int): IntArray {
        val pixels = IntArray(size * size)
        val base = 0xFF1B3A2A.toInt()
        val lift = 0xFF2A5540.toInt()
        for (y in 0 until size) {
            for (x in 0 until size) {
                val weave = ((x / 2) + (y / 2)) % 2 == 0
                val grain = ((x * 7 + y * 13) % 17) / 17f
                val mix = (if (weave) 0.18f else 0f) + grain * 0.12f
                pixels[y * size + x] = blend(base, lift, mix.coerceIn(0f, 1f))
            }
        }
        return pixels
    }

    fun contactShadowPixels(size: Int): IntArray {
        val pixels = IntArray(size * size)
        val centre = size / 2f
        val radius = centre.toFloat()
        for (y in 0 until size) {
            for (x in 0 until size) {
                val dx = (x + 0.5f) - centre
                val dy = (y + 0.5f) - centre
                val r = kotlin.math.sqrt(dx * dx + dy * dy) / radius
                val alpha = ((1f - r).coerceIn(0f, 1f)).let { it * it * (3f - 2f * it) }
                pixels[y * size + x] = ((alpha * 255f + 0.5f).toInt().coerceIn(0, 255) shl 24)
            }
        }
        return pixels
    }

    fun groundQuad(halfExtent: Float, y: Float, tiles: Float = 3f): PitQuad = PitQuad(
        positions = floatArrayOf(
            -halfExtent, y, -halfExtent,
            -halfExtent, y, halfExtent,
            halfExtent, y, halfExtent,
            halfExtent, y, -halfExtent,
        ),
        uvs = floatArrayOf(0f, 0f, 0f, tiles, tiles, tiles, tiles, 0f),
        indices = shortArrayOf(0, 1, 2, 0, 2, 3),
    )

    fun contactDisc(radius: Float, y: Float, segments: Int): PitQuad {
        val rim = segments.coerceAtLeast(3)
        val positions = FloatArray((rim + 1) * 6)
        val uvs = FloatArray((rim + 1) * 4)
        val indices = ShortArray(rim * 3)
        positions[0] = 0f
        positions[1] = y
        positions[2] = 0f
        positions[3] = 0f
        positions[4] = 1f
        positions[5] = 0f
        uvs[0] = 0.5f
        uvs[1] = 0.5f
        for (i in 0 until rim) {
            val angle = 2.0 * Math.PI.toFloat() * i / rim
            val x = radius * kotlin.math.cos(angle)
            val z = radius * kotlin.math.sin(angle)
            val base = (i + 1) * 6
            positions[base] = x.toFloat()
            positions[base + 1] = y
            positions[base + 2] = z.toFloat()
            positions[base + 3] = 0f
            positions[base + 4] = 1f
            positions[base + 5] = 0f
            uvs[(i + 1) * 4 + 2] = (0.5f + 0.5f * kotlin.math.cos(angle)).toFloat()
            uvs[(i + 1) * 4 + 3] = (0.5f + 0.5f * kotlin.math.sin(angle)).toFloat()
        }
        for (i in 0 until rim) {
            indices[i * 3] = 0
            indices[i * 3 + 1] = (1 + (i + 1) % rim).toShort()
            indices[i * 3 + 2] = (1 + i).toShort()
        }
        return PitQuad(positions, uvs, indices)
    }

    fun cornerCount(kind: Int): Int = when (kind) {
        DieMeshBuilder.QUAD -> 4
        DieMeshBuilder.PENT -> 5
        else -> 3
    }

    fun tileCorners(kind: Int): FloatArray {
        val count = cornerCount(kind)
        val corners = FloatArray(count * 2)
        for (k in 0 until count) {
            val (x, y) = DieMeshBuilder.tileCorner(kind, k)
            corners[k * 2] = x
            corners[k * 2 + 1] = y
        }
        return corners
    }

    fun containsLocal(kind: Int, fx: Float, fy: Float): Boolean =
        inside(tileCorners(kind), cornerCount(kind), fx, fy)

    fun flatNormal(): Int = pack(FLAT_XY shr 8, FLAT_XY and 0xFF, FLAT_Z)

    fun encodeNormal(x: Float, y: Float): Int {
        val len = sqrt(x * x + y * y + 1f)
        val nx = x / len
        val ny = y / len
        val nz = 1f / len
        return pack(
            ((nx * 0.5f + 0.5f) * 255f + 0.5f).toInt().coerceIn(0, 255),
            ((ny * 0.5f + 0.5f) * 255f + 0.5f).toInt().coerceIn(0, 255),
            ((nz * 0.5f + 0.5f) * 255f + 0.5f).toInt().coerceIn(0, 255),
        )
    }

    fun toRgbaA(pixels: IntArray, opaque: Boolean): ByteArray {
        val out = ByteArray(pixels.size * 4)
        pixels.forEachIndexed { i, pixel ->
            out[i * 4] = ((pixel shr 16) and 0xFF).toByte()
            out[i * 4 + 1] = ((pixel shr 8) and 0xFF).toByte()
            out[i * 4 + 2] = (pixel and 0xFF).toByte()
            out[i * 4 + 3] = (if (opaque) 0xFF else (pixel ushr 24) and 0xFF).toByte()
        }
        return out
    }

    private fun inside(corners: FloatArray, count: Int, fx: Float, fy: Float): Boolean {
        var positive = 0
        var negative = 0
        for (i in 0 until count) {
            val j = (i + 1) % count
            val ax = corners[i * 2]
            val ay = corners[i * 2 + 1]
            val bx = corners[j * 2]
            val by = corners[j * 2 + 1]
            val cross = (bx - ax) * (fy - ay) - (by - ay) * (fx - ax)
            if (cross > 0f) positive++ else if (cross < 0f) negative++
        }
        return positive == 0 || negative == 0
    }

    private fun averageChannel(a: Int, b: Int, c: Int, d: Int, shift: Int): Int =
        (((a shr shift) and 0xFF) + ((b shr shift) and 0xFF) +
            ((c shr shift) and 0xFF) + ((d shr shift) and 0xFF) + 2) / 4

    private fun pack(r: Int, g: Int, b: Int): Int = pack(0xFF, r, g, b)

    private fun pack(a: Int, r: Int, g: Int, b: Int): Int =
        (a.coerceIn(0, 255) shl 24) or (r.coerceIn(0, 255) shl 16) or
            (g.coerceIn(0, 255) shl 8) or b.coerceIn(0, 255)

    private fun blend(a: Int, b: Int, t: Float): Int {
        val ar = (a shr 16) and 0xFF
        val ag = (a shr 8) and 0xFF
        val ab = a and 0xFF
        val br = (b shr 16) and 0xFF
        val bg = (b shr 8) and 0xFF
        val bb = b and 0xFF
        return pack(
            (ar + (br - ar) * t).toInt(),
            (ag + (bg - ag) * t).toInt(),
            (ab + (bb - ab) * t).toInt(),
        )
    }
}
