// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.pit

import kotlin.math.sqrt

data class DieMesh(
    val positions: FloatArray,
    val uvs: FloatArray,
    val indices: ShortArray,
    val faceNumbers: IntArray,
)

object DieMeshBuilder {
    const val COLS = 5
    const val ROWS = 4
    const val FACE_COUNT = 20

    private val ratio = ((1.0 + sqrt(5.0)) / 2.0).toFloat()

    private val verts = arrayOf(
        floatArrayOf(-1f, ratio, 0f),
        floatArrayOf(1f, ratio, 0f),
        floatArrayOf(-1f, -ratio, 0f),
        floatArrayOf(1f, -ratio, 0f),
        floatArrayOf(0f, -1f, ratio),
        floatArrayOf(0f, 1f, ratio),
        floatArrayOf(0f, -1f, -ratio),
        floatArrayOf(0f, 1f, -ratio),
        floatArrayOf(ratio, 0f, -1f),
        floatArrayOf(ratio, 0f, 1f),
        floatArrayOf(-ratio, 0f, -1f),
        floatArrayOf(-ratio, 0f, 1f),
    )

    private val faces = arrayOf(
        intArrayOf(0, 11, 5),
        intArrayOf(0, 5, 1),
        intArrayOf(0, 1, 7),
        intArrayOf(0, 7, 10),
        intArrayOf(0, 10, 11),
        intArrayOf(1, 5, 9),
        intArrayOf(5, 11, 4),
        intArrayOf(11, 10, 2),
        intArrayOf(10, 7, 6),
        intArrayOf(7, 1, 8),
        intArrayOf(3, 9, 4),
        intArrayOf(3, 4, 2),
        intArrayOf(3, 2, 6),
        intArrayOf(3, 6, 8),
        intArrayOf(3, 8, 9),
        intArrayOf(4, 9, 5),
        intArrayOf(2, 4, 11),
        intArrayOf(6, 2, 10),
        intArrayOf(8, 6, 7),
        intArrayOf(9, 8, 1),
    )

    fun tileCorner(corner: Int): Pair<Float, Float> = when (corner) {
        0 -> 0.5f to 0.15f
        1 -> 0.15f to 0.85f
        else -> 0.85f to 0.85f
    }

    fun build(): DieMesh {
        val unit = verts.map { v ->
            val len = sqrt((v[0] * v[0] + v[1] * v[1] + v[2] * v[2]).toDouble()).toFloat()
            floatArrayOf(v[0] / len, v[1] / len, v[2] / len)
        }
        val wound = faces.map { f ->
            val normal = faceNormal(unit[f[0]], unit[f[1]], unit[f[2]])
            val centroid = centroid(unit[f[0]], unit[f[1]], unit[f[2]])
            val outward = normal[0] * centroid[0] + normal[1] * centroid[1] +
                normal[2] * centroid[2]
            if (outward < 0f) intArrayOf(f[0], f[2], f[1]) else f
        }
        val normals = wound.map { f -> faceNormal(unit[f[0]], unit[f[1]], unit[f[2]]) }
        val numbers = IntArray(FACE_COUNT)
        var next = 1
        for (i in 0 until FACE_COUNT) {
            if (numbers[i] != 0) continue
            val mate = (0 until FACE_COUNT).first { k ->
                k != i && numbers[k] == 0 && dot(normals[i], normals[k]) < -0.999f
            }
            numbers[i] = next
            numbers[mate] = 21 - next
            next++
        }
        val positions = FloatArray(FACE_COUNT * 9)
        val uvs = FloatArray(FACE_COUNT * 6)
        val indices = ShortArray(FACE_COUNT * 3) { it.toShort() }
        for (face in 0 until FACE_COUNT) {
            val col = face % COLS
            val row = face / COLS
            for (corner in 0 until 3) {
                val out = face * 3 + corner
                val v = unit[wound[face][corner]]
                positions[out * 3] = v[0]
                positions[out * 3 + 1] = v[1]
                positions[out * 3 + 2] = v[2]
                val (fx, fy) = tileCorner(corner)
                uvs[out * 2] = (col + fx) / COLS
                uvs[out * 2 + 1] = 1f - (row + fy) / ROWS
            }
        }
        return DieMesh(positions, uvs, indices, numbers)
    }

    private fun faceNormal(a: FloatArray, b: FloatArray, c: FloatArray): FloatArray {
        val u = floatArrayOf(b[0] - a[0], b[1] - a[1], b[2] - a[2])
        val v = floatArrayOf(c[0] - a[0], c[1] - a[1], c[2] - a[2])
        val n = floatArrayOf(
            u[1] * v[2] - u[2] * v[1],
            u[2] * v[0] - u[0] * v[2],
            u[0] * v[1] - u[1] * v[0],
        )
        val len = sqrt((n[0] * n[0] + n[1] * n[1] + n[2] * n[2]).toDouble()).toFloat()
        return floatArrayOf(n[0] / len, n[1] / len, n[2] / len)
    }

    private fun centroid(a: FloatArray, b: FloatArray, c: FloatArray): FloatArray =
        floatArrayOf(
            (a[0] + b[0] + c[0]) / 3f,
            (a[1] + b[1] + c[1]) / 3f,
            (a[2] + b[2] + c[2]) / 3f,
        )

    private fun dot(a: FloatArray, b: FloatArray): Float =
        a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
}
