// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.navigation

import androidx.compose.foundation.layout.size
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import com.pathfindergod.spoke.R
import com.pathfindergod.spoke.ui.designsystem.Dimens
import com.pathfindergod.spoke.ui.designsystem.GodTags
import com.pathfindergod.spoke.ui.designsystem.godLiveRegion
import com.pathfindergod.spoke.ui.theme.GoldAccent
import com.pathfindergod.spoke.ui.theme.VoidBackground

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AppTopBar(
    title: String,
    canNavigateUp: Boolean,
    onNavigateUp: () -> Unit,
    onHome: () -> Unit,
    onMore: () -> Unit,
) {
    TopAppBar(
        title = {
            Text(
                text = title,
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold,
                color = GoldAccent,
                modifier = Modifier
                    .godLiveRegion()
                    .testTag(GodTags.TOP_BAR_TITLE),
            )
        },
        navigationIcon = {
            IconButton(
                onClick = { if (canNavigateUp) onNavigateUp() else onHome() },
                // The tag goes on the IconButton, not the Icon. The Icon is 24dp, so a tag
                // there measures the glyph instead of the tappable control and reports a
                // 24dp target. The IconButton is the 48dp touch target, and it is the
                // element a test or an accessibility service should be inspecting.
                modifier = Modifier
                    .size(Dimens.minTouchTarget)
                    .testTag(GodTags.TOP_BAR_BACK),
            ) {
                Icon(
                    imageVector = if (canNavigateUp) {
                        Icons.AutoMirrored.Filled.ArrowBack
                    } else {
                        Icons.Filled.Home
                    },
                    contentDescription = stringResource(
                        if (canNavigateUp) R.string.nav_back else R.string.nav_to_home,
                    ),
                    tint = GoldAccent,
                )
            }
        },
        actions = {
            IconButton(
                onClick = onMore,
                modifier = Modifier
                    .size(Dimens.minTouchTarget)
                    .testTag(GodTags.TOP_BAR_MORE),
            ) {
                Icon(
                    imageVector = Icons.Filled.MoreVert,
                    contentDescription = stringResource(R.string.nav_more),
                    tint = GoldAccent,
                )
            }
        },
        colors = TopAppBarDefaults.topAppBarColors(
            containerColor = VoidBackground,
            titleContentColor = GoldAccent,
            navigationIconContentColor = GoldAccent,
            actionIconContentColor = GoldAccent,
        ),
    )
}
