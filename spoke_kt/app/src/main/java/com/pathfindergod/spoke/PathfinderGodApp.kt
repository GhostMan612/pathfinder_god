// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke

import android.app.Application
import com.pathfindergod.spoke.data.network.HubApiFactory

class PathfinderGodApp : Application() {
    override fun onTerminate() {
        HubApiFactory.shutdown()
        super.onTerminate()
    }
}
