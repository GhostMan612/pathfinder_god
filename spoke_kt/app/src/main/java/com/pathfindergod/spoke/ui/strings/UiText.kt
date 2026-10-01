// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.strings

import androidx.annotation.StringRes
import androidx.compose.runtime.Composable
import androidx.compose.ui.res.stringResource

sealed interface UiText {
    data class Resource(@StringRes val resId: Int) : UiText

    data class Message(val text: String) : UiText
}

@Composable
fun UiText.resolve(): String = when (this) {
    is UiText.Resource -> stringResource(resId)
    is UiText.Message -> text
}
