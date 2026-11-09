// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import androidx.core.view.WindowCompat
import com.pathfindergod.spoke.ui.navigation.NavigationShell
import com.pathfindergod.spoke.ui.pit.PitFrameGovernor
import com.pathfindergod.spoke.ui.theme.PathfinderGodTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) {
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.POST_NOTIFICATIONS), 0)
        }
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
