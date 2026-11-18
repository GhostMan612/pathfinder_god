// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.service

import android.content.Context
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.pathfindergod.spoke.data.local.AppDatabase
import com.pathfindergod.spoke.data.local.AppPreferences
import com.pathfindergod.spoke.data.network.HubApiFactory
import com.pathfindergod.spoke.data.repository.CharacterRepository
import com.pathfindergod.spoke.data.repository.HubBinding
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.CancellationException

/**
 * Schedules the sync-outbox retry worker (Issue #33 Phase 3).
 *
 * Two lanes, both unique so they can never stack:
 * - a periodic 15-minute sweep (the WorkManager minimum) that picks up
 *   entries whose backoff has expired, even if the app was killed;
 * - a one-time immediate run requested after every failed sync attempt.
 * Both require network. The worker itself is a thin shell: all replay,
 * backoff and conflict logic lives in [CharacterRepository], which the unit
 * tests cover without WorkManager test infrastructure.
 */
object SyncWorkScheduler {
    const val PERIODIC_WORK_NAME = "sync-outbox-periodic"
    const val ONE_TIME_WORK_NAME = "sync-outbox-now"

    fun schedulePeriodic(context: Context) {
        val request = PeriodicWorkRequestBuilder<SyncRetryWorker>(15, TimeUnit.MINUTES)
            .setConstraints(networkConstraints())
            .build()
        WorkManager.getInstance(context).enqueueUniquePeriodicWork(
            PERIODIC_WORK_NAME,
            ExistingPeriodicWorkPolicy.KEEP,
            request,
        )
    }

    fun scheduleNow(context: Context) {
        val request = OneTimeWorkRequestBuilder<SyncRetryWorker>()
            .setConstraints(networkConstraints())
            .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS)
            .build()
        WorkManager.getInstance(context).enqueueUniqueWork(
            ONE_TIME_WORK_NAME,
            ExistingWorkPolicy.REPLACE,
            request,
        )
    }

    private fun networkConstraints(): Constraints =
        Constraints.Builder()
            .setRequiredNetworkType(NetworkType.CONNECTED)
            .build()
}

class SyncRetryWorker(
    appContext: Context,
    params: WorkerParameters,
) : CoroutineWorker(appContext, params) {
    override suspend fun doWork(): Result {
        return try {
            val context = applicationContext
            val prefs = AppPreferences(context)
            val repository = CharacterRepository(
                AppDatabase.get(context),
                apiProvider = { HubApiFactory.get(prefs.baseUrl()) },
                selectedCampaignIdProvider = { prefs.selectedCampaignId() },
                hubUrlProvider = { prefs.baseUrl() },
                bindingProvider = { HubBinding.of(prefs.baseUrl(), HubApiFactory::get) },
                scheduleRetry = { SyncWorkScheduler.scheduleNow(context) },
            )
            repository.replayDueOutboxEntries()
            Result.success()
        } catch (e: CancellationException) {
            throw e
        } catch (_: Exception) {
            Result.retry()
        }
    }
}
