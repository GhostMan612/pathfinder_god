// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.motion

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.slideInVertically
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import kotlinx.coroutines.delay

@Composable
fun StaggerIn(
    index: Int,
    modifier: Modifier = Modifier,
    content: @Composable () -> Unit,
) {
    // rememberSaveable, not remember: inside a keyed Lazy item both are disposed
    // when the row scrolls out of the window and recreated when it scrolls back,
    // so scrolling a 200-row roll history down and up replayed every row's fade
    // and slide. Saveable state survives disposal, so an item animates once.
    var visible by rememberSaveable(index) { mutableStateOf(false) }
    LaunchedEffect(Unit) {
        delay((index * 70).coerceAtMost(560).toLong())
        visible = true
    }
    AnimatedVisibility(
        visible = visible,
        enter = fadeIn(tween(280)) + slideInVertically(tween(280)) { it / 4 },
        modifier = modifier,
    ) {
        content()
    }
}
