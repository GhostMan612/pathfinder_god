// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.pit

import com.pathfindergod.spoke.ui.dice.Die
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.math.acos
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
        Die.D10 to Expectation(10, (1..10).toList(), 11),
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

    @Test
    fun centroidNormalsAreUnitLengthAndOutward() {
        for (die in Die.entries) {
            val mesh = DieMeshBuilder.build(die)
            assertEquals("$die centroid count", mesh.faceCount * 3, mesh.centroidNormals.size)
            for (face in 0 until mesh.faceCount) {
                val n = mesh.centroidNormal(face)
                assertEquals("$die $face length", 1f, norm(n), 1e-4f)
                val c = centroidOf(mesh.facePoints[face])
                assertTrue("$die $face outward ${dot(n, c)}", dot(n, c) > 0f)
            }
        }
    }

    @Test
    fun centroidNormalsAgreeWithFacePlaneNormalsWithinBevelTolerance() {
        for (die in Die.entries) {
            val mesh = DieMeshBuilder.build(die)
            for (face in 0 until mesh.faceCount) {
                val n = mesh.centroidNormal(face)
                val plane = newell(mesh.facePoints[face])
                val angle = Math.toDegrees(
                    acos(dot(n, plane).coerceIn(-1f, 1f).toDouble()),
                )
                assertTrue("$die $face centroid vs plane $angle", angle < 25.0)
            }
        }
    }

    @Test
    fun centroidNormalsAreDistinctWithinEachSolid() {
        for (die in Die.entries) {
            val mesh = DieMeshBuilder.build(die)
            for (a in 0 until mesh.faceCount) {
                for (b in a + 1 until mesh.faceCount) {
                    val agreement = dot(mesh.centroidNormal(a), mesh.centroidNormal(b))
                    assertTrue("$die $a/$b duplicated $agreement", agreement < 0.999f)
                }
            }
        }
    }

    @Test
    fun centroidNormalsForOppositeFacesAreAntiparallel() {
        for (die in Die.entries) {
            val sum = expectations.getValue(die).pairSum ?: continue
            val mesh = DieMeshBuilder.build(die)
            val floor = oppositeFloor[die] ?: -0.999f
            for (face in 0 until mesh.faceCount) {
                val mate = mesh.faceIndexOf(sum - mesh.faceNumbers[face])
                assertNotNull("$die mate of ${mesh.faceNumbers[face]}", mate)
                val alignment = dot(
                    mesh.centroidNormal(face),
                    mesh.centroidNormal(mate!!),
                )
                assertTrue(
                    "$die ${mesh.faceNumbers[face]}/$sum alignment $alignment",
                    alignment < floor,
                )
            }
        }
    }

    @Test
    fun everyRollableValueResolvesToExactlyOneCentroidNormal() {
        for (die in Die.entries) {
            val mesh = DieMeshBuilder.build(die)
            val rollable = 1..die.sides
            assertEquals(
                "$die rollable count",
                mesh.faceCount,
                rollable.count(),
            )
            for (value in rollable) {
                assertEquals("$die $value occurrences", 1, mesh.faceNumbers.count { it == value })
                val index = mesh.faceIndexOf(value)
                assertTrue("$die $value missing", index >= 0)
                val n = mesh.centroidNormalFor(value)
                assertNotNull("$die $value normal", n)
                assertEquals("$die $value normal length", 1f, norm(n!!), 1e-4f)
            }
        }
    }

    @Test
    fun solidsAreInscribedInTheUnitSphere() {
        for (die in Die.entries) {
            val mesh = DieMeshBuilder.build(die)
            var longest = 0f
            var i = 0
            while (i < mesh.positions.size) {
                val p = floatArrayOf(
                    mesh.positions[i],
                    mesh.positions[i + 1],
                    mesh.positions[i + 2],
                )
                val r = norm(p)
                assertTrue("$die vertex $r", r <= 1.0001f)
                longest = maxOf(longest, r)
                i += 3
            }
            assertEquals("$die circumscribed", 1f, longest, 1e-4f)
        }
    }

    @Test
    fun faceFacingRotationAimsEveryCentroidNormalAtTheCamera() {
        for (die in Die.entries) {
            val mesh = DieMeshBuilder.build(die)
            for (face in 0 until mesh.faceCount) {
                val n = mesh.centroidNormal(face)
                for (target in CAMERA_TARGETS) {
                    val q = PitTransform.faceFacingRotation(n, target)
                    val aimed = PitTransform.rotate(q, n)
                    val error = kotlin.math.abs(
                        PitTransform.dot(aimed, target) - 1f,
                    )
                    assertTrue(
                        "$die $face -> ${target.toList()} off by $error",
                        error < 1e-4f,
                    )
                }
            }
        }
    }

    @Test
    fun faceFacingRotationIsAPureRotation() {
        for (die in Die.entries) {
            val mesh = DieMeshBuilder.build(die)
            for (face in 0 until mesh.faceCount) {
                val n = mesh.centroidNormal(face)
                for (target in CAMERA_TARGETS) {
                    val m = PitTransform.toMatrix(
                        PitTransform.faceFacingRotation(n, target),
                    )
                    val cx = floatArrayOf(m[0], m[4], m[8])
                    val cy = floatArrayOf(m[1], m[5], m[9])
                    val cz = floatArrayOf(m[2], m[6], m[10])
                    assertEquals("$die $face col0", 1f, norm(cx), 1e-4f)
                    assertEquals("$die $face col1", 1f, norm(cy), 1e-4f)
                    assertEquals("$die $face col2", 1f, norm(cz), 1e-4f)
                    assertEquals("$die $face x.y", 0f, dot(cx, cy), 1e-4f)
                    assertEquals("$die $face x.z", 0f, dot(cx, cz), 1e-4f)
                    assertEquals("$die $face y.z", 0f, dot(cy, cz), 1e-4f)
                    assertEquals("$die $face det", 1f, PitTransform.determinant3(m), 1e-4f)
                }
            }
        }
    }

    @Test
    fun tangentsAreUnitLengthAndPerpendicularToTheFaceNormal() {
        for (die in Die.entries) {
            val mesh = DieMeshBuilder.build(die)
            val vertices = mesh.indices.size
            assertEquals("$die tangent count", vertices * 4, mesh.tangents.size)
            var tri = 0
            while (tri < vertices) {
                val p = Array(3) { corner ->
                    floatArrayOf(
                        mesh.positions[(tri + corner) * 3],
                        mesh.positions[(tri + corner) * 3 + 1],
                        mesh.positions[(tri + corner) * 3 + 2],
                    )
                }
                val normal = PitTransform.normalizeDirection(
                    PitTransform.cross(sub(p[1], p[0]), sub(p[2], p[0])),
                )
                val tangent = PitTransform.normalizeDirection(
                    floatArrayOf(
                        mesh.tangents[tri * 4] + mesh.tangents[(tri + 1) * 4] +
                            mesh.tangents[(tri + 2) * 4],
                        mesh.tangents[tri * 4 + 1] + mesh.tangents[(tri + 1) * 4 + 1] +
                            mesh.tangents[(tri + 2) * 4 + 1],
                        mesh.tangents[tri * 4 + 2] + mesh.tangents[(tri + 1) * 4 + 2] +
                            mesh.tangents[(tri + 2) * 4 + 2],
                    ),
                )
                val w = mesh.tangents[tri * 4 + 3]
                assertEquals("$die tri $tri tangent length", 1f, norm(tangent), 1e-3f)
                assertEquals("$die tri $tri tangent orthog", 0f, dot(tangent, normal), 1e-3f)
                assertTrue("$die tri $tri handedness $w", w == 1f || w == -1f)
                tri += 3
            }
        }
    }

    @Test
    fun centroidNormalsMatchTheCapturedBuildTimeTable() {
        for (die in Die.entries) {
            val mesh = DieMeshBuilder.build(die)
            val expected = golden.getValue(die)
            assertEquals("$die golden face count", expected.size, mesh.faceCount)
            for (face in 0 until mesh.faceCount) {
                val want = expected[face]
                val got = mesh.centroidNormal(face)
                for (axis in 0 until 3) {
                    assertEquals(
                        "$die face $face axis $axis (face number ${mesh.faceNumbers[face]})",
                        want[axis],
                        got[axis],
                        GOLDEN_TOLERANCE,
                    )
                }
            }
        }
    }

    @Test
    fun faceNumbersMatchTheCapturedBuildTimeTable() {
        for (die in Die.entries) {
            val mesh = DieMeshBuilder.build(die)
            assertEquals(
                "$die face numbering",
                goldenNumbers.getValue(die).toList(),
                mesh.faceNumbers.toList(),
            )
        }
    }

    @Test
    fun everyCentroidNormalIsTheUnitDirectionOfItsFaceCentroid() {
        for (die in Die.entries) {
            val mesh = DieMeshBuilder.build(die)
            for (face in 0 until mesh.faceCount) {
                val c = centroidOf(mesh.facePoints[face])
                val expected = floatArrayOf(c[0] / norm(c), c[1] / norm(c), c[2] / norm(c))
                val got = mesh.centroidNormal(face)
                for (axis in 0 until 3) {
                    assertEquals(
                        "$die $face axis $axis",
                        expected[axis],
                        got[axis],
                        1e-5f,
                    )
                }
            }
        }
    }

    @Test
    fun everyCentroidNormalStaysInsideItsOwnAtlasTile() {
        for (die in Die.entries) {
            val mesh = DieMeshBuilder.build(die)
            val grid = DieTexture.atlasGrid(mesh)
            for (face in 0 until mesh.faceCount) {
                val cell = grid.tileOf(face)
                val corners = DieAtlas.cornerCount(mesh.faceKinds[face])
                val span = 0.8f
                for (corner in 0 until corners) {
                    val (fx, fy) = DieMeshBuilder.tileCorner(mesh.faceKinds[face], corner)
                    val localX = cell.uvX(fx)
                    val localY = cell.uvY(fy)
                    assertTrue("$die $face u $localX", localX > 0f && localX < 1f)
                    assertTrue("$die $face v $localY", localY > 0f && localY < 1f)
                    assertEquals("$die $face col", cell.col, colOfU(localX, grid.cols))
                    assertEquals("$die $face row", cell.row, rowOfV(localY, grid.rows))
                }
                assertTrue(
                    "$die $face tile span $span",
                    cell.centreX - cell.left > 0 && cell.centreY - cell.top > 0,
                )
            }
        }
    }

    @Test
    fun everyAtlasTileKeepsItsNumberInsideTheFacePolygon() {
        for (die in Die.entries) {
            val mesh = DieMeshBuilder.build(die)
            for (face in 0 until mesh.faceCount) {
                val kind = mesh.faceKinds[face]
                assertTrue(
                    "$die face $face number painted outside the face",
                    DieAtlas.containsLocal(kind, 0.5f, 0.5f),
                )
            }
        }
    }

    @Test
    fun everyTriangleIsWoundOutwardSoBackFaceCullingIsSafe() {
        for (die in Die.entries) {
            val mesh = DieMeshBuilder.build(die)
            val triangles = mesh.indices.size / 3
            for (tri in 0 until triangles) {
                val a = vertex(mesh, tri * 3)
                val b = vertex(mesh, tri * 3 + 1)
                val c = vertex(mesh, tri * 3 + 2)
                val n = PitTransform.normalizeDirection(
                    PitTransform.cross(sub(b, a), sub(c, a)),
                )
                val g = PitTransform.normalizeDirection(
                    floatArrayOf(
                        (a[0] + b[0] + c[0]) / 3f,
                        (a[1] + b[1] + c[1]) / 3f,
                        (a[2] + b[2] + c[2]) / 3f,
                    ),
                )
                assertTrue(
                    "$die tri $tri inward ${dot(n, g)}",
                    dot(n, g) > 0.1f,
                )
            }
        }
    }

    @Test
    fun filamentMatrixUsesColumnMajorWithTranslationInTheLastColumn() {
        val q = PitTransform.axisAngle(floatArrayOf(0.3f, 0.8f, 0.5f), 1.1f)
        val v = floatArrayOf(0.4f, -0.7f, 0.2f)
        val placed = PitTransform.toFilamentMatrix(q, 0f, PitWorld.DIE_Y, 0f)
        assertEquals(0f, placed[12], 0f)
        assertEquals(PitWorld.DIE_Y, placed[13], 0f)
        assertEquals(0f, placed[14], 0f)
        assertEquals(1f, placed[15], 0f)
        assertEquals(PitWorld.DIE_Y, placed[13], 0f)
        for (row in 0 until 3) {
            for (col in 0 until 3) {
                var columnLength = 0f
                for (r in 0 until 3) columnLength += placed[r * 4 + col] * placed[r * 4 + col]
                assertEquals(
                    "column $col length",
                    1f,
                    kotlin.math.sqrt(columnLength),
                    1e-4f,
                )
            }
            for (col in row + 1 until 3) {
                var shared = 0f
                for (r in 0 until 3) shared += placed[r * 4 + row] * placed[r * 4 + col]
                assertEquals("columns $row/$col orthogonal", 0f, shared, 1e-4f)
            }
            assertEquals("row $row w", 0f, placed[row * 4 + 3], 0f)
        }
        val moved = PitTransform.applyMatrix(placed, floatArrayOf(v[0], v[1], v[2], 1f))
        val rotated = PitTransform.rotate(q, v)
        for (axis in 0 until 3) {
            assertEquals("axis $axis", rotated[axis] + PitWorld.DIE_Y * axisShim(axis), moved[axis], 1e-4f)
        }
    }

    private fun axisShim(axis: Int): Float = if (axis == 1) 1f else 0f

    private fun vertex(mesh: DieMesh, index: Int): FloatArray = floatArrayOf(
        mesh.positions[index * 3],
        mesh.positions[index * 3 + 1],
        mesh.positions[index * 3 + 2],
    )

    private fun colOfU(u: Float, cols: Int): Int =
        ((u * cols).toInt() + cols) % cols

    private fun rowOfV(v: Float, rows: Int): Int = rows - 1 - ((v * rows).toInt() % rows)

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

    private fun norm(v: FloatArray): Float =
        sqrt((v[0] * v[0] + v[1] * v[1] + v[2] * v[2]).toDouble()).toFloat()

    private companion object {
        const val GOLDEN_TOLERANCE = 1e-3f

        val CAMERA_TARGETS: List<FloatArray> = listOf(
            floatArrayOf(0f, 0f, 1f),
            floatArrayOf(0f, 0f, -1f),
            floatArrayOf(1f, 0f, 0f),
            floatArrayOf(0f, 1f, 0f),
            floatArrayOf(0f, -1f, 0f),
            PitTransform.normalizeDirection(floatArrayOf(1f, 1f, 1f)),
            PitTransform.normalizeDirection(floatArrayOf(-0.3f, 0.8f, -0.5f)),
        )

        val oppositeFloor: Map<Die, Float> = mapOf(
            Die.D10 to -0.9995f,
        )

        val golden: Map<Die, List<FloatArray>> = mapOf(
            Die.D4 to listOf(
                floatArrayOf(-0.577350f, -0.577350f, -0.577350f),
                floatArrayOf(-0.577350f, +0.577350f, +0.577350f),
                floatArrayOf(+0.577350f, -0.577350f, +0.577350f),
                floatArrayOf(+0.577350f, +0.577350f, -0.577350f),
            ),
            Die.D6 to listOf(
                floatArrayOf(+1.000000f, +0.000000f, +0.000000f),
                floatArrayOf(-1.000000f, +0.000000f, +0.000000f),
                floatArrayOf(+0.000000f, +1.000000f, +0.000000f),
                floatArrayOf(+0.000000f, -1.000000f, +0.000000f),
                floatArrayOf(+0.000000f, +0.000000f, +1.000000f),
                floatArrayOf(+0.000000f, +0.000000f, -1.000000f),
            ),
            Die.D8 to listOf(
                floatArrayOf(+0.577350f, +0.577350f, +0.577350f),
                floatArrayOf(-0.577350f, +0.577350f, +0.577350f),
                floatArrayOf(-0.577350f, -0.577350f, +0.577350f),
                floatArrayOf(+0.577350f, -0.577350f, +0.577350f),
floatArrayOf(+0.577350f, +0.577350f, -0.577350f),
        floatArrayOf(-0.577350f, +0.577350f, -0.577350f),
        floatArrayOf(-0.577350f, -0.577350f, -0.577350f),
        floatArrayOf(+0.577350f, -0.577350f, -0.577350f),
            ),
            Die.D10 to listOf(
                floatArrayOf(+0.729666f, +0.431909f, +0.530134f),
                floatArrayOf(-0.278708f, +0.431909f, +0.857774f),
                floatArrayOf(-0.901917f, +0.431909f, +0.000000f),
                floatArrayOf(-0.278708f, +0.431909f, -0.857774f),
                floatArrayOf(+0.729666f, +0.431909f, -0.530134f),
                floatArrayOf(+0.901917f, -0.431909f, -0.000000f),
                floatArrayOf(+0.278708f, -0.431909f, +0.857774f),
                floatArrayOf(-0.729666f, -0.431909f, +0.530134f),
                floatArrayOf(-0.729666f, -0.431909f, -0.530134f),
                floatArrayOf(+0.278708f, -0.431909f, -0.857774f),
            ),
            Die.D12 to listOf(
                floatArrayOf(-0.525731f, +0.850651f, +0.000000f),
                floatArrayOf(+0.525731f, +0.850651f, +0.000000f),
                floatArrayOf(-0.525731f, -0.850651f, +0.000000f),
                floatArrayOf(+0.525731f, -0.850651f, +0.000000f),
                floatArrayOf(+0.000000f, -0.525731f, +0.850651f),
                floatArrayOf(+0.000000f, +0.525731f, +0.850651f),
                floatArrayOf(+0.000000f, -0.525731f, -0.850651f),
                floatArrayOf(+0.000000f, +0.525731f, -0.850651f),
                floatArrayOf(+0.850651f, +0.000000f, -0.525731f),
                floatArrayOf(+0.850651f, +0.000000f, +0.525731f),
                floatArrayOf(-0.850651f, +0.000000f, -0.525731f),
                floatArrayOf(-0.850651f, +0.000000f, +0.525731f),
            ),
            Die.D20 to listOf(
                floatArrayOf(-0.577350f, +0.577350f, +0.577350f),
                floatArrayOf(+0.000000f, +0.934172f, +0.356822f),
                floatArrayOf(+0.000000f, +0.934172f, -0.356822f),
                floatArrayOf(-0.577350f, +0.577350f, -0.577350f),
                floatArrayOf(-0.934172f, +0.356822f, +0.000000f),
                floatArrayOf(+0.577350f, +0.577350f, +0.577350f),
                floatArrayOf(-0.356822f, +0.000000f, +0.934172f),
                floatArrayOf(-0.934172f, -0.356822f, +0.000000f),
                floatArrayOf(-0.356822f, +0.000000f, -0.934172f),
                floatArrayOf(+0.577350f, +0.577350f, -0.577350f),
                floatArrayOf(+0.577350f, -0.577350f, +0.577350f),
                floatArrayOf(+0.000000f, -0.934172f, +0.356822f),
                floatArrayOf(+0.000000f, -0.934172f, -0.356822f),
                floatArrayOf(+0.577350f, -0.577350f, -0.577350f),
                floatArrayOf(+0.934172f, -0.356822f, +0.000000f),
                floatArrayOf(+0.356822f, +0.000000f, +0.934172f),
                floatArrayOf(-0.577350f, -0.577350f, +0.577350f),
                floatArrayOf(-0.577350f, -0.577350f, -0.577350f),
                floatArrayOf(+0.356822f, +0.000000f, -0.934172f),
                floatArrayOf(+0.934172f, +0.356822f, +0.000000f),
            ),
        )

        val goldenNumbers: Map<Die, List<Int>> = mapOf(
            Die.D4 to listOf(1, 2, 3, 4),
            Die.D6 to listOf(1, 6, 2, 5, 3, 4),
            Die.D8 to listOf(1, 2, 3, 4, 6, 5, 8, 7),
            Die.D10 to listOf(1, 2, 3, 4, 5, 8, 7, 6, 10, 9),
            Die.D12 to listOf(1, 2, 11, 12, 3, 4, 9, 10, 5, 6, 7, 8),
            Die.D20 to listOf(
                1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 17, 18, 19, 20, 16, 12, 11, 15, 14, 13,
            ),
        )
    }
}
