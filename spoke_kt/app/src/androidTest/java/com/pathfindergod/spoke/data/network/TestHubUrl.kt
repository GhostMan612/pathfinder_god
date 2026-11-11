// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.network

import android.content.Context
import androidx.test.platform.app.InstrumentationRegistry
import com.pathfindergod.spoke.data.local.AppPreferences

/**
 * Hub base URL for instrumentation tests.
 *
 * The laptop's LAN IP changes between networks, so it must not be baked
 * into a test. Priority: the `hubBaseUrl` instrumentation argument, then
 * the hub URL the app already has stored in Settings, then the emulator
 * default. Pass the argument with either of:
 *
 *   ./gradlew connectedDebugAndroidTest -Pandroid.testInstrumentationRunnerArguments.hubBaseUrl=http://192.168.1.10:8000
 *   adb shell am instrument -e hubBaseUrl http://192.168.1.10:8000 -w com.pathfindergod.spoke.test/androidx.test.runner.AndroidJUnitRunner
 */
object TestHubUrl {
    fun resolve(context: Context? = null): String {
        val fromArg = InstrumentationRegistry.getArguments()
            .getString("hubBaseUrl")?.trim().orEmpty()
        if (fromArg.isNotEmpty()) return fromArg.trimEnd('/')
        val ctx = context
            ?: InstrumentationRegistry.getInstrumentation().targetContext
        return AppPreferences(ctx).baseUrl().trimEnd('/')
    }
}
