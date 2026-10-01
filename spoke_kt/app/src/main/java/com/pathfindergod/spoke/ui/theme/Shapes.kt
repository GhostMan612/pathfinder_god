// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.theme

import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Shapes
import androidx.compose.ui.graphics.RectangleShape
import androidx.compose.ui.unit.dp

object GodShape {
    val panel = RoundedCornerShape(6.dp)
    val chip = RoundedCornerShape(4.dp)
    val field = RoundedCornerShape(6.dp)
    val card = RoundedCornerShape(10.dp)
    val sheet = RoundedCornerShape(16.dp)
    val circle = CircleShape
    val square = RectangleShape
    val none = RoundedCornerShape(0.dp)
}

val GodShapes: Shapes = Shapes(
    extraSmall = GodShape.chip,
    small = GodShape.field,
    medium = GodShape.panel,
    large = GodShape.card,
    extraLarge = GodShape.sheet,
)
