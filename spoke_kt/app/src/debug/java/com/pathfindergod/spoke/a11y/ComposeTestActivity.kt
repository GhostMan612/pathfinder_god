// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.a11y

import androidx.activity.ComponentActivity

/**
 * Host activity for the Compose UI tests. Debug-only, so it never reaches a
 * shippable build.
 *
 * Why not androidx.activity.ComponentActivity, which ui-test-manifest supplies?
 * That activity is contributed to the APPLICATION manifest via
 * `debugImplementation`, so it inherits Theme.PathfinderGod, which parents
 * Theme.AppCompat. It launches (logcat confirms "Displayed") but the
 * ComposeTestRule never registers a Compose root, so every test fails with
 * "No compose hierarchies found in the app" - including a minimal
 * `setContent { Text("smoke") }`, which proves it is not the design system.
 *
 * It must also live in the app process, not the instrumentation APK: declaring it
 * in src/androidTest/AndroidManifest.xml fails with "Intent in process
 * com.pathfindergod.spoke resolved to different process
 * com.pathfindergod.spoke.test". Hence src/debug, not src/androidTest.
 *
 * It is deliberately NOT MainActivity: that extends the AGDK GameActivity, which
 * owns a native surface and is not a valid Compose test host.
 */
class ComposeTestActivity : ComponentActivity()