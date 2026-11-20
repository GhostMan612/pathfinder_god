// ============================================================
// Genesis header
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.designsystem

import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import com.pathfindergod.spoke.ui.theme.GoldAccent
import com.pathfindergod.spoke.ui.theme.ParchmentSurface

/**
 * RPG-themed "unearthing the rulebook" loading card: a parchment tile with a
 * slow shimmer sweep of staggered gold lines, plus a softly pulsing glow.
 * Drawn on the Canvas so it runs at draw time without recomposition.
 */
@Composable
fun GodLoadingBook(
    modifier: Modifier = Modifier,
) {
    val infiniteTransition = rememberInfiniteTransition(label = "rules_loading")
    val sweep by infiniteTransition.animateFloat(
        initialValue = 0f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(2800, easing = LinearEasing),
            repeatMode = RepeatMode.Restart,
        ),
        label = "sweep",
    )
    val glow by infiniteTransition.animateFloat(
        initialValue = 0.4f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(1200, easing = LinearEasing),
            repeatMode = RepeatMode.Reverse,
        ),
        label = "glow",
    )
    Box(
        modifier = modifier,
        contentAlignment = Alignment.Center,
    ) {
        Canvas(Modifier.fillMaxSize()) {
            val pad = 28f
            val w = size.width - pad * 2f
            val h = size.height - pad * 2f
            val radius = 12f
            val topLeft = Offset(pad, pad)
            val outline = Stroke(2f)
            drawRoundRect(ParchmentSurface, topLeft, Size(w, h), CornerRadius(radius))
            drawRoundRect(
                GoldAccent.copy(alpha = 0.6f * glow),
                topLeft,
                Size(w, h),
                CornerRadius(radius),
                style = outline,
            )
            val lineCount = 5
            repeat(lineCount) { i ->
                val y = pad + 10f + (i + 1f) * h / (lineCount + 1f)
                drawRect(
                    brush = Brush.horizontalGradient(
                        listOf(
                            GoldAccent.copy(alpha = 0f),
                            GoldAccent.copy(alpha = 0.9f),
                        ),
                    ),
                    topLeft = Offset(pad, y),
                    size = Size((w * sweep).coerceAtLeast(0f), 8f),
                )
            }
        }
    }
}
