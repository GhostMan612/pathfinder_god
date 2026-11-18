// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke

import android.app.Application
import com.pathfindergod.spoke.data.network.HubApiFactory
import com.pathfindergod.spoke.data.security.SpokeCredentialVault
import com.pathfindergod.spoke.service.SyncWorkScheduler

class PathfinderGodApp : Application() {
    override fun onCreate() {
        super.onCreate()
        val vault = SpokeCredentialVault.get(this)
        vault.setChangeListener { HubApiFactory.refreshClient() }
        HubApiFactory.init(vault)
        // Issue #33 Phase 3: the periodic sweep replays due outbox entries
        // even if the app was killed; the immediate run picks up anything
        // queued by a previous session.
        SyncWorkScheduler.schedulePeriodic(this)
        SyncWorkScheduler.scheduleNow(this)
    }

    override fun onTerminate() {
        HubApiFactory.shutdown()
        super.onTerminate()
    }
}
