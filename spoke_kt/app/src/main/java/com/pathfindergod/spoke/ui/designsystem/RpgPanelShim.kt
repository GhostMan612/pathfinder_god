// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.designsystem

import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.Dp
import com.pathfindergod.spoke.ui.theme.GoldAccent
import com.pathfindergod.spoke.ui.theme.ParchmentSurface

@Deprecated(
    message = "rpgPanel is dead. Use Modifier.godCard or the GodCard composable.",
    replaceWith = ReplaceWith("Modifier.godCard(cornerRadius, fill, border)"),
)
fun Modifier.rpgPanel(
    cornerRadius: Dp = Dimens.panelCorner,
    fill: Color = ParchmentSurface,
    border: Color = GoldAccent,
): Modifier = this.godCard(
    cornerRadius = cornerRadius,
    fill = fill,
    border = border,
)
