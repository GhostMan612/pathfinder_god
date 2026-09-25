// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.dice

import android.os.Build
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import com.pathfindergod.spoke.ui.motion.StaggerIn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalHapticFeedback
import com.pathfindergod.spoke.service.AudioService
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.pathfindergod.spoke.ui.theme.GoldAccent
import com.pathfindergod.spoke.ui.theme.TextPrimary
import com.pathfindergod.spoke.ui.theme.TextSecondary
import com.pathfindergod.spoke.ui.theme.rpgPanel

@Composable
fun DiceScreen() {
    val engine = remember { DiceEngine() }
    val context = LocalContext.current
    val audio = remember { AudioService(context.applicationContext) }
    val haptics = LocalHapticFeedback.current
    DisposableEffect(Unit) {
        onDispose { audio.release() }
    }
    var selected by remember { mutableStateOf(Die.D20) }
    var mode by remember { mutableStateOf(Advantage.STRAIGHT) }
    var record by remember { mutableStateOf<RollRecord?>(null) }
    var history by remember { mutableStateOf(emptyList<RollRecord>()) }
    var rollToken by remember { mutableIntStateOf(0) }
    Column(
        modifier = Modifier.fillMaxSize().padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        DiceCanvas(
            die = selected,
            face = record?.kept?.firstOrNull() ?: selected.sides,
            rollToken = rollToken,
            modifier = Modifier.size(180.dp).align(Alignment.CenterHorizontally),
            impact = record?.impact ?: Impact.NORMAL,
            onImpact = {
                val dramatic = record?.impact != null &&
                    record?.impact != Impact.NORMAL
                if (dramatic || Build.VERSION.SDK_INT < 27) {
                    haptics.performHapticFeedback(HapticFeedbackType.LongPress)
                } else {
                    haptics.performHapticFeedback(HapticFeedbackType.TextHandleMove)
                }
                if (record?.impact == Impact.CRITICAL_SUCCESS) {
                    audio.playCritChime()
                } else {
                    audio.playClatter()
                }
            },
        )
        Text(
            text = record?.let { "${it.total}" } ?: "—",
            style = MaterialTheme.typography.displayLarge,
            fontWeight = FontWeight.Bold,
            color = GoldAccent,
            modifier = Modifier.align(Alignment.CenterHorizontally),
        )
        Text(
            text = record?.let { impactLabel(it) } ?: "Choose a die and roll.",
            style = MaterialTheme.typography.bodyMedium,
            color = TextSecondary,
            modifier = Modifier.align(Alignment.CenterHorizontally),
        )
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceEvenly,
        ) {
            Die.entries.forEach { die ->
                Box(
                    modifier = Modifier
                        .rpgPanel()
                        .clickable { selected = die }
                        .padding(horizontal = 10.dp, vertical = 8.dp),
                ) {
                    Text(
                        text = "d${die.sides}",
                        color = if (die == selected) GoldAccent else TextPrimary,
                        fontWeight = if (die == selected) FontWeight.Bold else FontWeight.Normal,
                    )
                }
            }
        }
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceEvenly,
        ) {
            Advantage.entries.forEach { entry ->
                val enabled = selected == Die.D20
                Box(
                    modifier = Modifier
                        .rpgPanel()
                        .clickable(enabled = enabled) { mode = entry }
                        .padding(horizontal = 12.dp, vertical = 8.dp),
                ) {
                    Text(
                        text = entry.name.lowercase().replaceFirstChar { it.uppercase() },
                        color = when {
                            !enabled -> TextSecondary.copy(alpha = 0.4f)
                            entry == mode -> GoldAccent
                            else -> TextPrimary
                        },
                    )
                }
            }
        }
        Box(
            modifier = Modifier
                .rpgPanel()
                .clickable {
                    val notation = buildString {
                        append("d${selected.sides}")
                        if (selected == Die.D20 && mode == Advantage.ADVANTAGE) append("adv")
                        if (selected == Die.D20 && mode == Advantage.DISADVANTAGE) append("dis")
                    }
                    val result = engine.roll(notation)
                    record = result
                    history = listOf(result) + history.take(29)
                    rollToken++
                }
                .padding(vertical = 14.dp)
                .fillMaxWidth(),
            contentAlignment = Alignment.Center,
        ) {
            Text(
                text = "ROLL",
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold,
                color = GoldAccent,
            )
        }
        LazyColumn(
            modifier = Modifier.fillMaxWidth().weight(1f),
            verticalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            itemsIndexed(history) { index, entry ->
                StaggerIn(index = index) {
                    Text(
                        text = "${entry.notation} → ${entry.total}",
                        style = MaterialTheme.typography.bodyMedium,
                        color = TextSecondary,
                    )
                }
            }
        }
    }
}

private fun impactLabel(record: RollRecord): String = when (record.impact) {
    Impact.CRITICAL_SUCCESS -> "${record.notation} — critical success!"
    Impact.CRITICAL_FAILURE -> "${record.notation} — critical failure."
    Impact.NORMAL -> "${record.notation} — ${record.kept.joinToString("+")}" +
        if (record.modifier != 0) {
            "${if (record.modifier > 0) "+" else ""}${record.modifier}"
        } else {
            ""
        }
}
