// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.pit

import kotlin.math.acos
import kotlin.math.sqrt

object PitTransform {

    const val EPSILON = 1e-5f

    fun identity(): FloatArray = floatArrayOf(0f, 0f, 0f, 1f)

    fun dot(a: FloatArray, b: FloatArray): Float =
        a[0] * b[0] + a[1] * b[1] + a[2] * b[2]

    fun cross(a: FloatArray, b: FloatArray): FloatArray = floatArrayOf(
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )

    fun length(v: FloatArray): Float =
        sqrt((v[0] * v[0] + v[1] * v[1] + v[2] * v[2]).toDouble()).toFloat()

    fun quatLength(v: FloatArray): Float =
        sqrt((v[0] * v[0] + v[1] * v[1] + v[2] * v[2] + v[3] * v[3]).toDouble()).toFloat()

    fun normalize(v: FloatArray): FloatArray {
        val len = quatLength(v)
        if (len < 1e-12f) return floatArrayOf(0f, 0f, 0f, 1f)
        return floatArrayOf(v[0] / len, v[1] / len, v[2] / len, v[3] / len)
    }

    fun normalizeDirection(v: FloatArray): FloatArray {
        val len = sqrt((v[0] * v[0] + v[1] * v[1] + v[2] * v[2]).toDouble()).toFloat()
        if (len < 1e-12f) return floatArrayOf(0f, 0f, 1f)
        return floatArrayOf(v[0] / len, v[1] / len, v[2] / len)
    }

    fun isDirection(v: FloatArray): Boolean = kotlin.math.abs(length(v) - 1f) < 1e-3f

    fun rotationFromTo(from: FloatArray, to: FloatArray): FloatArray {
        val a = normalizeDirection(from)
        val b = normalizeDirection(to)
        val d = dot(a, b)
        if (d > 1f - 1e-6f) return identity()
        if (d < -1f + 1e-6f) {
            var seed = cross(a, floatArrayOf(0f, 1f, 0f))
            if (length(seed) < 1e-4f) seed = cross(a, floatArrayOf(1f, 0f, 0f))
            val axis = normalizeDirection(seed)
            return floatArrayOf(axis[0], axis[1], axis[2], 0f)
        }
        val c = cross(a, b)
        return normalize(floatArrayOf(c[0], c[1], c[2], 1f + d))
    }

    fun faceFacingRotation(faceNormal: FloatArray, target: FloatArray): FloatArray =
        rotationFromTo(faceNormal, target)

    fun settleQuaternion(
        current: FloatArray,
        faceNormal: FloatArray,
        towardsCamera: FloatArray,
    ): FloatArray {
        val worldNormal = rotate(current, faceNormal)
        val delta = faceFacingRotation(worldNormal, towardsCamera)
        return normalize(multiply(delta, current))
    }

    fun toFilamentMatrix(q: FloatArray, x: Float, y: Float, z: Float): FloatArray {
        val m = toMatrix(q)
        m[12] = x
        m[13] = y
        m[14] = z
        m[15] = 1f
        return m
    }

    fun multiply(a: FloatArray, b: FloatArray): FloatArray = floatArrayOf(
        a[3] * b[0] + a[0] * b[3] + a[1] * b[2] - a[2] * b[1],
        a[3] * b[1] - a[0] * b[2] + a[1] * b[3] + a[2] * b[0],
        a[3] * b[2] + a[0] * b[1] - a[1] * b[0] + a[2] * b[3],
        a[3] * b[3] - a[0] * b[0] - a[1] * b[1] - a[2] * b[2],
    )

    fun conjugate(q: FloatArray): FloatArray =
        floatArrayOf(-q[0], -q[1], -q[2], q[3])

    fun rotate(q: FloatArray, v: FloatArray): FloatArray {
        val u = floatArrayOf(q[0], q[1], q[2])
        val w = q[3]
        val uv = cross(u, v)
        val uuv = cross(u, uv)
        return floatArrayOf(
            v[0] + 2f * (uv[0] * w + uuv[0]),
            v[1] + 2f * (uv[1] * w + uuv[1]),
            v[2] + 2f * (uv[2] * w + uuv[2]),
        )
    }

    fun toMatrix(q: FloatArray): FloatArray {
        val x = q[0]
        val y = q[1]
        val z = q[2]
        val w = q[3]
        val xx = x * x
        val yy = y * y
        val zz = z * z
        val xy = x * y
        val xz = x * z
        val yz = y * z
        val wx = w * x
        val wy = w * y
        val wz = w * z
        return floatArrayOf(
            1f - 2f * (yy + zz), 2f * (xy + wz), 2f * (xz - wy), 0f,
            2f * (xy - wz), 1f - 2f * (xx + zz), 2f * (yz + wx), 0f,
            2f * (xz + wy), 2f * (yz - wx), 1f - 2f * (xx + yy), 0f,
            0f, 0f, 0f, 1f,
        )
    }

    fun applyMatrix(m: FloatArray, v: FloatArray): FloatArray = floatArrayOf(
        m[0] * v[0] + m[4] * v[1] + m[8] * v[2] + m[12] * v[3],
        m[1] * v[0] + m[5] * v[1] + m[9] * v[2] + m[13] * v[3],
        m[2] * v[0] + m[6] * v[1] + m[10] * v[2] + m[14] * v[3],
        m[3] * v[0] + m[7] * v[1] + m[11] * v[2] + m[15] * v[3],
    )

    fun axisAngle(axis: FloatArray, radians: Float): FloatArray {
        val a = normalizeDirection(axis)
        val half = radians * 0.5f
        val s = kotlin.math.sin(half.toDouble()).toFloat()
        return floatArrayOf(a[0] * s, a[1] * s, a[2] * s, kotlin.math.cos(half.toDouble()).toFloat())
    }

    fun yawPitch(yaw: Float, pitch: Float): FloatArray = multiply(
        axisAngle(floatArrayOf(0f, 1f, 0f), yaw),
        axisAngle(floatArrayOf(1f, 0f, 0f), pitch),
    )

    fun slerp(a: FloatArray, b: FloatArray, t: Float): FloatArray {
        var target = b
        var cos = a[0] * b[0] + a[1] * b[1] + a[2] * b[2] + a[3] * b[3]
        if (cos < 0f) {
            target = floatArrayOf(-b[0], -b[1], -b[2], -b[3])
            cos = -cos
        }
        if (cos > 0.9995f) {
            val out = floatArrayOf(
                a[0] + (target[0] - a[0]) * t,
                a[1] + (target[1] - a[1]) * t,
                a[2] + (target[2] - a[2]) * t,
                a[3] + (target[3] - a[3]) * t,
            )
            return normalize(out)
        }
        val theta = acos(cos.coerceIn(-1f, 1f).toDouble()).toFloat()
        val sinTheta = kotlin.math.sin(theta.toDouble()).toFloat()
        val wa = kotlin.math.sin(((1f - t) * theta).toDouble()).toFloat() / sinTheta
        val wb = kotlin.math.sin((t * theta).toDouble()).toFloat() / sinTheta
        return floatArrayOf(
            a[0] * wa + target[0] * wb,
            a[1] * wa + target[1] * wb,
            a[2] * wa + target[2] * wb,
            a[3] * wa + target[3] * wb,
        )
    }

    fun determinant3(m: FloatArray): Float =
        m[0] * (m[5] * m[10] - m[6] * m[9]) -
            m[4] * (m[1] * m[10] - m[2] * m[9]) +
            m[8] * (m[1] * m[6] - m[2] * m[5])
}
