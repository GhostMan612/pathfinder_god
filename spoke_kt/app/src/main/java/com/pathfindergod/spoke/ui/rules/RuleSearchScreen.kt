// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.rules

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
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Clear
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.pathfindergod.spoke.R
import com.pathfindergod.spoke.data.local.DatabaseAssetManager
import com.pathfindergod.spoke.data.local.RulesDatabase
import com.pathfindergod.spoke.data.repository.RuleRepository
import com.pathfindergod.spoke.ui.designsystem.Dimens
import com.pathfindergod.spoke.ui.designsystem.GodChip
import com.pathfindergod.spoke.ui.designsystem.GodEmptyState
import com.pathfindergod.spoke.ui.designsystem.GodLiveRegion
import com.pathfindergod.spoke.ui.designsystem.GodStatusText
import com.pathfindergod.spoke.ui.designsystem.GodTags
import com.pathfindergod.spoke.ui.designsystem.GodTextField
import com.pathfindergod.spoke.ui.designsystem.Spacing
import com.pathfindergod.spoke.ui.designsystem.godTouchSize
import com.pathfindergod.spoke.ui.theme.TextSecondary
import com.pathfindergod.spoke.ui.viewmodel.RuleSearchViewModel

private class RuleVmFactory(
    private val repository: RuleRepository,
) : ViewModelProvider.Factory {
    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>): T =
        RuleSearchViewModel(repository) as T
}

@Composable
internal fun rememberRuleSearchViewModel(): RuleSearchViewModel? {
    val context = LocalContext.current
    var database by remember { mutableStateOf<RulesDatabase?>(null) }
    var failed by remember { mutableStateOf(false) }
    LaunchedEffect(Unit) {
        try {
            DatabaseAssetManager.ensureExtracted(context.applicationContext)
            database = RulesDatabase.open(context.applicationContext)
        } catch (_: Exception) {
            failed = true
        }
    }
    if (failed) return null
    val current = database ?: return null
    val repository = remember(current) { RuleRepository(current) }
    return viewModel(factory = remember(current) { RuleVmFactory(repository) })
}

@Composable
fun RuleSearchScreen() {
    val viewModel = rememberRuleSearchViewModel()
    if (viewModel == null) {
        Box(
            modifier = Modifier.fillMaxSize(),
            contentAlignment = Alignment.Center,
        ) {
            GodStatusText(text = stringResource(R.string.rules_extracting))
        }
    } else {
        OracleBody(viewModel = viewModel)
    }
}

@Composable
private fun OracleBody(
    viewModel: RuleSearchViewModel,
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    var text by rememberSaveable { mutableStateOf("") }
    var edition by rememberSaveable { mutableStateOf<String?>(null) }
    Column(modifier = Modifier.fillMaxSize().padding(Spacing.lg)) {
        GodTextField(
            value = text,
            onValueChange = {
                text = it
                viewModel.search(it, edition)
            },
            placeholder = stringResource(R.string.rules_placeholder),
            trailingIcon = {
                if (text.isNotEmpty()) {
                    Icon(
                        imageVector = Icons.Filled.Clear,
                        contentDescription = stringResource(R.string.rules_clear),
                        tint = TextSecondary,
                        modifier = Modifier
                            .clickable(
                                onClickLabel = stringResource(R.string.a11y_clear_query),
                                role = Role.Button,
                            ) {
                                text = ""
                                viewModel.clear()
                            }
                            .godTouchSize()
                            .testTag(GodTags.RULES_CLEAR),
                    )
                }
            },
            imeAction = ImeAction.Search,
            keyboardActions = KeyboardActions(onSearch = { viewModel.searchNow(text, edition) }),
            modifier = Modifier.fillMaxWidth().testTag(GodTags.RULES_QUERY),
        )
        Row(
            horizontalArrangement = Arrangement.spacedBy(Spacing.sm),
            modifier = Modifier.fillMaxWidth().padding(top = Spacing.md),
        ) {
            EditionChip(
                label = stringResource(R.string.rules_edition_all),
                tag = GodTags.navTab("rules:all"),
                selected = edition == null,
            ) {
                edition = null
                viewModel.searchNow(text, null)
            }
            EditionChip(
                label = stringResource(R.string.rules_edition_1e),
                tag = GodTags.navTab("rules:1e"),
                selected = edition == "1e",
            ) {
                edition = "1e"
                viewModel.searchNow(text, "1e")
            }
            EditionChip(
                label = stringResource(R.string.rules_edition_2e),
                tag = GodTags.navTab("rules:2e"),
                selected = edition == "2e",
            ) {
                edition = "2e"
                viewModel.searchNow(text, "2e")
            }
        }
        if (state.isLoading) {
            GodStatusText(
                text = stringResource(R.string.rules_seeking),
                modifier = Modifier.padding(top = Spacing.sm),
            )
        }
        if (state.results.isNotEmpty() && !state.isLoading) {
            GodLiveRegion(
                text = stringResource(R.string.a11y_rules_results, state.results.size),
                tag = GodTags.RULES_RESULT_COUNT,
                modifier = Modifier.padding(top = Spacing.xs),
            )
        }
        if (text.isBlank() && state.results.isEmpty()) {
            Box(
                modifier = Modifier.fillMaxWidth().weight(1f),
                contentAlignment = Alignment.Center,
            ) {
                GodEmptyState(text = stringResource(R.string.rules_entry_count))
            }
        } else {
            LazyColumn(
                modifier = Modifier.fillMaxWidth().weight(1f).padding(top = Spacing.md),
                verticalArrangement = Arrangement.spacedBy(Dimens.gridSpacing),
            ) {
                itemsIndexed(state.results, key = { _, rule -> rule.rowId }) { index, rule ->
                    StaggerIn(index = index, modifier = Modifier.animateItem()) {
                        RuleCard(rule = rule)
                    }
                }
            }
        }
    }
}

@Composable
private fun EditionChip(
    label: String,
    tag: String,
    selected: Boolean,
    onSelect: () -> Unit,
) {
    GodChip(
        label = label,
        selected = selected,
        onClick = onSelect,
        horizontalPadding = Spacing.lg,
        testTag = tag,
    )
}
