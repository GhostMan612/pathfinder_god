// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.pit

import com.pathfindergod.spoke.ui.dice.DiceEngine
import com.pathfindergod.spoke.ui.dice.DiceSpec
import com.pathfindergod.spoke.ui.dice.Die
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.math.sqrt

class PitSettleTest {

    @Test
    fun twoDReadoutAndThreeDParityForEveryRolledFace() {
        for (die in Die.entries) {
            val mesh = DieMeshBuilder.build(die)
            for (value in 1..die.sides) {
                assertEquals("$die $value twoD readout", value.toString(), readout(value))
                val normal = mesh.centroidNormalFor(value)
                assertNotNull("$die $value centroid normal", normal)
                assertEquals(
                    "$die $value face carrying the number",
                    value,
                    mesh.faceNumbers[mesh.faceIndexOf(value)],
                )
                assertEquals("$die $value settle target", 1f, length(normal!!), 1e-4f)
            }
        }
    }

    @Test
    fun everyEngineRollResolvesToASettleableFace() {
        val engine = DiceEngine()
        for (die in Die.entries) {
            val mesh = DieMeshBuilder.build(die)
            repeat(ROLLS_PER_DIE) {
                val record = engine.roll(DiceSpec(count = 1, sides = die.sides))
                val kept = record.kept.first()
                assertTrue("$die kept $kept in range", kept in 1..die.sides)
                assertNotNull("$die kept $kept normal", mesh.centroidNormalFor(kept))
            }
        }
    }

    @Test
    fun settleQuaternionAimsTheRolledFaceAtTheCameraFromAnyStartingOrientation() {
        for (die in Die.entries) {
            val mesh = DieMeshBuilder.build(die)
            for (value in 1..die.sides) {
                val normal = mesh.centroidNormalFor(value)!!
                for (from in START_ORIENTATIONS) {
                    for (eye in cameraEyes()) {
                        val towardsCamera = towardsCamera(eye)
                        val settled = PitTransform.settleQuaternion(from, normal, towardsCamera)
                        assertEquals("$die $value unit", 1f, quatLength(settled), 1e-4f)
                        val aimed = PitTransform.rotate(settled, normal)
                        assertEquals(
                            "$die $value aim ${aimed.toList()} vs ${towardsCamera.toList()}",
                            1f,
                            dot(aimed, towardsCamera),
                            AIM_TOLERANCE,
                        )
                    }
                }
            }
        }
    }

    @Test
    fun settleQuaternionNeverMirrorsTheSolid() {
        for (die in Die.entries) {
            val mesh = DieMeshBuilder.build(die)
            for (value in 1..die.sides) {
                val normal = mesh.centroidNormalFor(value)!!
                for (from in START_ORIENTATIONS) {
                    for (eye in cameraEyes()) {
                        val settled = PitTransform.settleQuaternion(
                            from,
                            normal,
                            towardsCamera(eye),
                        )
                        val m = PitTransform.toMatrix(settled)
                        assertEquals(
                            "$die $value handedness",
                            1f,
                            PitTransform.determinant3(m),
                            1e-4f,
                        )
                    }
                }
            }
        }
    }

    @Test
    fun settlePathStartsAtTheCurrentOrientationAndConvergesOnTheTarget() {
        for (die in Die.entries) {
            val mesh = DieMeshBuilder.build(die)
            for (value in 1..die.sides) {
                val normal = mesh.centroidNormalFor(value)!!
                for (from in START_ORIENTATIONS) {
                    for (eye in cameraEyes()) {
                        val towards = towardsCamera(eye)
                        val to = PitTransform.settleQuaternion(from, normal, towards)
                        val atZero = PitTransform.slerp(from, to, 0f)
                        assertTrue(
                            "$die $value path start",
                            quatDot(atZero, from) > 1f - 1e-3f,
                        )
                        val atOne = PitTransform.slerp(from, to, 1f)
                        assertEquals(
                            "$die $value path end",
                            1f,
                            dot(PitTransform.rotate(atOne, normal), towards),
                            AIM_TOLERANCE,
                        )
                        val startError = 1f - dot(PitTransform.rotate(from, normal), towards)
                        val midError = 1f - dot(
                            PitTransform.rotate(PitTransform.slerp(from, to, 0.5f), normal),
                            towards,
                        )
                        val endError = 1f - dot(PitTransform.rotate(to, normal), towards)
                        assertTrue(
                            "$die $value midpoint $midError above $endError",
                            midError > endError - 1e-3f,
                        )
                        assertTrue(
                            "$die $value midpoint $midError below $startError",
                            midError < startError + 1e-3f,
                        )
                    }
                }
            }
        }
    }

    @Test
    fun settleKeepsTheDieCentreFixedAboveTheFelt() {
        for (die in Die.entries) {
            val mesh = DieMeshBuilder.build(die)
            for (value in 1..die.sides) {
                val normal = mesh.centroidNormalFor(value)!!
                for (from in START_ORIENTATIONS) {
                    for (eye in cameraEyes()) {
                        val settled = PitTransform.settleQuaternion(
                            from,
                            normal,
                            towardsCamera(eye),
                        )
                        val m = PitTransform.toFilamentMatrix(settled, 0f, PitWorld.DIE_Y, 0f)
                        val centre = PitTransform.applyMatrix(
                            m,
                            floatArrayOf(0f, 0f, 0f, 1f),
                        )
                        assertEquals("$die $value cx", 0f, centre[0], 1e-4f)
                        assertEquals("$die $value cy", PitWorld.DIE_Y, centre[1], 1e-4f)
                        assertEquals("$die $value cz", 0f, centre[2], 1e-4f)
                        assertTrue(
                            "$die $value above the felt",
                            PitWorld.DIE_Y - PitWorld.DIE_RADIUS > PitWorld.GROUND_Y,
                        )
                    }
                }
            }
        }
    }

    @Test
    fun theRolledFaceIsTheFaceFacedAtTheCameraAfterSettling() {
        for (die in Die.entries) {
            val mesh = DieMeshBuilder.build(die)
            for (value in 1..die.sides) {
                for (from in START_ORIENTATIONS) {
                    for (eye in cameraEyes()) {
                        val towards = towardsCamera(eye)
                        val settled = PitTransform.settleQuaternion(
                            from,
                            mesh.centroidNormalFor(value)!!,
                            towards,
                        )
                        var bestFace = -1
                        var bestDot = -2f
                        mesh.faceNumbers.indices.forEach { face ->
                            val aimed = dot(
                                PitTransform.rotate(settled, mesh.centroidNormal(face)),
                                towards,
                            )
                            if (aimed > bestDot) {
                                bestDot = aimed
                                bestFace = face
                            }
                        }
                        assertEquals(
                            "$die $value settled onto face ${mesh.faceNumbers[bestFace]}",
                            value,
                            mesh.faceNumbers[bestFace],
                        )
                    }
                }
            }
        }
    }

    @Test
    fun cameraDirectionAlwaysPointsFromTheDieCentreToTheEye() {
        for (yaw in 0 until 8) {
            for (pitchStep in 1..6) {
                val pitch = PitWorld.MIN_PITCH +
                    (PitWorld.MAX_PITCH - PitWorld.MIN_PITCH) * pitchStep / 7f
                val distance = PitWorld.DEFAULT_DISTANCE
val eye = PitWorld.eye(yaw.toFloat(), pitch, distance)
                assertEquals("yaw $yaw pitch $pitch radius", distance, radius(eye), 1e-3f)
                assertTrue("yaw $yaw pitch $pitch above the felt", eye[1] > PitWorld.GROUND_Y)
                val raw = PitWorld.toDieDirection(eye)
                assertEquals("yaw $yaw pitch $pitch x", eye[0], raw[0], 0f)
                assertEquals("yaw $yaw pitch $pitch y", eye[1] - PitWorld.DIE_Y, raw[1], 0f)
                assertEquals("yaw $yaw pitch $pitch z", eye[2], raw[2], 0f)
                val toEye = PitTransform.normalizeDirection(raw)
                assertEquals("yaw $yaw pitch $pitch unit", 1f, length(toEye), 1e-4f)
                for (axis in 0 until 3) {
                    assertEquals(
                        "yaw $yaw pitch $pitch axis $axis",
                        raw[axis],
                        toEye[axis] * length(raw),
                        1e-3f,
                    )
                }
            }
        }
    }

    @Test
    fun orbitStaysInsideTheDeclaredLimits() {
        var yaw = PitWorld.DEFAULT_YAW
        var pitch = PitWorld.DEFAULT_PITCH
        var distance = PitWorld.DEFAULT_DISTANCE
        repeat(ORBIT_STEPS) {
            yaw -= 37f
            pitch = (pitch + 61f).coerceIn(PitWorld.MIN_PITCH, PitWorld.MAX_PITCH)
            distance = (distance / 1.04f).coerceIn(
                PitWorld.MIN_DISTANCE,
                PitWorld.MAX_DISTANCE,
            )
        }
        assertTrue("pitch $pitch", pitch in PitWorld.MIN_PITCH..PitWorld.MAX_PITCH)
        assertTrue(
            "distance $distance",
            distance in PitWorld.MIN_DISTANCE..PitWorld.MAX_DISTANCE,
        )
        val eye = PitWorld.eye(yaw, pitch, distance)
        assertEquals("eye radius", distance, radius(eye), 1e-3f)
    }

    private fun radius(eye: FloatArray): Float = sqrt(
        eye[0] * eye[0] + (eye[1] - PitWorld.FOCUS_Y) * (eye[1] - PitWorld.FOCUS_Y) +
            eye[2] * eye[2],
    ).toFloat()

    private fun towardsCamera(eye: FloatArray): FloatArray =
        PitTransform.normalizeDirection(PitWorld.toDieDirection(eye))

    private fun readout(value: Int): String = value.toString()

    private fun cameraEyes(): List<FloatArray> = listOf(
        PitWorld.eye(PitWorld.DEFAULT_YAW, PitWorld.DEFAULT_PITCH, PitWorld.DEFAULT_DISTANCE),
        PitWorld.eye(0f, PitWorld.MAX_PITCH, PitWorld.MIN_DISTANCE),
        PitWorld.eye(3.5f, PitWorld.MIN_PITCH, PitWorld.MAX_DISTANCE),
        PitWorld.eye(1.9f, 0.9f, 3.1f),
    )

    private fun dot(a: FloatArray, b: FloatArray): Float =
        a[0] * b[0] + a[1] * b[1] + a[2] * b[2]

    private fun length(v: FloatArray): Float = sqrt(
        (v[0] * v[0] + v[1] * v[1] + v[2] * v[2]).toDouble(),
    ).toFloat()

    private fun quatDot(a: FloatArray, b: FloatArray): Float =
        a[0] * b[0] + a[1] * b[1] + a[2] * b[2] + a[3] * b[3]

    private fun quatLength(v: FloatArray): Float = sqrt(
        (v[0] * v[0] + v[1] * v[1] + v[2] * v[2] + v[3] * v[3]).toDouble(),
    ).toFloat()

    private companion object {
        const val AIM_TOLERANCE = 1e-3f
        const val ROLLS_PER_DIE = 64
        const val ORBIT_STEPS = 400

        val START_ORIENTATIONS: List<FloatArray> = listOf(
            PitTransform.identity(),
            PitTransform.axisAngle(floatArrayOf(0f, 1f, 0f), 1.5707963f),
            PitTransform.axisAngle(floatArrayOf(0.577f, 0.577f, 0.577f), 2.4f),
            PitTransform.axisAngle(floatArrayOf(0f, 1f, 0f), 0.3f),
        )
    }
}
