// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke

import android.os.Bundle
import androidx.activity.compose.setContent
import androidx.core.view.WindowCompat
import com.google.androidgamesdk.GameActivity
import com.pathfindergod.spoke.ui.navigation.NavigationShell
import com.pathfindergod.spoke.ui.pit.PitFrameGovernor
import com.pathfindergod.spoke.ui.theme.PathfinderGodTheme

class MainActivity : GameActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        WindowCompat.setDecorFitsSystemWindows(window, false)
        PitFrameGovernor.bind(this)
        setContent {
            PathfinderGodTheme {
                NavigationShell()
            }
        }
    }

    override fun onResume() {
        super.onResume()
        PitFrameGovernor.onHostResume()
    }

    override fun onPause() {
        PitFrameGovernor.onHostPause()
        super.onPause()
    }

    override fun onDestroy() {
        PitFrameGovernor.release(this)
        super.onDestroy()
    }
}
