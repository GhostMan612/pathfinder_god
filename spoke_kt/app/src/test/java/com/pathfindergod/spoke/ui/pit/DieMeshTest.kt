// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.pit

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.math.sqrt

class DieMeshTest {

    @Test
    fun layoutCounts() {
        val mesh = DieMeshBuilder.build()
        assertEquals(20 * 9, mesh.positions.size)
        assertEquals(20 * 6, mesh.uvs.size)
        assertEquals(60, mesh.indices.size)
        assertEquals(20, mesh.faceNumbers.size)
        mesh.indices.forEachIndexed { i, s -> assertEquals(i.toShort(), s) }
    }

    @Test
    fun numbersFormOppositePairs() {
        val mesh = DieMeshBuilder.build()
        assertEquals((1..20).toList(), mesh.faceNumbers.sorted().toList())
        val normals = faceNormals(mesh)
        for (i in 0 until 20) {
            val mate = (0 until 20).first { k ->
                k != i && dot(normals[i], normals[k]) < -0.999f
            }
            assertEquals(21, mesh.faceNumbers[i] + mesh.faceNumbers[mate])
        }
    }

    @Test
    fun facesWoundOutward() {
        val mesh = DieMeshBuilder.build()
        for (face in 0 until 20) {
            val a = vert(mesh, face, 0)
            val b = vert(mesh, face, 1)
            val c = vert(mesh, face, 2)
            val n = normal(a, b, c)
            val cx = (a[0] + b[0] + c[0]) / 3f
            val cy = (a[1] + b[1] + c[1]) / 3f
            val cz = (a[2] + b[2] + c[2]) / 3f
            assertTrue(n[0] * cx + n[1] * cy + n[2] * cz > 0f)
        }
    }

    @Test
    fun uvsInsideUnitSquare() {
        val mesh = DieMeshBuilder.build()
        mesh.uvs.forEach { uv -> assertTrue(uv >= 0f && uv <= 1f) }
    }

    private fun vert(mesh: DieMesh, face: Int, corner: Int): FloatArray {
        val o = (face * 3 + corner) * 3
        return floatArrayOf(mesh.positions[o], mesh.positions[o + 1], mesh.positions[o + 2])
    }

    private fun normal(a: FloatArray, b: FloatArray, c: FloatArray): FloatArray {
        val ux = b[0] - a[0]
        val uy = b[1] - a[1]
        val uz = b[2] - a[2]
        val vx = c[0] - a[0]
        val vy = c[1] - a[1]
        val vz = c[2] - a[2]
        val n = floatArrayOf(
            uy * vz - uz * vy,
            uz * vx - ux * vz,
            ux * vy - uy * vx,
        )
        val len = sqrt((n[0] * n[0] + n[1] * n[1] + n[2] * n[2]).toDouble()).toFloat()
        return floatArrayOf(n[0] / len, n[1] / len, n[2] / len)
    }

    private fun dot(a: FloatArray, b: FloatArray): Float =
        a[0] * b[0] + a[1] * b[1] + a[2] * b[2]

    private fun faceNormals(mesh: DieMesh): List<FloatArray> =
        (0 until 20).map { f -> normal(vert(mesh, f, 0), vert(mesh, f, 1), vert(mesh, f, 2)) }
}
