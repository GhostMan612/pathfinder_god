// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.map

fun mapSampleSize(width: Int, height: Int, maxDimension: Int): Int {
    if (width <= 0 || height <= 0 || maxDimension <= 0) return 1
    var longest = maxOf(width, height)
    var sample = 1
    while (longest / 2 >= maxDimension) {
        longest /= 2
        sample *= 2
    }
    return sample
}

fun mapBoundsClamp(
    offsetX: Float,
    offsetY: Float,
    viewportWidth: Float,
    viewportHeight: Float,
    scale: Float,
): FloatArray {
    val slackX = (viewportWidth * (scale - 1f) / 2f).coerceAtLeast(0f)
    val slackY = (viewportHeight * (scale - 1f) / 2f).coerceAtLeast(0f)
    return floatArrayOf(
        offsetX.coerceIn(-slackX, slackX),
        offsetY.coerceIn(-slackY, slackY),
    )
}
