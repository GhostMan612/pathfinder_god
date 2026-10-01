// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.campaign

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import com.pathfindergod.spoke.ui.motion.StaggerIn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.pathfindergod.spoke.R
import com.pathfindergod.spoke.data.local.AppDatabase
import com.pathfindergod.spoke.data.local.AppPreferences
import com.pathfindergod.spoke.data.network.HubApiFactory
import com.pathfindergod.spoke.data.repository.CampaignRepository
import com.pathfindergod.spoke.ui.designsystem.Dimens
import com.pathfindergod.spoke.ui.designsystem.GodCard
import com.pathfindergod.spoke.ui.designsystem.GodEmptyState
import com.pathfindergod.spoke.ui.designsystem.GodFab
import com.pathfindergod.spoke.ui.designsystem.GodPrimaryButton
import com.pathfindergod.spoke.ui.designsystem.GodStatusText
import com.pathfindergod.spoke.ui.designsystem.GodTags
import com.pathfindergod.spoke.ui.designsystem.GodTextField
import com.pathfindergod.spoke.ui.designsystem.GodTone
import com.pathfindergod.spoke.ui.designsystem.Spacing
import com.pathfindergod.spoke.ui.strings.resolve
import com.pathfindergod.spoke.ui.theme.CritRed
import com.pathfindergod.spoke.ui.theme.GoldAccent
import com.pathfindergod.spoke.ui.theme.TextPrimary
import com.pathfindergod.spoke.ui.theme.TextSecondary
import com.pathfindergod.spoke.ui.viewmodel.CampaignViewModel
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonPrimitive

@Composable
private fun rememberMockCombatEvents(): List<String> = listOf(
    stringResource(R.string.campaign_mock_event_felled),
    stringResource(R.string.campaign_mock_event_stabilized),
    stringResource(R.string.campaign_mock_event_vault),
)

private class CampaignVmFactory(
    private val repository: CampaignRepository,
) : ViewModelProvider.Factory {
    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>): T =
        CampaignViewModel(repository) as T
}

@Composable
internal fun rememberCampaignViewModel(): CampaignViewModel {
    val context = LocalContext.current
    val prefs = remember { AppPreferences(context) }
    val api = remember { HubApiFactory.get(prefs.restUrl()) }
    val repository = remember {
        CampaignRepository(AppDatabase.create(context.applicationContext), api)
    }
    return viewModel(factory = remember { CampaignVmFactory(repository) })
}

private fun ledgerNotes(raw: String): List<String> = try {
    (Json.parseToJsonElement(raw) as? JsonArray)
        ?.mapNotNull { (it as? JsonPrimitive)?.takeIf { p -> p.isString }?.content }
        .orEmpty()
        .asReversed()
} catch (_: Exception) {
    emptyList()
}

@Composable
fun CampaignScreen(
    viewModel: CampaignViewModel,
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    var name by rememberSaveable { mutableStateOf("") }
    var description by rememberSaveable { mutableStateOf("") }
    val mockCombatEvents = rememberMockCombatEvents()
    val campaign = state.campaign
    Box(modifier = Modifier.fillMaxSize()) {
        Column(modifier = Modifier.fillMaxSize().padding(Spacing.lg)) {
            if (campaign == null) {
                Box(
                    modifier = Modifier.fillMaxWidth().weight(1f),
                    contentAlignment = Alignment.Center,
                ) {
                    GodEmptyState(text = stringResource(R.string.campaign_empty))
                }
            } else {
                GodCard(
                    title = {
                        Text(
                            text = campaign.name,
                            style = MaterialTheme.typography.headlineSmall,
                            color = GoldAccent,
                        )
                    },
                ) {
                    if (campaign.description.isNotBlank()) {
                        Text(
                            text = campaign.description,
                            style = MaterialTheme.typography.bodyMedium,
                            color = TextSecondary,
                            modifier = Modifier.padding(top = Spacing.xs),
                        )
                    }
                }
                val notes = remember(campaign.sessionNotes) {
                    ledgerNotes(campaign.sessionNotes)
                }
                if (state.isSummarizing) {
                    GodStatusText(
                        text = stringResource(R.string.campaign_summarizing),
                        modifier = Modifier.padding(top = Spacing.sm),
                    )
                }
                state.error?.let { error ->
                    GodStatusText(
                        text = error.resolve(),
                        tone = GodTone.Critical,
                        color = CritRed,
                        modifier = Modifier.padding(top = Spacing.xs),
                    )
                }
                LazyColumn(
                    modifier = Modifier.fillMaxWidth().weight(1f).padding(top = Spacing.md),
                    verticalArrangement = Arrangement.spacedBy(Dimens.gridSpacing),
                ) {
                    itemsIndexed(notes, key = { _, note -> note.hashCode() }) { index, note ->
                        StaggerIn(index = index, modifier = Modifier.animateItem()) {
                            GodCard(contentPadding = PaddingValues(Dimens.cardPaddingTight)) {
                                Text(
                                    text = note,
                                    style = MaterialTheme.typography.bodyMedium,
                                    color = TextPrimary,
                                )
                            }
                        }
                    }
                }
                GodPrimaryButton(
                    text = stringResource(R.string.campaign_summarize),
                    onClickLabel = stringResource(R.string.a11y_campaign_summarize),
                    onClick = { viewModel.summarizeRecentEvents(mockCombatEvents) },
                    testTag = GodTags.CAMPAIGN_SUMMARIZE,
                )
            }
            Row(
                modifier = Modifier.fillMaxWidth().padding(top = Spacing.md),
                horizontalArrangement = Arrangement.spacedBy(Spacing.sm),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                GodTextField(
                    value = name,
                    onValueChange = { name = it },
                    label = stringResource(R.string.campaign_field_name),
                    modifier = Modifier.weight(1f),
                )
                GodTextField(
                    value = description,
                    onValueChange = { description = it },
                    label = stringResource(R.string.campaign_field_description),
                    modifier = Modifier.weight(1f),
                )
            }
        }
        GodFab(
            icon = Icons.Filled.Add,
            contentDescription = stringResource(R.string.campaign_fab),
            onClick = {
                viewModel.createCampaign(name.trim(), description.trim())
                name = ""
                description = ""
            },
            testTag = GodTags.CAMPAIGN_FAB,
            modifier = Modifier
                .align(Alignment.BottomEnd)
                .padding(Spacing.xl),
        )
    }
}
