// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.home

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.BottomSheetDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import com.pathfindergod.spoke.R
import com.pathfindergod.spoke.ui.designsystem.Dimens
import com.pathfindergod.spoke.ui.designsystem.GodBadge
import com.pathfindergod.spoke.ui.designsystem.GodCard
import com.pathfindergod.spoke.ui.designsystem.GodSectionHeader
import com.pathfindergod.spoke.ui.designsystem.GodTags
import com.pathfindergod.spoke.ui.designsystem.Spacing
import com.pathfindergod.spoke.ui.navigation.Destination
import com.pathfindergod.spoke.ui.navigation.overflowDestinations
import com.pathfindergod.spoke.ui.theme.GoldAccent
import com.pathfindergod.spoke.ui.theme.ParchmentSurface
import com.pathfindergod.spoke.ui.theme.TextPrimary

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MoreSheet(
    currentRoute: String?,
    onOpen: (Destination) -> Unit,
    onDismiss: () -> Unit,
) {
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        containerColor = ParchmentSurface,
        contentColor = TextPrimary,
        dragHandle = { BottomSheetDefaults.DragHandle(color = GoldAccent) },
    ) {
        LazyColumn(
            modifier = Modifier.fillMaxWidth().testTag(GodTags.MORE_SHEET),
            contentPadding = PaddingValues(
                start = Spacing.lg,
                end = Spacing.lg,
                bottom = Spacing.xl,
            ),
            verticalArrangement = Arrangement.spacedBy(Dimens.gridSpacing),
        ) {
            item {
                GodSectionHeader(
                    text = stringResource(R.string.more_title),
                    prominent = true,
                )
            }
            items(overflowDestinations, key = { it.route }) { destination ->
                val here = destination.route == currentRoute
                GodCard(
                    contentPadding = PaddingValues(Dimens.cardPaddingTight),
                    onClick = { onOpen(destination) },
                    onClickLabel = stringResource(R.string.a11y_open_destination),
                    contentDescription = stringResource(destination.labelRes),
                    stateDescription = if (here) {
                        stringResource(R.string.a11y_current_destination)
                    } else {
                        null
                    },
                    testTag = GodTags.moreDestination(destination.route),
                ) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(Spacing.md),
                    ) {
                        Icon(
                            painter = painterResource(destination.iconRes),
                            contentDescription = null,
                            tint = GoldAccent,
                            modifier = Modifier.size(Dimens.statusDot * 2),
                        )
                        Text(
                            text = stringResource(destination.labelRes),
                            style = MaterialTheme.typography.titleMedium,
                            color = TextPrimary,
                            modifier = Modifier.weight(1f),
                        )
                        if (here) {
                            GodBadge(text = stringResource(R.string.more_here))
                        }
                    }
                }
            }
        }
    }
}