// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.network

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assume
import org.junit.Test
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL

/**
 * Opt-in smoke check that a real handset can reach a running Hub.
 *
 * This asserts a *deployment*, not app behaviour: it can only pass when a developer
 * has a Hub listening on a LAN address (or `adb reverse` in place). Folding that into
 * `connectedDebugAndroidTest` made the whole device lane fail on a perfectly good
 * build whenever the laptop daemon was down, so an unreachable Hub now skips with the
 * reason attached. A Hub that answers with the wrong status still fails hard -- that
 * is a real defect rather than missing infrastructure.
 */
class LanHubSmokeTest {

    @Test
    fun configuredHubHealthEndpointResponds() {
        val base = try {
            TestHubUrl.resolve()
        } catch (exc: IllegalStateException) {
            // No valid physical-device target configured (e.g. a stale 127.0.0.1
            // from Settings, or no hubBaseUrl argument). Nothing to smoke-test.
            Assume.assumeTrue("LAN hub smoke test skipped: ${exc.message}", false)
            return
        }

        val conn = URL("$base/health").openConnection() as HttpURLConnection
        conn.connectTimeout = 5000
        conn.readTimeout = 5000
        conn.instanceFollowRedirects = false

        try {
            conn.connect()
        } catch (exc: IOException) {
            // Connection refused, unknown host, timeout: infrastructure absent.
            Assume.assumeTrue(
                "LAN hub smoke test skipped: no Hub reachable at $base (${exc.javaClass.simpleName}: ${exc.message})",
                false,
            )
            return
        }

        try {
            assertEquals(200, conn.responseCode)
            val body = conn.inputStream.bufferedReader().use { it.readText() }
            assertEquals("ok", JSONObject(body).optString("status"))
        } finally {
            conn.disconnect()
        }
    }
}
