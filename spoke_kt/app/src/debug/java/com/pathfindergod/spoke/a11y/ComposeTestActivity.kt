// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.a11y

import androidx.activity.ComponentActivity

/**
 * The Compose UI test host. Debug-only (src/debug), so it can never reach a shippable build.
 *
 * Every instrumentation test in this package launches this activity explicitly with
 * `createAndroidComposeRule<ComposeTestActivity>()`. That is the documented pattern for
 * tests that need a known host: Android's docs note that ui-test-manifest is "needed for
 * createComposeRule(), but not for createAndroidComposeRule<YourActivity>()", which
 * instead requires the activity to be declared in the app's own manifest - which is what
 * src/debug/AndroidManifest.xml does.
 *
 * It must live in src/debug rather than src/androidTest: an activity declared in the
 * androidTest manifest lands in the instrumentation APK, so ActivityScenario resolves it
 * against the test process rather than the app process and the launch fails.
 *
 * It must also not be MainActivity, which extends the AGDK GameActivity and owns a native
 * surface, so it is not a valid Compose test host.
 *
 * The XML theme is a plain platform theme (see src/debug/AndroidManifest.xml) because
 * AppCompat themes throw during window creation for a host that is not an AppCompatActivity.
 * The tests do not need one: theming comes from the PathfinderGodTheme composable called
 * inside setContent, not from the XML theme.
 *
 * Do not read this file as the explanation for the "No compose hierarchies found in the app"
 * failures that these tests previously threw on every node lookup. That was NOT host-activity
 * resolution, and it was not AGDK. The real cause was androidx.tracing:tracing being pinned
 * to 1.0.0 by AGDK's POM, which made androidx.test:monitor throw NoSuchMethodError for
 * Trace.forceEnableAppTracing() and killed the test environment before it could register a
 * Compose root. See the tracing dependency block in app/build.gradle.kts.
 */
class ComposeTestActivity : ComponentActivity()
