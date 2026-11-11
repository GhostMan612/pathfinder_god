// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.network

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.net.HttpURLConnection
import java.net.URL

class LanHubSmokeTest {

    @Test
    fun configuredHubHealthEndpointResponds() {
        val url = URL("${TestHubUrl.resolve()}/health")
        val conn = url.openConnection() as HttpURLConnection
        conn.connectTimeout = 5000
        conn.readTimeout = 5000
        try {
            val code = conn.responseCode
            assertEquals(200, code)
            val body = conn.inputStream.bufferedReader().use { it.readText() }
            assertTrue(body.contains("\"status\":\"ok\""))
        } finally {
            conn.disconnect()
        }
    }
}
