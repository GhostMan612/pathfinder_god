// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.designsystem

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.State
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.semantics.ProgressBarRangeInfo
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.progressBarRangeInfo
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import com.pathfindergod.spoke.ui.theme.GoldAccent
import com.pathfindergod.spoke.ui.theme.TextPrimary
import com.pathfindergod.spoke.ui.theme.TextSecondary

@Composable
fun GodEmptyState(
    text: String,
    modifier: Modifier = Modifier,
    horizontalPadding: Dp = Spacing.xxl,
) {
    Box(
        modifier = modifier.fillMaxWidth(),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = text,
            style = MaterialTheme.typography.titleMedium,
            color = TextSecondary,
            textAlign = TextAlign.Center,
            modifier = Modifier.padding(horizontal = horizontalPadding),
        )
    }
}

@Composable
fun GodStatTile(
    label: String,
    value: String,
    modifier: Modifier = Modifier,
    valueColor: Color = TextPrimary,
) {
    Column(
        modifier = modifier.semantics(mergeDescendants = true) {
            contentDescription = "$value, $label"
        },
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(
            text = value,
            style = MaterialTheme.typography.titleLarge,
            fontWeight = FontWeight.Bold,
            color = valueColor,
        )
        Text(
            text = label,
            style = MaterialTheme.typography.bodyMedium,
            color = TextSecondary,
        )
    }
}

@Composable
fun GodProgressBar(
    fraction: Float,
    modifier: Modifier = Modifier,
    ghostFraction: Float = fraction,
    barColor: Color = GoldAccent,
    trackColor: Color = TextSecondary.copy(alpha = 0.25f),
    height: Dp = Dimens.progressHeight,
    label: String? = null,
    testTag: String? = null,
    ghostFractionState: State<Float>? = null,
) {
    val clamped = fraction.coerceIn(0f, 1f)
    // BP-08 O7: when the ghost bar is animated, its value is read inside
    // drawBehind (draw phase) instead of here. Reading an animated State in
    // composition recomposes this subtree on every animation frame.
    val staticGhost = ghostFraction.coerceIn(0f, 1f)
    Box(
        modifier = modifier
            .fillMaxWidth()
            .height(height)
            .semantics {
                progressBarRangeInfo = ProgressBarRangeInfo(clamped, 0f..1f)
                if (label != null) contentDescription = label
                if (testTag != null) this.testTag = testTag
            },
    ) {
        Box(
            modifier = Modifier
                .fillMaxSize()
                .clip(CircleShape)
                .drawBehind {
                    drawRect(trackColor)
                    // Drawn as a rect rather than a fillMaxWidth(ghost) child:
                    // a width-driven child is a LAYOUT input, so it forced the
                    // animated value to be read in composition every frame.
                    val g = (ghostFractionState?.value ?: staticGhost).coerceIn(0f, 1f)
                    if (g > clamped) {
                        drawRect(
                            color = barColor.copy(alpha = 0.45f),
                            size = Size(size.width * g, size.height),
                        )
                    }
                },
        )
        Box(
            modifier = Modifier
                .fillMaxWidth(clamped)
                .fillMaxHeight()
                .clip(CircleShape)
                .drawBehind { drawRect(barColor) },
        )
    }
}

@Composable
fun GlassCard(
    modifier: Modifier = Modifier,
    cornerRadius: Dp = Dimens.panelCorner,
    contentAlignment: Alignment = Alignment.Center,
    content: @Composable () -> Unit,
) {
    val scrim = Color.White.copy(alpha = Dimens.glassScrim)
    Box(
        modifier = modifier
            .drawBehind {
                val radiusPx = cornerRadius.toPx()
                val corner = CornerRadius(radiusPx, radiusPx)
                drawRoundRect(
                    brush = Brush.verticalGradient(
                        colors = listOf(
                            scrim.copy(alpha = Dimens.glassSheen * 2f),
                            scrim,
                        ),
                    ),
                    cornerRadius = corner,
                )
                drawRoundRect(
                    color = Color.White.copy(alpha = 0.18f),
                    cornerRadius = corner,
                    style = Stroke(width = Dimens.glassStroke.toPx()),
                )
                drawCircle(
                    color = Color.White.copy(alpha = 0.10f),
                    radius = radiusPx * 0.6f,
                    center = Offset(size.width * 0.18f, radiusPx * 0.8f),
                )
            }
            .padding(Spacing.sm),
        contentAlignment = contentAlignment,
    ) {
        content()
    }
}
