// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

// LICENCE OBLIGATION - this screen is the in-app half of the CC BY 3.0 and
// CC BY 4.0 attribution requirements for dice_crit.wav, tap.wav (RPG Sound
// Pack, Tuomo Untinen, CC BY 3.0) and bgm_inn.mp3 (tcarisland, CC BY 4.0).
//
// The obligation is discharged by DISPLAYING the credit, so the licence text
// must never be dropped from the rendered output. It is held in
// res/values/strings.xml as credits_license_by30 / credits_license_by40 and
// rendered by AUDIO_LICENSE_TEXTS below. This file and docs/audio-credits.md
// are the two halves and must stay in step: a credit present in only one of
// them does not discharge the licence. CC0 1.0 entries are credited anyway.
//
// Removing an entry here, or removing the licence block from this screen,
// breaks CC BY compliance. See docs/audio-credits.md.

package com.pathfindergod.spoke.ui.settings

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.pathfindergod.spoke.R
import com.pathfindergod.spoke.ui.designsystem.Dimens
import com.pathfindergod.spoke.ui.designsystem.GodBadge
import com.pathfindergod.spoke.ui.designsystem.GodBackLink
import com.pathfindergod.spoke.ui.designsystem.GodCard
import com.pathfindergod.spoke.ui.designsystem.GodSectionHeader
import com.pathfindergod.spoke.ui.designsystem.GodTags
import com.pathfindergod.spoke.ui.designsystem.GodTone
import com.pathfindergod.spoke.ui.designsystem.Spacing
import com.pathfindergod.spoke.ui.theme.GoldAccent
import com.pathfindergod.spoke.ui.theme.TextPrimary
import com.pathfindergod.spoke.ui.theme.TextSecondary

data class AudioCredit(
    val file: String,
    val titleRes: Int,
    val authorRes: Int,
    val licenseRes: Int,
    val licenseUrl: String,
    val sourceRes: Int,
    val sourceUrl: String,
    val modificationRes: Int,
    val attributionRequired: Boolean,
)

data class LicenseText(
    val nameRes: Int,
    val url: String,
    val summaryRes: Int,
)

data class AssetCredit(
    val files: List<String>,
    val titleRes: Int,
    val authorRes: Int,
    val licenseRes: Int?,
    val licenseUrl: String?,
    val sourceRes: Int,
    val sourceUrl: String,
    val modificationRes: Int,
    val attributionRequired: Boolean,
    val badgeRes: Int,
    val iconsMadeBy: Boolean = false,
)

val ASSET_ICON_CREDITS: List<AssetCredit> = listOf(
    AssetCredit(
        files = listOf(
            "res/drawable/gi_loot_coins.xml",
            "res/drawable/gi_loot_fire_gem.xml",
            "res/drawable/gi_loot_glowing_artifact.xml",
            "res/drawable/gi_loot_chest.xml",
            "res/drawable/gi_enc_trivial.xml",
            "res/drawable/gi_enc_low.xml",
            "res/drawable/gi_enc_moderate.xml",
            "res/drawable/gi_enc_severe.xml",
            "res/drawable/gi_enc_extreme.xml",
            "res/drawable/gi_cond_prone.xml",
        ),
        titleRes = R.string.credits_title_rpg_icons,
        authorRes = R.string.credits_author_delapouite,
        licenseRes = R.string.credits_license_by30,
        licenseUrl = "https://creativecommons.org/licenses/by/3.0/",
        sourceRes = R.string.credits_source_game_icons,
        sourceUrl = "https://game-icons.net/",
        modificationRes = R.string.credits_mod_icons,
        attributionRequired = true,
        badgeRes = R.string.credits_required,
        iconsMadeBy = true,
    ),
    AssetCredit(
        files = listOf(
            "res/drawable/gi_loot_crystal_cluster.xml",
            "res/drawable/gi_loot_crystal_shine.xml",
            "res/drawable/gi_cond_frightened.xml",
            "res/drawable/gi_cond_sickened.xml",
        ),
        titleRes = R.string.credits_title_rpg_icons,
        authorRes = R.string.credits_author_lorc,
        licenseRes = R.string.credits_license_by30,
        licenseUrl = "https://creativecommons.org/licenses/by/3.0/",
        sourceRes = R.string.credits_source_game_icons,
        sourceUrl = "https://game-icons.net/",
        modificationRes = R.string.credits_mod_icons,
        attributionRequired = true,
        badgeRes = R.string.credits_required,
        iconsMadeBy = true,
    ),
    AssetCredit(
        files = listOf(
            "res/drawable/ki_home.xml",
            "res/drawable/ki_dice.xml",
            "res/drawable/ki_combat.xml",
            "res/drawable/ki_hero.xml",
            "res/drawable/ki_rules.xml",
            "res/drawable/ki_campaign.xml",
            "res/drawable/ki_map.xml",
            "res/drawable/ki_encounter.xml",
            "res/drawable/ki_god.xml",
            "res/drawable/ki_setup.xml",
            "res/drawable/ki_credits.xml",
        ),
        titleRes = R.string.credits_title_kenney_icons,
        authorRes = R.string.credits_author_kenney,
        licenseRes = R.string.credits_license_cc0,
        licenseUrl = "https://creativecommons.org/publicdomain/zero/1.0/",
        sourceRes = R.string.credits_source_kenney_boardgame,
        sourceUrl = "https://kenney.nl/assets/board-game-icons",
        modificationRes = R.string.credits_mod_kenney,
        attributionRequired = false,
        badgeRes = R.string.credits_courtesy,
    ),
)

val ASSET_PROCEDURAL_CREDITS: List<AssetCredit> = listOf(
    AssetCredit(
        files = listOf("ui/designsystem/GodTexture.kt"),
        titleRes = R.string.credits_title_procedural,
        authorRes = R.string.credits_author_ours,
        licenseRes = null,
        licenseUrl = null,
        sourceRes = R.string.credits_source_ours,
        sourceUrl = "",
        modificationRes = R.string.credits_mod_procedural,
        attributionRequired = false,
        badgeRes = R.string.credits_ours,
    ),
)

val AUDIO_MUSIC_CREDITS: List<AudioCredit> = listOf(
    AudioCredit(
        file = "assets/audio/bgm_tavern.mp3",
        titleRes = R.string.credits_title_tavern,
        authorRes = R.string.credits_author_tavern,
        licenseRes = R.string.credits_license_cc0,
        licenseUrl = "https://creativecommons.org/publicdomain/zero/1.0/",
        sourceRes = R.string.credits_source_site,
        sourceUrl = "https://opengameart.org/content/medieval-the-old-tower-inn",
        modificationRes = R.string.credits_mod_music,
        attributionRequired = false,
    ),
    AudioCredit(
        file = "assets/audio/bgm_inn.mp3",
        titleRes = R.string.credits_title_inn,
        authorRes = R.string.credits_author_inn,
        licenseRes = R.string.credits_license_by40,
        licenseUrl = "https://creativecommons.org/licenses/by/4.0/",
        sourceRes = R.string.credits_source_site,
        sourceUrl = "https://opengameart.org/content/inn-music",
        modificationRes = R.string.credits_mod_music_cross,
        attributionRequired = true,
    ),
)

val AUDIO_EFFECT_CREDITS: List<AudioCredit> = listOf(
    AudioCredit(
        file = "assets/audio/dice_roll.ogg",
        titleRes = R.string.credits_title_roll,
        authorRes = R.string.credits_author_oga,
        licenseRes = R.string.credits_license_cc0,
        licenseUrl = "https://creativecommons.org/publicdomain/zero/1.0/",
        sourceRes = R.string.credits_source_rpg_sfx,
        sourceUrl = "https://opengameart.org/content/80-cc0-rpg-sfx",
        modificationRes = R.string.credits_mod_sfx,
        attributionRequired = false,
    ),
    AudioCredit(
        file = "assets/audio/dice_fail.ogg",
        titleRes = R.string.credits_title_fail,
        authorRes = R.string.credits_author_oga,
        licenseRes = R.string.credits_license_cc0,
        licenseUrl = "https://creativecommons.org/publicdomain/zero/1.0/",
        sourceRes = R.string.credits_source_rpg_sfx,
        sourceUrl = "https://opengameart.org/content/80-cc0-rpg-sfx",
        modificationRes = R.string.credits_mod_sfx,
        attributionRequired = false,
    ),
    AudioCredit(
        file = "assets/audio/error.ogg",
        titleRes = R.string.credits_title_thud,
        authorRes = R.string.credits_author_oga,
        licenseRes = R.string.credits_license_cc0,
        licenseUrl = "https://creativecommons.org/publicdomain/zero/1.0/",
        sourceRes = R.string.credits_source_cc0_sfx,
        sourceUrl = "https://opengameart.org/content/100-cc0-sfx",
        modificationRes = R.string.credits_mod_sfx,
        attributionRequired = false,
    ),
    AudioCredit(
        file = "assets/audio/dice_crit.wav",
        titleRes = R.string.credits_title_coin,
        authorRes = R.string.credits_author_untinen,
        licenseRes = R.string.credits_license_by30,
        licenseUrl = "https://creativecommons.org/licenses/by/3.0/",
        sourceRes = R.string.credits_source_rpg_sound_pack,
        sourceUrl = "https://opengameart.org/content/rpg-sound-pack",
        modificationRes = R.string.credits_mod_sfx,
        attributionRequired = true,
    ),
    AudioCredit(
        file = "assets/audio/tap.wav",
        titleRes = R.string.credits_title_tap,
        authorRes = R.string.credits_author_untinen,
        licenseRes = R.string.credits_license_by30,
        licenseUrl = "https://creativecommons.org/licenses/by/3.0/",
        sourceRes = R.string.credits_source_rpg_sound_pack,
        sourceUrl = "https://opengameart.org/content/rpg-sound-pack",
        modificationRes = R.string.credits_mod_sfx,
        attributionRequired = true,
    ),
)

val AUDIO_LICENSE_TEXTS: List<LicenseText> = listOf(
    LicenseText(
        nameRes = R.string.credits_lic_cc0_name,
        url = "https://creativecommons.org/publicdomain/zero/1.0/",
        summaryRes = R.string.credits_lic_cc0_summary,
    ),
    LicenseText(
        nameRes = R.string.credits_lic_by40_name,
        url = "https://creativecommons.org/licenses/by/4.0/",
        summaryRes = R.string.credits_lic_by40_summary,
    ),
    LicenseText(
        nameRes = R.string.credits_lic_by30_name,
        url = "https://creativecommons.org/licenses/by/3.0/",
        summaryRes = R.string.credits_lic_by30_summary,
    ),
)

@Composable
fun AudioCreditsScreen(onBack: () -> Unit) {
    LazyColumn(
        modifier = Modifier.fillMaxSize().padding(Spacing.lg),
        verticalArrangement = Arrangement.spacedBy(Spacing.md),
    ) {
        item {
            Column {
                GodSectionHeader(
                    text = stringResource(R.string.credits_title),
                    prominent = true,
                )
                GodBackLink(
                    text = stringResource(R.string.credits_back),
                    onClick = onBack,
                    testTag = GodTags.CREDITS_BACK,
                )
            }
        }
        item {
            GodCard(contentPadding = PaddingValues(Dimens.cardPaddingLoose)) {
                Text(
                    text = stringResource(R.string.credits_intro),
                    style = MaterialTheme.typography.bodyMedium,
                    color = TextPrimary,
                )
            }
        }
        item { CreditHeader(stringResource(R.string.credits_section_music)) }
        items(AUDIO_MUSIC_CREDITS, key = { it.file }) { CreditRow(it) }
        item { CreditHeader(stringResource(R.string.credits_section_effects)) }
        items(AUDIO_EFFECT_CREDITS, key = { it.file }) { CreditRow(it) }
        item { CreditHeader(stringResource(R.string.credits_section_assets)) }
        items(ASSET_ICON_CREDITS, key = { "${it.titleRes}/${it.authorRes}" }) {
            AssetCreditRow(it)
        }
        item { CreditHeader(stringResource(R.string.credits_section_procedural)) }
        items(ASSET_PROCEDURAL_CREDITS, key = { "${it.titleRes}/${it.authorRes}" }) {
            AssetCreditRow(it)
        }
        item { CreditHeader(stringResource(R.string.credits_section_licenses)) }
        items(AUDIO_LICENSE_TEXTS, key = { it.nameRes }) { license ->
            GodCard(contentPadding = PaddingValues(Dimens.cardPaddingLoose)) {
                Text(
                    text = stringResource(license.nameRes),
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    color = GoldAccent,
                )
                Text(
                    text = stringResource(license.summaryRes),
                    style = MaterialTheme.typography.bodyMedium,
                    color = TextPrimary,
                    modifier = Modifier.padding(top = Spacing.sm),
                )
                Text(
                    text = license.url,
                    style = MaterialTheme.typography.bodySmall,
                    color = TextSecondary,
                    modifier = Modifier.padding(top = Spacing.xs),
                )
            }
        }
        item {
            Text(
                text = stringResource(R.string.credits_register),
                style = MaterialTheme.typography.bodySmall,
                color = TextSecondary,
                modifier = Modifier.fillMaxWidth().padding(top = Spacing.sm),
            )
        }
    }
}

@Composable
private fun CreditHeader(label: String) {
    GodSectionHeader(
        text = label,
        modifier = Modifier.padding(top = Spacing.sm),
    )
}

@Composable
private fun CreditRow(credit: AudioCredit) {
    GodCard(contentPadding = PaddingValues(Dimens.cardPaddingLoose)) {
        CreditTitleRow(
            title = stringResource(credit.titleRes),
            required = credit.attributionRequired,
        )
        Text(
            text = stringResource(R.string.credits_by_pattern, stringResource(credit.authorRes)),
            style = MaterialTheme.typography.bodyMedium,
            color = TextPrimary,
            modifier = Modifier.padding(top = Spacing.xs),
        )
        Text(
            text = stringResource(
                R.string.credits_source_pattern,
                stringResource(credit.sourceRes),
                credit.sourceUrl,
            ),
            style = MaterialTheme.typography.bodySmall,
            color = TextSecondary,
            modifier = Modifier.padding(top = Spacing.xs),
        )
        Text(
            text = stringResource(
                R.string.credits_license_pattern,
                stringResource(credit.licenseRes),
                credit.licenseUrl,
            ),
            style = MaterialTheme.typography.bodySmall,
            color = TextSecondary,
            modifier = Modifier.padding(top = Spacing.xxs),
        )
        Text(
            text = stringResource(
                R.string.credits_changes_pattern,
                stringResource(credit.modificationRes),
            ),
            style = MaterialTheme.typography.bodySmall,
            color = TextSecondary,
            modifier = Modifier.padding(top = Spacing.xxs),
        )
        Text(
            text = credit.file,
            style = MaterialTheme.typography.bodySmall,
            color = TextSecondary,
            modifier = Modifier.padding(top = Spacing.sm),
        )
    }
}

@Composable
private fun AssetCreditRow(credit: AssetCredit) {
    val licenseRes = credit.licenseRes
    val licenseUrl = credit.licenseUrl
    GodCard(contentPadding = PaddingValues(Dimens.cardPaddingLoose)) {
        CreditTitleRow(
            title = stringResource(credit.titleRes),
            required = credit.attributionRequired,
            badgeRes = credit.badgeRes,
        )
        Text(
            text = stringResource(
                if (credit.iconsMadeBy) {
                    R.string.credits_icons_made_by_pattern
                } else {
                    R.string.credits_by_pattern
                },
                stringResource(credit.authorRes),
            ),
            style = MaterialTheme.typography.bodyMedium,
            color = TextPrimary,
            modifier = Modifier.padding(top = Spacing.xs),
        )
        if (credit.sourceUrl.isNotBlank()) {
            Text(
                text = stringResource(
                    R.string.credits_source_pattern,
                    stringResource(credit.sourceRes),
                    credit.sourceUrl,
                ),
                style = MaterialTheme.typography.bodySmall,
                color = TextSecondary,
                modifier = Modifier.padding(top = Spacing.xs),
            )
        } else {
            Text(
                text = stringResource(credit.sourceRes),
                style = MaterialTheme.typography.bodySmall,
                color = TextSecondary,
                modifier = Modifier.padding(top = Spacing.xs),
            )
        }
        if (licenseRes != null && licenseUrl != null) {
            Text(
                text = stringResource(
                    R.string.credits_license_pattern,
                    stringResource(licenseRes),
                    licenseUrl,
                ),
                style = MaterialTheme.typography.bodySmall,
                color = TextSecondary,
                modifier = Modifier.padding(top = Spacing.xxs),
            )
        }
        Text(
            text = stringResource(
                R.string.credits_changes_pattern,
                stringResource(credit.modificationRes),
            ),
            style = MaterialTheme.typography.bodySmall,
            color = TextSecondary,
            modifier = Modifier.padding(top = Spacing.xxs),
        )
        credit.files.forEachIndexed { index, path ->
            Text(
                text = path,
                style = MaterialTheme.typography.bodySmall,
                color = TextSecondary,
                modifier = Modifier.padding(
                    top = if (index == 0) Spacing.sm else Spacing.xxs,
                ),
            )
        }
    }
}

@Composable
private fun CreditTitleRow(
    title: String,
    required: Boolean,
    badgeRes: Int = if (required) R.string.credits_required else R.string.credits_courtesy,
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            text = title,
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.Bold,
            color = TextPrimary,
            modifier = Modifier.weight(1f, fill = false),
        )
        GodBadge(
            text = stringResource(badgeRes),
            tone = if (required) GodTone.Critical else GodTone.Positive,
            horizontalPadding = 0.dp,
            modifier = Modifier.padding(start = Spacing.md),
        )
    }
}
