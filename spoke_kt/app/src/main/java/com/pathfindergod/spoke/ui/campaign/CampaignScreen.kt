// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.campaign

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
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
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.material3.TextField
import androidx.compose.material3.TextFieldDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.pathfindergod.spoke.data.local.AppDatabase
import com.pathfindergod.spoke.data.local.NetworkPreferences
import com.pathfindergod.spoke.data.network.HubApiFactory
import com.pathfindergod.spoke.data.repository.CampaignRepository
import com.pathfindergod.spoke.ui.theme.CritRed
import com.pathfindergod.spoke.ui.theme.CrimsonPrimary
import com.pathfindergod.spoke.ui.theme.GodTypography
import com.pathfindergod.spoke.ui.theme.GoldAccent
import com.pathfindergod.spoke.ui.theme.TextPrimary
import com.pathfindergod.spoke.ui.theme.TextSecondary
import com.pathfindergod.spoke.ui.theme.rpgPanel
import com.pathfindergod.spoke.ui.viewmodel.CampaignViewModel
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonPrimitive

private val mockCombatEvents = listOf(
    "The fighter felled the goblin chief with a critical strike.",
    "The cleric stabilized the dying rogue.",
    "The party claimed the crypt vault.",
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
    val prefs = remember { NetworkPreferences(context) }
    val api = remember { HubApiFactory.create(prefs.restUrl()) }
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
    val campaign = state.campaign
    Box(modifier = Modifier.fillMaxSize()) {
        Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {
            if (campaign == null) {
                Box(
                    modifier = Modifier.fillMaxWidth().weight(1f),
                    contentAlignment = Alignment.Center,
                ) {
                    Text(
                        text = "No chronicle begun — name a campaign below.",
                        style = GodTypography.titleMedium,
                        color = TextSecondary,
                        textAlign = TextAlign.Center,
                        modifier = Modifier.padding(horizontal = 32.dp),
                    )
                }
            } else {
                Column(modifier = Modifier.rpgPanel().fillMaxWidth().padding(16.dp)) {
                    Text(
                        text = campaign.name,
                        style = GodTypography.headlineSmall,
                        color = GoldAccent,
                    )
                    if (campaign.description.isNotBlank()) {
                        Text(
                            text = campaign.description,
                            style = GodTypography.bodyMedium,
                            color = TextSecondary,
                            modifier = Modifier.padding(top = 4.dp),
                        )
                    }
                }
                val notes = remember(campaign.sessionNotes) {
                    ledgerNotes(campaign.sessionNotes)
                }
                if (state.isSummarizing) {
                    Text(
                        text = "The chronicler writes…",
                        style = GodTypography.bodyMedium,
                        color = TextSecondary,
                        modifier = Modifier.padding(top = 8.dp),
                    )
                }
                state.error?.let { error ->
                    Text(
                        text = error,
                        style = GodTypography.bodyMedium,
                        color = CritRed,
                        modifier = Modifier.padding(top = 4.dp),
                    )
                }
                LazyColumn(
                    modifier = Modifier.fillMaxWidth().weight(1f).padding(top = 12.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    itemsIndexed(notes, key = { _, note -> note.hashCode() }) { index, note ->
                        StaggerIn(index = index, modifier = Modifier.animateItem()) {
                            Text(
                                text = note,
                                style = GodTypography.bodyMedium,
                                color = TextPrimary,
                                modifier = Modifier
                                    .rpgPanel()
                                    .fillMaxWidth()
                                    .padding(12.dp),
                            )
                        }
                    }
                }
                Box(
                    modifier = Modifier
                        .rpgPanel()
                        .clickable { viewModel.summarizeRecentEvents(mockCombatEvents) }
                        .fillMaxWidth(),
                    contentAlignment = Alignment.Center,
                ) {
                    Text(
                        text = "SUMMARIZE RECENT COMBAT",
                        style = GodTypography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        color = GoldAccent,
                        modifier = Modifier.padding(vertical = 14.dp),
                    )
                }
            }
            Row(
                modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                CampaignField(
                    value = name,
                    onChange = { name = it },
                    label = "Name",
                    modifier = Modifier.weight(1f),
                )
                CampaignField(
                    value = description,
                    onChange = { description = it },
                    label = "Description",
                    modifier = Modifier.weight(1f),
                )
            }
        }
        FloatingActionButton(
            onClick = {
                viewModel.createCampaign(name.trim(), description.trim())
                name = ""
                description = ""
            },
            containerColor = CrimsonPrimary,
            modifier = Modifier.align(Alignment.BottomEnd).padding(20.dp),
        ) {
            Icon(
                imageVector = Icons.Filled.Add,
                contentDescription = "New campaign",
                tint = GoldAccent,
            )
        }
    }
}

@Composable
private fun CampaignField(
    value: String,
    onChange: (String) -> Unit,
    label: String,
    modifier: Modifier = Modifier,
) {
    TextField(
        value = value,
        onValueChange = onChange,
        label = { Text(text = label) },
        singleLine = true,
        colors = TextFieldDefaults.colors(
            focusedTextColor = TextPrimary,
            unfocusedTextColor = TextPrimary,
            focusedContainerColor = Color.Transparent,
            unfocusedContainerColor = Color.Transparent,
            cursorColor = GoldAccent,
            focusedLabelColor = TextSecondary,
            unfocusedLabelColor = TextSecondary,
        ),
        modifier = modifier,
    )
}
