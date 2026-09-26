// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.pit

import com.pathfindergod.spoke.ui.dice.Die
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.math.sqrt

class DieMeshTest {

    private data class Expectation(
        val faces: Int,
        val numbers: List<Int>,
        val pairSum: Int?,
    )

    private val expectations = mapOf(
        Die.D4 to Expectation(4, (1..4).toList(), null),
        Die.D6 to Expectation(6, (1..6).toList(), 7),
        Die.D8 to Expectation(8, (1..8).toList(), 9),
        Die.D10 to Expectation(10, (0..9).toList(), 9),
        Die.D12 to Expectation(12, (1..12).toList(), 13),
        Die.D20 to Expectation(20, (1..20).toList(), 21),
    )

    @Test
    fun everyDieBuildsCleanly() {
        for (die in Die.entries) {
            val mesh = DieMeshBuilder.build(die)
            val expect = expectations.getValue(die)
            assertEquals(expect.faces, expect.faces.let { mesh.faceNumbers.size })
            assertEquals(expect.numbers.sorted(), mesh.faceNumbers.sorted().toList())
            val tris = mesh.indices.size / 3
            assertEquals(tris * 9, mesh.positions.size)
            assertEquals(tris * 6, mesh.uvs.size)
            assertEquals(expect.faces, mesh.faceKinds.size)
            assertEquals(expect.faces, mesh.facePoints.size)
            mesh.uvs.forEach { uv -> assertTrue("$die uv $uv", uv >= 0f && uv <= 1f) }
        }
    }

    @Test
    fun facesWoundOutward() {
        for (die in Die.entries) {
            val mesh = DieMeshBuilder.build(die)
            mesh.facePoints.forEach { corners ->
                val n = newell(corners)
                val c = centroidOf(corners)
                assertTrue(
                    "$die outward ${n[0] * c[0] + n[1] * c[1] + n[2] * c[2]}",
                    n[0] * c[0] + n[1] * c[1] + n[2] * c[2] > 0f,
                )
            }
        }
    }

    @Test
    fun quadFacesArePlanar() {
        for (die in listOf(Die.D6, Die.D10, Die.D12)) {
            val mesh = DieMeshBuilder.build(die)
            mesh.facePoints.forEach { corners ->
                val a = corners[0]
                val b = corners[1]
                val c = corners[2]
                val d = corners[3 % corners.size]
                val volume = scalarTriple(sub(b, a), sub(c, a), sub(d, a))
                assertTrue("$die planar $volume", kotlin.math.abs(volume) < 1e-4f)
            }
        }
    }

    @Test
    fun oppositeFacesSumCorrectly() {
        for (die in Die.entries) {
            val sum = expectations.getValue(die).pairSum ?: continue
            val mesh = DieMeshBuilder.build(die)
            val normals = mesh.facePoints.map { newell(it) }
            for (i in mesh.faceNumbers.indices) {
                val mate = normals.indices.first { k ->
                    k != i && dot(normals[i], normals[k]) < -0.999f
                }
                assertEquals(
                    "$die faces $i/$mate",
                    sum,
                    mesh.faceNumbers[i] + mesh.faceNumbers[mate],
                )
            }
        }
    }

    private fun newell(corners: List<FloatArray>): FloatArray {
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
        val len = sqrt((nx * nx + ny * ny + nz * nz).toDouble()).toFloat()
        return floatArrayOf(nx / len, ny / len, nz / len)
    }

    private fun centroidOf(corners: List<FloatArray>): FloatArray {
        var x = 0f
        var y = 0f
        var z = 0f
        corners.forEach { x += it[0]; y += it[1]; z += it[2] }
        val n = corners.size.toFloat()
        return floatArrayOf(x / n, y / n, z / n)
    }

    private fun sub(a: FloatArray, b: FloatArray): FloatArray =
        floatArrayOf(a[0] - b[0], a[1] - b[1], a[2] - b[2])

    private fun scalarTriple(a: FloatArray, b: FloatArray, c: FloatArray): Float =
        a[0] * (b[1] * c[2] - b[2] * c[1]) -
            a[1] * (b[0] * c[2] - b[2] * c[0]) +
            a[2] * (b[0] * c[1] - b[1] * c[0])

    private fun dot(a: FloatArray, b: FloatArray): Float =
        a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
}
