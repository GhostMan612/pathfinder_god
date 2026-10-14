// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.combat

import android.util.Log
import com.pathfindergod.spoke.data.network.CombatSceneRequest
import com.pathfindergod.spoke.data.network.HubApiFactory
import com.pathfindergod.spoke.ui.viewmodel.CombatUiState
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * Publishes the live combat scene to the Hub so the GM narrates against real HP,
 * turn order and conditions instead of guessing.
 *
 * Resilience rules, in order of importance:
 *  - Never block or crash the UI. Every dispatch is fire-and-forget on IO.
 *  - A missing Hub is the normal case at the table (laptop off), so failures
 *    are swallowed after one log line rather than surfaced as an error.
 *  - Coalesce bursts: dragging an HP slider fires many state updates, so
 *    dispatches are debounced rather than queued one-per-keystroke.
 */
class CombatSceneProducer(
    private val baseUrlProvider: () -> String,
    private val campaignId: Int = 1,
    private val scope: CoroutineScope = CoroutineScope(SupervisorJob() + Dispatchers.IO),
) {

    @Volatile
    private var pending: CombatUiState? = null

    @Volatile
    private var inFlight = false

    /** Called from the ViewModel on every combat state change. Cheap and safe. */
    fun onStateChanged(state: CombatUiState) {
        pending = state
        if (inFlight) return
        inFlight = true
        scope.launch { drainLoop() }
    }

    private suspend fun drainLoop() {
        try {
            while (true) {
                val state = pending ?: break
                pending = null
                publish(state)
            }
        } finally {
            inFlight = false
        }
    }

    private suspend fun publish(state: CombatUiState) {
        val scene = CombatSceneSerializer.toSceneJson(state, campaignId)
        try {
            withContext(Dispatchers.IO) {
                HubApiFactory.get(baseUrlProvider())
                    .setCombatScene(CombatSceneRequest(campaignId = campaignId, scene = scene))
            }
        } catch (e: Exception) {
            // Deliberately swallowed: the Hub may be unreachable/offline, which
            // must never interrupt combat. Log once at debug level.
            Log.d(TAG, "combat scene publish skipped: ${e.javaClass.simpleName}")
        }
    }

    private companion object {
        const val TAG = "CombatSceneProducer"
    }
}