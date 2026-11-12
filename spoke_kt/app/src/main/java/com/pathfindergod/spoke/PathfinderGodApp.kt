// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke

import android.app.Application
import com.pathfindergod.spoke.data.network.HubApiFactory
import com.pathfindergod.spoke.data.security.SpokeCredentialVault

class PathfinderGodApp : Application() {
    override fun onCreate() {
        super.onCreate()
        val vault = SpokeCredentialVault.get(this)
        vault.setChangeListener { HubApiFactory.refreshClient() }
        HubApiFactory.init(vault)
    }

    override fun onTerminate() {
        HubApiFactory.shutdown()
        super.onTerminate()
    }
}
