// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.dice

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.spring
import androidx.compose.foundation.Canvas
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.graphics.toArgb
import com.pathfindergod.spoke.ui.theme.GoldAccent
import com.pathfindergod.spoke.ui.theme.ParchmentSurface
import com.pathfindergod.spoke.ui.theme.TextPrimary
import kotlinx.coroutines.launch
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.sin

@Composable
fun DiceCanvas(
    die: Die,
    face: Int,
    rollToken: Int,
    modifier: Modifier = Modifier,
) {
    val rotation = remember { Animatable(0f) }
    val scale = remember { Animatable(1f) }
    LaunchedEffect(rollToken) {
        if (rollToken == 0) return@LaunchedEffect
        launch {
            rotation.snapTo(-180f)
            rotation.animateTo(
                360f,
                spring(Spring.DampingRatioMediumBouncy, Spring.StiffnessLow),
            )
        }
        launch {
            scale.snapTo(1.35f)
            scale.animateTo(
                1f,
                spring(Spring.DampingRatioMediumBouncy, Spring.StiffnessMedium),
            )
        }
    }
    Canvas(modifier = modifier) {
        val radius = size.minDimension / 2f * scale.value
        val center = Offset(size.width / 2f, size.height / 2f)
        rotate(rotation.value, center) {
            val path = diePath(die, center, radius)
            drawPath(path = path, color = ParchmentSurface)
            drawPath(
                path = path,
                color = GoldAccent,
                style = Stroke(width = radius * 0.08f),
            )
        }
        drawContext.canvas.nativeCanvas.apply {
            val paint = android.graphics.Paint().apply {
                color = TextPrimary.toArgb()
                textSize = radius * 0.8f
                textAlign = android.graphics.Paint.Align.CENTER
            }
            drawText(face.toString(), center.x, center.y + radius * 0.28f, paint)
        }
    }
}

private fun diePath(die: Die, center: Offset, radius: Float): Path {
    val vertices = when (die) {
        Die.D4 -> 3
        Die.D6 -> 4
        Die.D8 -> 4
        Die.D10 -> 5
        Die.D12 -> 6
        Die.D20 -> 8
    }
    val start = when (die) {
        Die.D4 -> -PI / 2.0
        Die.D6 -> PI / 4.0
        Die.D8 -> 0.0
        Die.D10 -> -PI / 2.0
        Die.D12 -> 0.0
        Die.D20 -> PI / 8.0
    }
    return Path().apply {
        for (i in 0 until vertices) {
            val angle = start + 2.0 * PI * i / vertices
            val x = center.x + (radius * cos(angle)).toFloat()
            val y = center.y + (radius * sin(angle)).toFloat()
            if (i == 0) moveTo(x, y) else lineTo(x, y)
        }
        close()
    }
}
