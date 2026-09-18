// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.theme

import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.drawWithCache
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp

fun Modifier.rpgPanel(
    cornerRadius: Dp = 6.dp,
    fill: Color = ParchmentSurface,
    border: Color = GoldAccent,
): Modifier = this.drawWithCache {
    val radiusPx = cornerRadius.toPx()
    val outer = CornerRadius(radiusPx, radiusPx)
    val outerStroke = Stroke(width = 2.dp.toPx())
    val inset = 5.dp.toPx()
    val innerStroke = Stroke(width = 1.dp.toPx())
    val notch = 10.dp.toPx()
    val notchStroke = 3.dp.toPx()
    onDrawBehind {
        drawRoundRect(color = fill, cornerRadius = outer)
        drawRoundRect(color = border, cornerRadius = outer, style = outerStroke)
        drawRoundRect(
            color = border.copy(alpha = 0.55f),
            topLeft = Offset(inset, inset),
            size = Size(size.width - inset * 2f, size.height - inset * 2f),
            cornerRadius = CornerRadius((radiusPx - inset).coerceAtLeast(0f)),
            style = innerStroke,
        )
        val w = size.width
        val h = size.height
        drawLine(border, Offset(0f, notch), Offset(notch, 0f), notchStroke)
        drawLine(border, Offset(w - notch, 0f), Offset(w, notch), notchStroke)
        drawLine(border, Offset(w, h - notch), Offset(w - notch, h), notchStroke)
        drawLine(border, Offset(notch, h), Offset(0f, h - notch), notchStroke)
    }
}
