// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.character

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Share
import androidx.compose.material3.AlertDialog
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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import com.pathfindergod.spoke.service.ExportService
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import com.pathfindergod.spoke.R
import com.pathfindergod.spoke.data.local.CharacterEntity
import com.pathfindergod.spoke.data.network.HubCampaignSummary
import com.pathfindergod.spoke.ui.designsystem.Dimens
import com.pathfindergod.spoke.ui.designsystem.GodBackLink
import com.pathfindergod.spoke.ui.designsystem.GodCard
import com.pathfindergod.spoke.ui.designsystem.GodChip
import com.pathfindergod.spoke.ui.designsystem.GodPrimaryButton
import com.pathfindergod.spoke.ui.designsystem.GodStatTile
import com.pathfindergod.spoke.ui.designsystem.GodTags
import com.pathfindergod.spoke.ui.designsystem.GodTextField
import com.pathfindergod.spoke.ui.designsystem.Spacing
import com.pathfindergod.spoke.ui.designsystem.godRtlText
import com.pathfindergod.spoke.ui.designsystem.godTouchHeight
import com.pathfindergod.spoke.ui.designsystem.godTouchSize
import com.pathfindergod.spoke.ui.theme.CrimsonPrimary
import com.pathfindergod.spoke.ui.theme.CritRed
import com.pathfindergod.spoke.ui.theme.GoldAccent
import com.pathfindergod.spoke.ui.theme.ParchmentSurface
import com.pathfindergod.spoke.ui.theme.TextPrimary
import com.pathfindergod.spoke.ui.theme.TextSecondary
import com.pathfindergod.spoke.data.repository.HandsetAuthResult
import com.pathfindergod.spoke.ui.viewmodel.PendingCrossHubSync
import com.pathfindergod.spoke.ui.viewmodel.PendingSyncConflict
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.intOrNull

private val abilityOrder = listOf("str", "dex", "con", "int", "wis", "cha")

private fun flatEntries(raw: String?): List<Pair<String, String>> {
    if (raw.isNullOrBlank()) return emptyList()
    return try {
        when (val element = Json.parseToJsonElement(raw)) {
            is JsonObject -> element.entries.map { (key, value) -> key to renderValue(value) }
            is JsonArray -> element.mapIndexed { index, value -> "${index + 1}" to renderValue(value) }
            else -> listOf("value" to renderValue(element))
        }
    } catch (_: Exception) {
        listOf("text" to raw)
    }
}

private fun renderValue(element: JsonElement): String = when (element) {
    is JsonPrimitive -> element.intOrNull?.toString() ?: element.content
    is JsonArray -> element.joinToString(", ") { renderValue(it) }
    is JsonObject -> element.entries.joinToString(", ") { (key, value) ->
        "${prettyKey(key)}: ${renderValue(value)}"
    }
}

private fun prettyKey(key: String): String {
    val spaced = key.replace('_', ' ')
        .replace(Regex("([a-z0-9])([A-Z])"), "$1 $2")
    return spaced.replaceFirstChar { it.uppercase() }
}

private fun abilityModifier(score: Int): Int = Math.floorDiv(score - 10, 2)

@Composable
fun CharacterDetailScreen(
    entity: CharacterEntity,
    onBack: () -> Unit,
    currentHubIdentity: String = "",
    selectedCampaignId: Int? = null,
    hubCampaigns: List<HubCampaignSummary> = emptyList(),
    isLoadingCampaigns: Boolean = false,
    pendingCrossHubSync: PendingCrossHubSync? = null,
    pendingSyncConflict: PendingSyncConflict? = null,
    pendingOutboxCount: Int = 0,
    handsetAuth: HandsetAuthResult? = null,
    onLoadCampaigns: (() -> Unit)? = null,
    onSelectCampaign: ((Int) -> Unit)? = null,
    onSync: ((Long, Int, Boolean) -> Unit)? = null,
    onConfirmCrossHubSync: (() -> Unit)? = null,
    onDismissCrossHubSync: (() -> Unit)? = null,
    onResolveConflictKeepMine: (() -> Unit)? = null,
    onResolveConflictUseServer: (() -> Unit)? = null,
    onDismissConflict: (() -> Unit)? = null,
    onDismissQueuedSync: ((Long) -> Unit)? = null,
    onVerifyHandset: (() -> Unit)? = null,
    onDismissHandsetAuth: (() -> Unit)? = null,
    isSyncing: Boolean = false,
) {
    val context = LocalContext.current
    val boundToCurrentHub = !entity.hubUrl.isNullOrBlank() &&
        currentHubIdentity.isNotBlank() &&
        entity.hubUrl == currentHubIdentity
    val boundCampaignId = entity.campaignId?.takeIf { boundToCurrentHub }
    var explicitCampaignId by rememberSaveable(entity.id, currentHubIdentity) {
        mutableStateOf<Int?>(null)
    }
    val effectiveCampaignId = explicitCampaignId ?: boundCampaignId ?: selectedCampaignId
    var manualCampaignInput by rememberSaveable(entity.id, currentHubIdentity, effectiveCampaignId) {
        mutableStateOf(effectiveCampaignId?.toString().orEmpty())
    }
    val derived = remember(entity.derived) { flatEntries(entity.derived).toMap() }
    val abilities = remember(entity.abilities) { flatEntries(entity.abilities).toMap() }
    val proficiencies = remember(entity.proficiencies) { flatEntries(entity.proficiencies) }
    val feats = remember(entity.feats) { flatEntries(entity.feats) }
    val equipment = remember(entity.equipment) { CharacterEquipmentParser.parse(entity.equipment) }
    Column(
        modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(Spacing.lg),
        verticalArrangement = Arrangement.spacedBy(Spacing.md),
    ) {
        GodBackLink(
            text = godRtlText(R.string.character_back, R.string.character_back_rtl),
            onClick = onBack,
            testTag = GodTags.heroBack,
        )
        GodCard {
            Column(
                modifier = Modifier.fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(Spacing.sm),
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween,
                ) {
                    Column(modifier = Modifier.weight(1f).padding(end = Spacing.md)) {
                        Text(
                            text = stringResource(R.string.character_sync_title),
                            style = MaterialTheme.typography.titleMedium,
                            color = GoldAccent,
                        )
                        val statusText = when (entity.syncStatus) {
                            "synced" -> stringResource(R.string.character_sync_status_synced, entity.serverRevision ?: 1)
                            "conflict" -> stringResource(R.string.character_sync_status_conflict)
                            "auth_error" -> stringResource(R.string.character_sync_status_auth_error)
                            "tls_error" -> stringResource(R.string.character_sync_status_tls_error)
                            "network_error" -> stringResource(R.string.character_sync_status_network_error)
                            "campaign_required" -> stringResource(R.string.character_sync_status_campaign_required)
                            "campaign_not_found" -> stringResource(R.string.character_sync_status_campaign_not_found)
                            else -> stringResource(R.string.character_sync_status_local)
                        }
                        Text(
                            text = statusText,
                            style = MaterialTheme.typography.bodySmall,
                            color = if (
                                entity.syncStatus == "conflict" ||
                                entity.syncStatus == "auth_error" ||
                                entity.syncStatus == "tls_error" ||
                                entity.syncStatus == "campaign_required" ||
                                entity.syncStatus == "campaign_not_found"
                            ) {
                                CritRed
                            } else {
                                TextSecondary
                            },
                        )
                        // Issue #33 Phase 3: queued syncs waiting on the
                        // retry worker. Tap the line to discard the queue.
                        if (pendingOutboxCount > 0) {
                            Text(
                                text = stringResource(
                                    R.string.character_sync_outbox_pending,
                                    pendingOutboxCount,
                                ),
                                style = MaterialTheme.typography.bodySmall,
                                color = GoldAccent,
                                modifier = Modifier
                                    .testTag(GodTags.heroOutboxPending(entity.id))
                                    .clickable(role = Role.Button) {
                                        onDismissQueuedSync?.invoke(entity.id)
                                    }
                                    .godTouchHeight()
                                    .padding(top = Spacing.xs),
                            )
                        }
                        // Issue #33 Phase 4: the last handset verification
                        // result, until dismissed.
                        handsetAuth?.let { auth ->
                            val authText = when (auth) {
                                HandsetAuthResult.Ok ->
                                    stringResource(R.string.character_sync_verify_ok)
                                is HandsetAuthResult.AuthFailed ->
                                    stringResource(
                                        R.string.character_sync_verify_auth_failed,
                                        auth.statusCode,
                                    )
                                HandsetAuthResult.TlsFailed ->
                                    stringResource(R.string.character_sync_verify_tls_failed)
                                is HandsetAuthResult.Unreachable ->
                                    stringResource(
                                        R.string.character_sync_verify_unreachable,
                                        auth.message,
                                    )
                            }
                            Text(
                                text = authText,
                                style = MaterialTheme.typography.bodySmall,
                                color = if (auth is HandsetAuthResult.Ok) TextSecondary else CritRed,
                                modifier = Modifier
                                    .clickable(role = Role.Button) {
                                        onDismissHandsetAuth?.invoke()
                                    }
                                    .godTouchHeight()
                                    .padding(top = Spacing.xs),
                            )
                        }
                        val entityHub = entity.hubUrl
                        if (!entityHub.isNullOrBlank() &&
                            currentHubIdentity.isNotBlank() &&
                            entityHub != currentHubIdentity
                        ) {
                            Text(
                                text = stringResource(R.string.character_sync_other_hub, entityHub),
                                style = MaterialTheme.typography.bodySmall,
                                color = GoldAccent,
                            )
                        }
                        val matchedCampaign = hubCampaigns.firstOrNull { it.id == effectiveCampaignId }
                        val campaignText = when {
                            effectiveCampaignId == null -> stringResource(R.string.character_sync_campaign_none)
                            matchedCampaign != null -> stringResource(
                                R.string.character_sync_campaign_named,
                                matchedCampaign.id,
                                matchedCampaign.name,
                            )
                            else -> stringResource(R.string.character_sync_campaign_id, effectiveCampaignId)
                        }
                        Text(
                            text = campaignText,
                            style = MaterialTheme.typography.bodySmall,
                            color = if (effectiveCampaignId == null) CritRed else TextSecondary,
                        )
                    }
                    if (onSync != null) {
                        GodPrimaryButton(
                            text = stringResource(
                                if (isSyncing) R.string.character_sync_working else R.string.character_sync_action,
                            ),
                            onClick = { effectiveCampaignId?.let { onSync(entity.id, it, false) } },
                            enabled = !isSyncing && effectiveCampaignId != null,
                            testTag = GodTags.heroSync(entity.id),
                        )
                    }
                }
                if (onSelectCampaign != null || onLoadCampaigns != null) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .horizontalScroll(rememberScrollState()),
                        horizontalArrangement = Arrangement.spacedBy(Spacing.xs),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        if (onLoadCampaigns != null) {
                            GodChip(
                                label = stringResource(
                                    if (isLoadingCampaigns) {
                                        R.string.character_sync_campaigns_loading
                                    } else {
                                        R.string.character_sync_campaigns_load
                                    },
                                ),
                                selected = false,
                                enabled = !isLoadingCampaigns,
                                role = Role.Button,
                                selectedStateRes = null,
                                testTag = GodTags.heroCampaignRefresh(entity.id),
                                onClick = onLoadCampaigns,
                            )
                        }
                        if (onVerifyHandset != null) {
                            GodChip(
                                label = stringResource(R.string.character_sync_verify_action),
                                selected = false,
                                enabled = true,
                                role = Role.Button,
                                selectedStateRes = null,
                                testTag = GodTags.heroVerifyHandset(entity.id),
                                onClick = onVerifyHandset,
                            )
                        }
                        if (onSelectCampaign != null) {
                            hubCampaigns.forEach { campaign ->
                                GodChip(
                                    label = "#${campaign.id} ${campaign.name}",
                                    selected = effectiveCampaignId == campaign.id,
                                    testTag = GodTags.heroCampaignChip(entity.id, campaign.id),
                                    onClick = {
                                        manualCampaignInput = campaign.id.toString()
                                        explicitCampaignId = campaign.id
                                        onSelectCampaign(campaign.id)
                                    },
                                )
                            }
                        }
                    }
                }
                if (onSelectCampaign != null) {
                    val parsedManual = manualCampaignInput.trim().toIntOrNull()?.takeIf { it >= 1 }
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(Spacing.sm),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        GodTextField(
                            value = manualCampaignInput,
                            onValueChange = { next ->
                                if (next.all { it.isDigit() }) {
                                    manualCampaignInput = next
                                }
                            },
                            label = stringResource(R.string.character_sync_campaign_hint),
                            numeric = true,
                            modifier = Modifier
                                .weight(1f)
                                .testTag(GodTags.heroCampaignInput(entity.id)),
                        )
                        GodChip(
                            label = stringResource(R.string.character_sync_campaign_set),
                            selected = parsedManual != null && parsedManual == effectiveCampaignId,
                            enabled = parsedManual != null,
                            role = Role.Button,
                            selectedStateRes = null,
                            testTag = GodTags.heroCampaignApply(entity.id),
                            onClick = {
                                parsedManual?.let { cid ->
                                    explicitCampaignId = cid
                                    onSelectCampaign(cid)
                                }
                            },
                        )
                    }
                }
            }
        }
        GodCard {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(
                    modifier = Modifier.size(Dimens.avatar).background(CrimsonPrimary, CircleShape),
                    contentAlignment = Alignment.Center,
                ) {
                    Text(
                        text = entity.name.firstOrNull()?.uppercase()
                            ?: stringResource(R.string.value_unknown),
                        style = MaterialTheme.typography.headlineSmall,
                        color = ParchmentSurface,
                    )
                }
                Column(modifier = Modifier.weight(1f).padding(start = Spacing.lg)) {
                    Text(
                        text = entity.name,
                        style = MaterialTheme.typography.headlineSmall,
                        color = GoldAccent,
                    )
                    Text(
                        text = stringResource(
                            R.string.character_summary_pattern,
                            entity.ancestry ?: stringResource(R.string.value_not_set),
                            entity.characterClass ?: stringResource(R.string.value_not_set),
                            entity.level,
                        ),
                        style = MaterialTheme.typography.bodyMedium,
                        color = TextSecondary,
                    )
                }
                Icon(
                    imageVector = Icons.Filled.Share,
                    contentDescription = stringResource(R.string.character_share),
                    tint = GoldAccent,
                    modifier = Modifier
                        .clickable(
                            onClickLabel = stringResource(R.string.a11y_hero_share, entity.name),
                            role = Role.Button,
                        ) { ExportService.shareCharacter(context, entity) }
                        .testTag(GodTags.heroShare(entity.id))
                        .godTouchSize()
                        .padding(Spacing.sm),
                )
            }
        }
        GodCard(
            contentPadding = PaddingValues(vertical = Spacing.md),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceEvenly,
            ) {
                GodStatTile(
                    label = stringResource(R.string.character_stat_ac),
                    value = derived["ac"] ?: stringResource(R.string.character_stat_ac_default),
                )
                GodStatTile(
                    label = stringResource(R.string.character_stat_hp),
                    value = stringResource(
                        R.string.character_hp_pattern,
                        derived["hp"] ?: stringResource(R.string.character_stat_hp_default),
                        derived["maxHp"] ?: stringResource(R.string.character_stat_hp_default),
                    ),
                    valueColor = CritRed,
                )
                GodStatTile(
                    label = stringResource(R.string.character_stat_speed),
                    value = stringResource(
                        R.string.character_speed_unit,
                        derived["speed"] ?: (entity.speed ?: stringResource(R.string.character_stat_speed_default)),
                    ),
                )
            }
        }
        GodCard(
            title = {
                Text(
                    text = stringResource(R.string.character_ability_scores),
                    style = MaterialTheme.typography.titleMedium,
                    color = GoldAccent,
                )
            },
        ) {
            abilityOrder.chunked(3).forEach { row ->
                Row(
                    modifier = Modifier.fillMaxWidth().padding(top = Spacing.sm),
                    horizontalArrangement = Arrangement.SpaceEvenly,
                ) {
                    row.forEach { key ->
                        val score = abilities[key]?.toIntOrNull()
                            // The data is guarded with toIntOrNull but the fallback used an unguarded
        // toInt(). character_ability_default is "10" in the only locale we ship,
        // so this is latent - but any locale rendering it differently ("—",
        // "N/A", full-width or Arabic-Indic digits) threw NumberFormatException
        // while rendering the sheet.
        ?: stringResource(R.string.character_ability_default).toIntOrNull()
        ?: 10
                        val mod = abilityModifier(score)
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Text(
                                text = key.uppercase(),
                                style = MaterialTheme.typography.labelLarge,
                                color = TextSecondary,
                            )
                            Text(
                                text = "$score",
                                style = MaterialTheme.typography.titleLarge,
                                fontWeight = FontWeight.Bold,
                                color = TextPrimary,
                            )
                            Text(
                                text = if (mod >= 0) "+$mod" else "$mod",
                                style = MaterialTheme.typography.bodyMedium,
                                color = GoldAccent,
                            )
                        }
                    }
                }
            }
        }
        SheetSection(
            title = stringResource(R.string.character_proficiencies),
            entries = proficiencies,
        )
        SheetSection(
            title = stringResource(R.string.character_feats),
            entries = feats,
        )
        CharacterEquipmentCard(summary = equipment)
        if (!entity.spellcasting.isNullOrBlank()) {
            SheetSection(
                title = stringResource(R.string.character_spellcasting),
                entries = flatEntries(entity.spellcasting),
            )
        }
        if (!entity.conditions.isNullOrBlank()) {
            SheetSection(
                title = stringResource(R.string.character_conditions),
                entries = flatEntries(entity.conditions),
            )
        }
        if (!entity.notes.isNullOrBlank()) {
            GodCard(
                title = {
                    Text(
                        text = stringResource(R.string.character_notes),
                        style = MaterialTheme.typography.titleMedium,
                        color = GoldAccent,
                    )
                },
            ) {
                Text(
                    text = entity.notes,
                    style = MaterialTheme.typography.bodyMedium,
                    color = TextPrimary,
                    modifier = Modifier.padding(top = Spacing.xs),
                )
            }
        }
        val crossHub = pendingCrossHubSync
        if (crossHub != null && crossHub.characterId == entity.id) {
            AlertDialog(
                onDismissRequest = { onDismissCrossHubSync?.invoke() },
                modifier = Modifier.testTag(GodTags.heroCrossHubDialog(entity.id)),
                title = {
                    Text(
                        text = stringResource(R.string.character_sync_cross_hub_title),
                        style = MaterialTheme.typography.titleMedium,
                        color = GoldAccent,
                    )
                },
                text = {
                    Text(
                        text = if (crossHub.previousHubUrl.isNotBlank()) {
                            stringResource(
                                R.string.character_sync_cross_hub_message,
                                crossHub.previousHubUrl,
                                crossHub.targetHubUrl,
                                crossHub.campaignId,
                            )
                        } else {
                            stringResource(
                                R.string.character_sync_cross_hub_message_unknown,
                                crossHub.targetHubUrl,
                                crossHub.campaignId,
                            )
                        },
                        style = MaterialTheme.typography.bodyMedium,
                        color = TextPrimary,
                    )
                },
                confirmButton = {
                    Text(
                        text = stringResource(R.string.character_sync_cross_hub_confirm),
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        color = GoldAccent,
                        modifier = Modifier
                            .testTag(GodTags.heroCrossHubConfirm(entity.id))
                            .clickable(role = Role.Button) {
                                onConfirmCrossHubSync?.invoke()
                                    ?: onSync?.invoke(entity.id, crossHub.campaignId, true)
                            }
                            .godTouchHeight()
                            .padding(Spacing.sm),
                    )
                },
                dismissButton = {
                    Text(
                        text = stringResource(R.string.character_sync_cross_hub_cancel),
                        style = MaterialTheme.typography.titleMedium,
                        color = TextPrimary,
                        modifier = Modifier
                            .testTag(GodTags.heroCrossHubCancel(entity.id))
                            .clickable(role = Role.Button) {
                                onDismissCrossHubSync?.invoke()
                            }
                            .godTouchHeight()
                            .padding(Spacing.sm),
                    )
                },
            )
        }
        // Issue #33 Phase 4: a 409 is never resolved silently. The user
        // picks: keep the local sheet (re-push at the Hub's revision) or
        // adopt the Hub's row (replaces the local sheet).
        val conflict = pendingSyncConflict
        if (conflict != null && conflict.characterId == entity.id) {
            AlertDialog(
                onDismissRequest = { onDismissConflict?.invoke() },
                modifier = Modifier.testTag(GodTags.heroConflictDialog(entity.id)),
                title = {
                    Text(
                        text = stringResource(R.string.character_sync_conflict_title),
                        style = MaterialTheme.typography.titleMedium,
                        color = GoldAccent,
                    )
                },
                text = {
                    Text(
                        text = stringResource(
                            R.string.character_sync_conflict_message,
                            conflict.currentRevision,
                        ),
                        style = MaterialTheme.typography.bodyMedium,
                        color = TextPrimary,
                    )
                },
                confirmButton = {
                    Text(
                        text = stringResource(R.string.character_sync_conflict_keep_mine),
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        color = GoldAccent,
                        modifier = Modifier
                            .testTag(GodTags.heroConflictKeepMine(entity.id))
                            .clickable(role = Role.Button) {
                                onResolveConflictKeepMine?.invoke()
                            }
                            .godTouchHeight()
                            .padding(Spacing.sm),
                    )
                },
                dismissButton = {
                    Text(
                        text = stringResource(R.string.character_sync_conflict_use_server),
                        style = MaterialTheme.typography.titleMedium,
                        color = TextPrimary,
                        modifier = Modifier
                            .testTag(GodTags.heroConflictUseServer(entity.id))
                            .clickable(role = Role.Button) {
                                onResolveConflictUseServer?.invoke()
                            }
                            .godTouchHeight()
                            .padding(Spacing.sm),
                    )
                },
            )
        }
    }
}

@Composable
private fun CharacterEquipmentCard(summary: EquipmentSummary?) {
    GodCard(
        modifier = Modifier.testTag(GodTags.HERO_EQUIPMENT),
        title = {
            Text(
                text = stringResource(R.string.character_equipment),
                style = MaterialTheme.typography.titleMedium,
                color = GoldAccent,
            )
        },
    ) {
        if (summary == null || summary.isEmpty) {
            Text(
                text = stringResource(R.string.value_not_set),
                style = MaterialTheme.typography.bodyMedium,
                color = TextSecondary,
                modifier = Modifier.padding(top = Spacing.xs),
            )
        } else {
            EquipmentGroup(
                title = stringResource(R.string.character_weapons),
                lines = summary.weapons,
            )
            EquipmentGroup(
                title = stringResource(R.string.character_armor),
                lines = summary.armor,
            )
            EquipmentGroup(
                title = stringResource(R.string.character_shield),
                lines = summary.shield,
            )
            EquipmentGroup(
                title = stringResource(R.string.character_gear),
                lines = summary.gear,
            )
            if (summary.coins.isNotEmpty()) {
                Text(
                    text = stringResource(
                        R.string.character_entry_pattern,
                        stringResource(R.string.character_coins),
                        summary.coins.joinToString(" · ") { "${it.first} ${it.second}" },
                    ),
                    style = MaterialTheme.typography.bodyMedium,
                    color = TextPrimary,
                    modifier = Modifier.padding(top = Spacing.sm),
                )
            }
            EquipmentGroup(
                title = null,
                lines = summary.other,
            )
        }
    }
}

@Composable
private fun EquipmentGroup(
    title: String?,
    lines: List<EquipmentLine>,
) {
    if (lines.isEmpty()) return
    if (title != null) {
        Text(
            text = title,
            style = MaterialTheme.typography.titleSmall,
            color = GoldAccent,
            modifier = Modifier.padding(top = Spacing.md),
        )
    }
    lines.forEach { line ->
        Column(modifier = Modifier.padding(top = Spacing.sm)) {
            Text(
                text = line.name,
                style = MaterialTheme.typography.bodyLarge,
                color = TextPrimary,
            )
            line.details.forEach { (key, value) ->
                Text(
                    text = if (key == "value") {
                        value
                    } else {
                        stringResource(R.string.character_entry_pattern, key, value)
                    },
                    style = MaterialTheme.typography.bodyMedium,
                    color = TextSecondary,
                )
            }
        }
    }
}

@Composable
private fun SheetSection(
    title: String,
    entries: List<Pair<String, String>>,
) {
    GodCard(
        title = {
            Text(
                text = title,
                style = MaterialTheme.typography.titleMedium,
                color = GoldAccent,
            )
        },
    ) {
        if (entries.isEmpty()) {
            Text(
                text = stringResource(R.string.value_not_set),
                style = MaterialTheme.typography.bodyMedium,
                color = TextSecondary,
                modifier = Modifier.padding(top = Spacing.xs),
            )
        } else {
            entries.forEach { (key, value) ->
                Text(
                    text = stringResource(R.string.character_entry_pattern, key, value),
                    style = MaterialTheme.typography.bodyMedium,
                    color = TextPrimary,
                    modifier = Modifier.padding(top = Spacing.xs),
                )
            }
        }
    }
}
