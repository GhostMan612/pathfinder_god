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
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Clear
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.material3.TextField
import androidx.compose.material3.TextFieldDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
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
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.pathfindergod.spoke.data.local.DatabaseAssetManager
import com.pathfindergod.spoke.data.local.RulesDatabase
import com.pathfindergod.spoke.data.repository.RuleRepository
import com.pathfindergod.spoke.ui.theme.GodTypography
import com.pathfindergod.spoke.ui.theme.GoldAccent
import com.pathfindergod.spoke.ui.theme.TextPrimary
import com.pathfindergod.spoke.ui.theme.TextSecondary
import com.pathfindergod.spoke.ui.theme.rpgPanel
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
            Text(
                text = "Unearthing the rulebook…",
                style = GodTypography.titleMedium,
                color = TextSecondary,
                textAlign = TextAlign.Center,
            )
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
    Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {
        TextField(
            value = text,
            onValueChange = {
                text = it
                viewModel.search(it, edition)
            },
            singleLine = true,
            placeholder = { Text(text = "Ask the Oracle…") },
            trailingIcon = {
                if (text.isNotEmpty()) {
                    Icon(
                        imageVector = Icons.Filled.Clear,
                        contentDescription = "Clear",
                        tint = TextSecondary,
                        modifier = Modifier.clickable {
                            text = ""
                            viewModel.clear()
                        },
                    )
                }
            },
            keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
            keyboardActions = KeyboardActions(onSearch = { viewModel.search(text, edition) }),
            colors = TextFieldDefaults.colors(
                focusedTextColor = TextPrimary,
                unfocusedTextColor = TextPrimary,
                focusedContainerColor = Color.Transparent,
                unfocusedContainerColor = Color.Transparent,
                cursorColor = GoldAccent,
            ),
            modifier = Modifier.fillMaxWidth(),
        )
        Row(
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            modifier = Modifier.fillMaxWidth().padding(top = 10.dp),
        ) {
            EditionChip(label = "All", selected = edition == null) {
                edition = null
                viewModel.search(text, null)
            }
            EditionChip(label = "1e", selected = edition == "1e") {
                edition = "1e"
                viewModel.search(text, "1e")
            }
            EditionChip(label = "2e", selected = edition == "2e") {
                edition = "2e"
                viewModel.search(text, "2e")
            }
        }
        if (state.isLoading) {
            Text(
                text = "Seeking…",
                style = GodTypography.bodyMedium,
                color = TextSecondary,
                modifier = Modifier.padding(top = 8.dp),
            )
        }
        if (text.isBlank() && state.results.isEmpty()) {
            Box(
                modifier = Modifier.fillMaxWidth().weight(1f),
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    text = "44,620 entries sleep below.",
                    style = GodTypography.titleMedium,
                    color = TextSecondary,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.padding(horizontal = 32.dp),
                )
            }
        } else {
            LazyColumn(
                modifier = Modifier.fillMaxWidth().weight(1f).padding(top = 12.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
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
    selected: Boolean,
    onSelect: () -> Unit,
) {
    Text(
        text = label,
        style = GodTypography.titleMedium,
        fontWeight = if (selected) FontWeight.Bold else FontWeight.Normal,
        color = if (selected) GoldAccent else TextSecondary,
        modifier = Modifier.rpgPanel().clickable { onSelect() }.padding(horizontal = 16.dp, vertical = 8.dp),
    )
}
