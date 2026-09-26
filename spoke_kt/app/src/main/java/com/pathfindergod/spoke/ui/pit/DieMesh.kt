// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.pit

import com.pathfindergod.spoke.ui.dice.Die
import kotlin.math.atan2
import kotlin.math.cos
import kotlin.math.sin
import kotlin.math.sqrt

data class DieMesh(
    val positions: FloatArray,
    val uvs: FloatArray,
    val indices: ShortArray,
    val faceNumbers: IntArray,
    val faceKinds: IntArray,
    val facePoints: List<List<FloatArray>>,
)

object DieMeshBuilder {
    const val COLS = 5
    const val ROWS = 4
    const val TRI = 0
    const val QUAD = 1
    const val PENT = 2

    private data class Poly(val verts: IntArray, val kind: Int)
    private data class Tri(val v: IntArray, val c: IntArray, val face: Int)

    fun tileCorner(kind: Int, k: Int): Pair<Float, Float> {
        if (kind == QUAD) {
            return when (k) {
                0 -> 0.15f to 0.15f
                1 -> 0.85f to 0.15f
                2 -> 0.85f to 0.85f
                else -> 0.15f to 0.85f
            }
        }
        if (kind == PENT) {
            val angle = -Math.PI.toFloat() / 2f + k * 2f * Math.PI.toFloat() / 5f
            return (0.5f + 0.36f * cos(angle)) to (0.5f + 0.36f * sin(angle))
        }
        return when (k) {
            0 -> 0.5f to 0.15f
            1 -> 0.15f to 0.85f
            else -> 0.85f to 0.85f
        }
    }

    fun build(die: Die): DieMesh = when (die) {
        Die.D4 -> assemble(tetrahedron(), 1, null)
        Die.D6 -> assemble(cube(), 1, 7)
        Die.D8 -> assemble(octahedron(), 1, 9)
        Die.D10 -> assemble(trapezohedron(), 0, 9)
        Die.D12 -> assemble(dodecahedron(), 1, 13)
        Die.D20 -> assemble(icosahedron(), 1, 21)
    }

    private fun tetrahedron(): Pair<List<FloatArray>, List<Poly>> {
        val verts = listOf(
            floatArrayOf(1f, 1f, 1f),
            floatArrayOf(1f, -1f, -1f),
            floatArrayOf(-1f, 1f, -1f),
            floatArrayOf(-1f, -1f, 1f),
        )
        val polys = listOf(
            Poly(intArrayOf(1, 2, 3), TRI),
            Poly(intArrayOf(0, 2, 3), TRI),
            Poly(intArrayOf(0, 1, 3), TRI),
            Poly(intArrayOf(0, 1, 2), TRI),
        )
        return verts to polys
    }

    private fun cube(): Pair<List<FloatArray>, List<Poly>> {
        val verts = listOf(
            floatArrayOf(1f, 1f, 1f),
            floatArrayOf(1f, -1f, 1f),
            floatArrayOf(1f, -1f, -1f),
            floatArrayOf(1f, 1f, -1f),
            floatArrayOf(-1f, 1f, 1f),
            floatArrayOf(-1f, 1f, -1f),
            floatArrayOf(-1f, -1f, -1f),
            floatArrayOf(-1f, -1f, 1f),
            floatArrayOf(1f, 1f, 1f),
            floatArrayOf(1f, 1f, -1f),
            floatArrayOf(-1f, 1f, -1f),
            floatArrayOf(-1f, 1f, 1f),
            floatArrayOf(1f, -1f, 1f),
            floatArrayOf(-1f, -1f, 1f),
            floatArrayOf(-1f, -1f, -1f),
            floatArrayOf(1f, -1f, -1f),
            floatArrayOf(1f, 1f, 1f),
            floatArrayOf(1f, -1f, 1f),
            floatArrayOf(-1f, -1f, 1f),
            floatArrayOf(-1f, 1f, 1f),
            floatArrayOf(1f, 1f, -1f),
            floatArrayOf(-1f, 1f, -1f),
            floatArrayOf(-1f, -1f, -1f),
            floatArrayOf(1f, -1f, -1f),
        )
        val polys = listOf(
            Poly(intArrayOf(0, 1, 2, 3), QUAD),
            Poly(intArrayOf(4, 5, 6, 7), QUAD),
            Poly(intArrayOf(8, 9, 10, 11), QUAD),
            Poly(intArrayOf(12, 13, 14, 15), QUAD),
            Poly(intArrayOf(16, 17, 18, 19), QUAD),
            Poly(intArrayOf(20, 21, 22, 23), QUAD),
        )
        return verts to polys
    }

    private fun octahedron(): Pair<List<FloatArray>, List<Poly>> {
        val verts = listOf(
            floatArrayOf(0f, 0f, 1f),
            floatArrayOf(0f, 0f, -1f),
            floatArrayOf(1f, 0f, 0f),
            floatArrayOf(0f, 1f, 0f),
            floatArrayOf(-1f, 0f, 0f),
            floatArrayOf(0f, -1f, 0f),
        )
        val polys = listOf(
            Poly(intArrayOf(0, 2, 3), TRI),
            Poly(intArrayOf(0, 3, 4), TRI),
            Poly(intArrayOf(0, 4, 5), TRI),
            Poly(intArrayOf(0, 5, 2), TRI),
            Poly(intArrayOf(1, 3, 2), TRI),
            Poly(intArrayOf(1, 4, 3), TRI),
            Poly(intArrayOf(1, 5, 4), TRI),
            Poly(intArrayOf(1, 2, 5), TRI),
        )
        return verts to polys
    }

    private fun trapezohedron(): Pair<List<FloatArray>, List<Poly>> {
        val apexH = 1.134f
        val ringH = apexH * 0.2245f / 2.1267f
        val verts = mutableListOf(
            floatArrayOf(0f, apexH, 0f),
            floatArrayOf(0f, -apexH, 0f),
        )
        for (i in 0 until 10) {
            val angle = i * Math.PI.toFloat() / 5f
            val y = if (i % 2 == 0) ringH else -ringH
            verts.add(floatArrayOf(cos(angle), y, sin(angle)))
        }
        fun ring(i: Int): Int = 2 + ((i % 10) + 10) % 10
        val polys = mutableListOf<Poly>()
        for (i in 0 until 5) {
            polys.add(
                Poly(
                    intArrayOf(0, ring(2 * i), ring(2 * i + 1), ring(2 * i + 2)),
                    QUAD,
                ),
            )
        }
        for (i in 0 until 5) {
            polys.add(
                Poly(
                    intArrayOf(1, ring(2 * i + 1), ring(2 * i), ring(2 * i - 1)),
                    QUAD,
                ),
            )
        }
        return verts to polys
    }

    private fun dodecahedron(): Pair<List<FloatArray>, List<Poly>> {
        val ratio = ((1.0 + sqrt(5.0)) / 2.0).toFloat()
        val ico = listOf(
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
        val icoFaces = listOf(
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
        val centroids = icoFaces.map { f ->
            floatArrayOf(
                (ico[f[0]][0] + ico[f[1]][0] + ico[f[2]][0]) / 3f,
                (ico[f[0]][1] + ico[f[1]][1] + ico[f[2]][1]) / 3f,
                (ico[f[0]][2] + ico[f[1]][2] + ico[f[2]][2]) / 3f,
            )
        }
        val polys = mutableListOf<Poly>()
        for (m in ico.indices) {
            val n = norm(ico[m])
            val ref = if (kotlin.math.abs(n[1]) < 0.9f) {
                floatArrayOf(0f, 1f, 0f)
            } else {
                floatArrayOf(1f, 0f, 0f)
            }
            val t1 = norm(cross(n, ref))
            val t2 = cross(n, t1)
            val adjacent = icoFaces.indices.filter { f -> m in icoFaces[f] }
            val ordered = adjacent.sortedBy { f ->
                val r = sub(centroids[f], scale(n, dot(centroids[f], n)))
                atan2(dot(r, t2), dot(r, t1))
            }
            polys.add(Poly(ordered.toIntArray(), PENT))
        }
        return centroids to polys
    }

    private fun icosahedron(): Pair<List<FloatArray>, List<Poly>> {
        val ratio = ((1.0 + sqrt(5.0)) / 2.0).toFloat()
        val verts = listOf(
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
        val polys = listOf(
            Poly(intArrayOf(0, 11, 5), TRI),
            Poly(intArrayOf(0, 5, 1), TRI),
            Poly(intArrayOf(0, 1, 7), TRI),
            Poly(intArrayOf(0, 7, 10), TRI),
            Poly(intArrayOf(0, 10, 11), TRI),
            Poly(intArrayOf(1, 5, 9), TRI),
            Poly(intArrayOf(5, 11, 4), TRI),
            Poly(intArrayOf(11, 10, 2), TRI),
            Poly(intArrayOf(10, 7, 6), TRI),
            Poly(intArrayOf(7, 1, 8), TRI),
            Poly(intArrayOf(3, 9, 4), TRI),
            Poly(intArrayOf(3, 4, 2), TRI),
            Poly(intArrayOf(3, 2, 6), TRI),
            Poly(intArrayOf(3, 6, 8), TRI),
            Poly(intArrayOf(3, 8, 9), TRI),
            Poly(intArrayOf(4, 9, 5), TRI),
            Poly(intArrayOf(2, 4, 11), TRI),
            Poly(intArrayOf(6, 2, 10), TRI),
            Poly(intArrayOf(8, 6, 7), TRI),
            Poly(intArrayOf(9, 8, 1), TRI),
        )
        return verts to polys
    }

    private fun assemble(
        shape: Pair<List<FloatArray>, List<Poly>>,
        low: Int,
        pairSum: Int?,
    ): DieMesh {
        val (verts, rawPolys) = shape
        val maxLen = verts.maxOf { v ->
            sqrt((v[0] * v[0] + v[1] * v[1] + v[2] * v[2]).toDouble()).toFloat()
        }
        val unit = verts.map { v ->
            floatArrayOf(v[0] / maxLen, v[1] / maxLen, v[2] / maxLen)
        }
        val polys = rawPolys.map { poly ->
            val pts = poly.verts.map { unit[it] }
            val n = newellOf(pts)
            val c = centroidOf(pts)
            if (n[0] * c[0] + n[1] * c[1] + n[2] * c[2] < 0f) {
                Poly(poly.verts.reversedArray(), poly.kind)
            } else {
                poly
            }
        }
        val tris = mutableListOf<Tri>()
        polys.forEachIndexed { fi, poly ->
            val corners = when (poly.kind) {
                QUAD -> listOf(
                    Triple(poly.verts[0], poly.verts[1], poly.verts[2]) to
                        intArrayOf(0, 1, 2),
                    Triple(poly.verts[0], poly.verts[2], poly.verts[3]) to
                        intArrayOf(0, 2, 3),
                )
                PENT -> (0 until 3).map { k ->
                    val idx = intArrayOf(0, 1 + k, 2 + k)
                    Triple(poly.verts[idx[0]], poly.verts[idx[1]], poly.verts[idx[2]]) to idx
                }
                else -> listOf(
                    Triple(poly.verts[0], poly.verts[1], poly.verts[2]) to
                        intArrayOf(0, 1, 2),
                )
            }
            corners.forEach { (vv, cc) ->
                tris.add(Tri(intArrayOf(vv.first, vv.second, vv.third), cc, fi))
            }
        }
        tris.forEach { tri ->
            val a = unit[tri.v[0]]
            val b = unit[tri.v[1]]
            val c = unit[tri.v[2]]
            val n = faceNormal(a, b, c)
            val g = centroid(a, b, c)
            if (n[0] * g[0] + n[1] * g[1] + n[2] * g[2] < 0f) {
                val tv = tri.v[1]
                tri.v[1] = tri.v[2]
                tri.v[2] = tv
                val tc = tri.c[1]
                tri.c[1] = tri.c[2]
                tri.c[2] = tc
            }
        }
        val faceNormals = polys.indices.map { fi ->
            val tri = tris.first { it.face == fi }
            faceNormal(unit[tri.v[0]], unit[tri.v[1]], unit[tri.v[2]])
        }
        val numbers = IntArray(polys.size)
        if (pairSum == null) {
            for (i in numbers.indices) numbers[i] = low + i
        } else {
            val assigned = BooleanArray(polys.size)
            var next = low
            for (i in numbers.indices) {
                if (assigned[i]) continue
                val mate = numbers.indices.firstOrNull { k ->
                    k != i && !assigned[k] &&
                        dot(faceNormals[i], faceNormals[k]) < -0.999f
                }
                numbers[i] = next
                assigned[i] = true
                if (mate != null) {
                    numbers[mate] = pairSum - next
                    assigned[mate] = true
                }
                next++
            }
        }
        val positions = FloatArray(tris.size * 9)
        val uvs = FloatArray(tris.size * 6)
        val indices = ShortArray(tris.size * 3) { it.toShort() }
        tris.forEachIndexed { ti, tri ->
            val kind = polys[tri.face].kind
            val col = tri.face % COLS
            val row = tri.face / COLS
            for (corner in 0 until 3) {
                val out = ti * 3 + corner
                val v = unit[tri.v[corner]]
                positions[out * 3] = v[0]
                positions[out * 3 + 1] = v[1]
                positions[out * 3 + 2] = v[2]
                val (fx, fy) = tileCorner(kind, tri.c[corner])
                uvs[out * 2] = (col + fx) / COLS
                uvs[out * 2 + 1] = 1f - (row + fy) / ROWS
            }
        }
        val points = polys.map { poly -> poly.verts.map { unit[it] } }
        return DieMesh(positions, uvs, indices, numbers, polys.map { it.kind }.toIntArray(), points)
    }

    private fun faceNormal(a: FloatArray, b: FloatArray, c: FloatArray): FloatArray {
        val u = floatArrayOf(b[0] - a[0], b[1] - a[1], b[2] - a[2])
        val v = floatArrayOf(c[0] - a[0], c[1] - a[1], c[2] - a[2])
        val n = floatArrayOf(
            u[1] * v[2] - u[2] * v[1],
            u[2] * v[0] - u[0] * v[2],
            u[0] * v[1] - u[1] * v[0],
        )
        return norm(n)
    }

    private fun centroid(a: FloatArray, b: FloatArray, c: FloatArray): FloatArray =
        floatArrayOf(
            (a[0] + b[0] + c[0]) / 3f,
            (a[1] + b[1] + c[1]) / 3f,
            (a[2] + b[2] + c[2]) / 3f,
        )

    private fun newellOf(corners: List<FloatArray>): FloatArray {
        var nx = 0f
        var ny = 0f
        var nz = 0f
        for (i in corners.indices) {
            val a = corners[i]
            val b = corners[(i + 1) % corners.size]
            nx += (a[1] - b[1]) * (a[2] + b[2])
            ny += (a[2] - b[2]) * (a[0] + b[0])
            nz += (a[0] - b[0]) * (a[1] + b[1])
        }
        return norm(floatArrayOf(nx, ny, nz))
    }

    private fun centroidOf(corners: List<FloatArray>): FloatArray {
        var x = 0f
        var y = 0f
        var z = 0f
        corners.forEach { x += it[0]; y += it[1]; z += it[2] }
        val n = corners.size.toFloat()
        return floatArrayOf(x / n, y / n, z / n)
    }

    private fun norm(v: FloatArray): FloatArray {
        val len = sqrt((v[0] * v[0] + v[1] * v[1] + v[2] * v[2]).toDouble()).toFloat()
        return floatArrayOf(v[0] / len, v[1] / len, v[2] / len)
    }

    private fun cross(a: FloatArray, b: FloatArray): FloatArray =
        floatArrayOf(
            a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0],
        )

    private fun sub(a: FloatArray, b: FloatArray): FloatArray =
        floatArrayOf(a[0] - b[0], a[1] - b[1], a[2] - b[2])

    private fun scale(v: FloatArray, s: Float): FloatArray =
        floatArrayOf(v[0] * s, v[1] * s, v[2] * s)

    private fun dot(a: FloatArray, b: FloatArray): Float =
        a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
}
