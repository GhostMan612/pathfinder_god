// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.pit

import com.pathfindergod.spoke.ui.dice.Die
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class PitGeometryTest {

    @Test
    fun atlasGridCoversEverySolid() {
        for (die in Die.entries) {
            val faces = DieMeshBuilder.build(die).faceCount
            val grid = DieAtlas.gridFor(faces)
            assertTrue("$die cols ${grid.cols}", grid.cols >= 1)
            assertTrue("$die rows ${grid.rows}", grid.rows >= 1)
            assertTrue("$die slots ${grid.slots}", grid.slots >= faces)
            for (face in 0 until faces) {
                assertTrue("$die face $face col", grid.colOf(face) < grid.cols)
                assertTrue("$die face $face row", grid.rowOf(face) < grid.rows)
            }
        }
    }

    @Test
    fun atlasShrinksAgainstTheLegacyTwoThousandPixelLayout() {
        val legacyPixels = 2000L * 1600L
        for (die in Die.entries) {
            val grid = DieAtlas.gridFor(DieMeshBuilder.build(die).faceCount)
            val pixels = grid.width.toLong() * grid.height.toLong()
            assertTrue(
                "$die $pixels vs $legacyPixels",
                pixels < legacyPixels / 4,
            )
        }
        val widest = DieAtlas.gridFor(20)
        assertEquals(800, widest.width)
        assertEquals(640, widest.height)
    }

    @Test
    fun mipChainHalvesEveryLevelDownToOneByOne() {
        for (die in Die.entries) {
            val grid = DieAtlas.gridFor(DieMeshBuilder.build(die).faceCount)
            var w = grid.width
            var h = grid.height
            var level = 0
            while (level < grid.levels) {
                assertEquals("$die level $level w", maxOf(1, grid.width shr level), w)
                assertEquals("$die level $level h", maxOf(1, grid.height shr level), h)
                w = maxOf(1, w shr 1)
                h = maxOf(1, h shr 1)
                level++
            }
            assertEquals("$die terminal w", 1, w)
            assertEquals("$die terminal h", 1, h)
        }
    }

    @Test
    fun downsampleAveragesFourPixels() {
        val src = intArrayOf(
            0xFF000000.toInt(), 0xFF404040.toInt(),
            0xFF808080.toInt(), 0xFFC0C0C0.toInt(),
        )
        val out = DieAtlas.downsample(src, 2, 2)
        assertEquals(1, out.size)
        assertEquals(255, (out[0] ushr 24) and 0xFF)
        assertEquals(96, (out[0] shr 16) and 0xFF)
        assertEquals(96, (out[0] shr 8) and 0xFF)
        assertEquals(96, out[0] and 0xFF)
    }

    @Test
    fun downsamplePreservesTheAlphaFalloff() {
        val src = intArrayOf(0xFF000000.toInt(), 0x80000000.toInt())
        val out = DieAtlas.downsample(src, 2, 1)
        assertEquals(1, out.size)
        assertEquals(192, (out[0] ushr 24) and 0xFF)
    }

    @Test
    fun bevelNormalMapBevelsTheBorderWithoutSwampingTheFace() {
        for (die in Die.entries) {
            val mesh = DieMeshBuilder.build(die)
            val grid = DieAtlas.gridFor(mesh.faceCount)
            val normals = DieAtlas.bevelNormals(mesh.faceCount, mesh.faceKinds, grid)
            assertEquals("$die pixels", grid.width * grid.height, normals.size)
            for (face in 0 until mesh.faceCount) {
                val cx = grid.colOf(face) * grid.tile + grid.tile / 2
                val cy = grid.rowOf(face) * grid.tile + grid.tile / 2
                val core = normals[cy * grid.width + cx]
                assertEquals(
                    "$die $face core r",
                    (DieAtlas.FLAT_XY shr 8 and 0xFF).toDouble(),
                    ((core shr 16) and 0xFF).toDouble(),
                    2.0,
                )
                assertEquals(
                    "$die $face core g",
                    (DieAtlas.FLAT_XY and 0xFF).toDouble(),
                    ((core shr 8) and 0xFF).toDouble(),
                    2.0,
                )
                assertEquals("$die $face core b", 255.0, (core and 0xFF).toDouble(), 2.0)
            }
            var tilted = 0
            normals.forEach { pixel ->
                val dr = ((pixel shr 16) and 0xFF) - (DieAtlas.FLAT_XY shr 8 and 0xFF)
                val dg = ((pixel shr 8) and 0xFF) - (DieAtlas.FLAT_XY and 0xFF)
                if (kotlin.math.abs(dr) > 2 || kotlin.math.abs(dg) > 2) tilted++
            }
            val fraction = tilted.toFloat() / normals.size
            assertTrue("$die tilted fraction $fraction", fraction > 0.05f)
            assertTrue("$die tilted fraction $fraction", fraction < 0.45f)
        }
    }

    @Test
    fun bevelNormalMapTiltPointsOutwardOnTheQuad() {
        val mesh = DieMeshBuilder.build(Die.D6)
        val grid = DieAtlas.gridFor(mesh.faceCount)
        val normals = DieAtlas.bevelNormals(mesh.faceCount, mesh.faceKinds, grid)
        val x = (grid.colOf(0) * grid.tile + 0.17f * grid.tile).toInt()
        val y = (grid.rowOf(0) * grid.tile + 0.50f * grid.tile).toInt()
        val probe = normals[y * grid.width + x]
        val red = (probe shr 16) and 0xFF
        val green = (probe shr 8) and 0xFF
        assertTrue("outward red $red", red <= 100)
        assertEquals(
            "no cross tilt $green",
            (DieAtlas.FLAT_XY and 0xFF).toDouble(),
            green.toDouble(),
            3.0,
        )
        assertTrue("recessed blue ${probe and 0xFF}", (probe and 0xFF) >= 200)
    }

    @Test
    fun feltWeaveIsOpaqueAndSized() {
        val size = 64
        val felt = DieAtlas.feltPixels(size)
        assertEquals(size * size, felt.size)
        felt.forEach { pixel ->
            assertEquals(255, (pixel ushr 24) and 0xFF)
        }
        assertTrue("has variation", felt.toSortedSet().size > 1)
    }

    @Test
    fun groundQuadAndContactDiscFaceUp() {
        val ground = DieAtlas.groundQuad(6f, -1.2f)
        assertEquals(4 * 3, ground.indices.size)
        var index = 0
        while (index < ground.indices.size) {
            val a = vertex(ground, ground.indices[index])
            val b = vertex(ground, ground.indices[index + 1])
            val c = vertex(ground, ground.indices[index + 2])
            val n = PitTransform.normalizeDirection(
                PitTransform.cross(sub(b, a), sub(c, a)),
            )
            assertTrue("ground triangle $index normal ${n.toList()}", n[1] > 0.99f)
            index += 3
        }
        val disc = DieAtlas.contactDisc(1.2f, -1.18f, 32)
        assertEquals(33 * 6, disc.positions.size)
        assertEquals(32 * 3, disc.indices.size)
        index = 0
        while (index < disc.indices.size) {
            val a = vertex(disc, disc.indices[index])
            val b = vertex(disc, disc.indices[index + 1])
            val c = vertex(disc, disc.indices[index + 2])
            val n = PitTransform.normalizeDirection(
                PitTransform.cross(sub(b, a), sub(c, a)),
            )
            assertTrue("disc triangle $index normal ${n.toList()}", n[1] > 0.99f)
            index += 3
        }
    }

    private fun vertex(quad: PitQuad, index: Short): FloatArray = floatArrayOf(
        quad.positions[index * 3],
        quad.positions[index * 3 + 1],
        quad.positions[index * 3 + 2],
    )

    private fun sub(a: FloatArray, b: FloatArray): FloatArray =
        floatArrayOf(a[0] - b[0], a[1] - b[1], a[2] - b[2])
}
