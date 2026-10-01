// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.dice

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.graphics.toArgb
import com.pathfindergod.spoke.ui.theme.CritRed
import com.pathfindergod.spoke.ui.theme.GoldAccent
import com.pathfindergod.spoke.ui.theme.ParchmentSurface
import com.pathfindergod.spoke.ui.theme.TextPrimary
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.sin

private const val DROP_START = -260f
private const val SQUEEZE_START = 1.35f
private const val SPARK_COUNT = 14
private const val GLYPH_MIN_SCALE = 0.4f
private const val GLYPH_GROWTH = 0.6f
private const val GLYPH_BASE = 0.8f
private const val FLASH_MS = 650
private const val SPARK_MS = 750
private const val SPARK_DELAY_MS = 120L

private val DAMPING = Spring.DampingRatioMediumBouncy
private val SETTLE_STIFFNESS = Spring.StiffnessLow
private val DRAMA_STIFFNESS = Spring.StiffnessVeryLow

private fun glyphScale(glyph: Float): Float =
    GLYPH_MIN_SCALE + GLYPH_GROWTH * glyph.coerceIn(0f, 1f)

@Composable
fun DiceCanvas(
    die: Die,
    face: Int,
    rollToken: Int,
    modifier: Modifier = Modifier,
    impact: Impact = Impact.NORMAL,
    onImpact: () -> Unit = {},
) {
    val rotation = remember { Animatable(0f) }
    val scale = remember { Animatable(1f) }
    val drop = remember { Animatable(0f) }
    val flash = remember { Animatable(0f) }
    val sparks = remember { Animatable(0f) }
    val glyph = remember { Animatable(1f) }
    val path = remember { Path() }
    val paint = remember {
        android.graphics.Paint().apply {
            textAlign = android.graphics.Paint.Align.CENTER
            isAntiAlias = true
        }
    }
    val dramatic = impact != Impact.NORMAL
    val settle = if (dramatic) DRAMA_STIFFNESS else SETTLE_STIFFNESS
    LaunchedEffect(rollToken) {
        if (rollToken == 0) return@LaunchedEffect
        launch {
            drop.snapTo(DROP_START)
            drop.animateTo(0f, spring(dampingRatio = DAMPING, stiffness = settle))
            onImpact()
        }
        launch {
            rotation.snapTo(0f)
            rotation.animateTo(
                360f * if (dramatic) 6f else 4f,
                spring(dampingRatio = DAMPING, stiffness = settle),
            )
        }
        launch {
            scale.snapTo(SQUEEZE_START)
            scale.animateTo(1f, spring(dampingRatio = DAMPING, stiffness = settle))
        }
        launch {
            glyph.snapTo(GLYPH_MIN_SCALE)
            glyph.animateTo(1f, spring(dampingRatio = DAMPING, stiffness = settle))
        }
        if (dramatic) {
            launch {
                flash.snapTo(0f)
                flash.animateTo(1f, tween(durationMillis = FLASH_MS))
            }
            launch {
                sparks.snapTo(0f)
                delay(SPARK_DELAY_MS)
                sparks.animateTo(1f, tween(durationMillis = SPARK_MS))
            }
        } else {
            flash.snapTo(0f)
            sparks.snapTo(0f)
        }
    }
    Canvas(
        modifier = modifier.graphicsLayer {
            rotationZ = rotation.value
            scaleX = scale.value
            scaleY = scale.value
            translationY = drop.value
        },
    ) {
        val radius = size.minDimension / 2f
        val center = Offset(size.width / 2f, size.height / 2f)
        val sparkColor =
            if (impact == Impact.CRITICAL_SUCCESS) GoldAccent else CritRed
        path.rewind()
        buildDiePath(path, die, center, radius)
        drawPath(path = path, color = ParchmentSurface)
        drawPath(
            path = path,
            color = GoldAccent,
            style = Stroke(width = radius * 0.08f),
        )
        if (sparks.value > 0f) {
            for (i in 0 until SPARK_COUNT) {
                val angle = (i * 2.0 * PI / SPARK_COUNT).toFloat()
                val dist = radius * (0.7f + sparks.value * 1.2f)
                drawCircle(
                    color = sparkColor.copy(alpha = 1f - sparks.value),
                    radius = radius * 0.05f * (1f - sparks.value * 0.5f),
                    center = Offset(
                        center.x + dist * cos(angle),
                        center.y + dist * sin(angle),
                    ),
                )
            }
        }
        paint.color = TextPrimary.toArgb()
        paint.textSize = radius * GLYPH_BASE * glyphScale(glyph.value)
        drawContext.canvas.nativeCanvas.drawText(
            face.toString(),
            center.x,
            center.y + radius * 0.28f,
            paint,
        )
        if (flash.value > 0f) {
            val pulse = sin(flash.value * PI).toFloat()
            drawRect(color = sparkColor.copy(alpha = 0.3f * pulse))
        }
    }
}

private fun buildDiePath(
    target: Path,
    die: Die,
    center: Offset,
    radius: Float,
) {
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
    for (i in 0 until vertices) {
        val angle = start + 2.0 * PI * i / vertices
        val x = center.x + (radius * cos(angle)).toFloat()
        val y = center.y + (radius * sin(angle)).toFloat()
        if (i == 0) target.moveTo(x, y) else target.lineTo(x, y)
    }
    target.close()
}
