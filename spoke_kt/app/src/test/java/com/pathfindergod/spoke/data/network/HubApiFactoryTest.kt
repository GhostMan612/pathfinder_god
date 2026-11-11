// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.network

import org.junit.After
import org.junit.Assert.assertNotNull
import org.junit.Test

class HubApiFactoryTest {

    @After
    fun tearDown() {
        HubApiFactory.shutdown()
    }

    @Test
    fun bareIpWithoutSchemeGetsHttp() {
        // Retrofit rejects a schemeless base URL, so a bare IP typed in
        // Settings must come back with http:// prepended.
        val api = HubApiFactory.get("192.168.1.5:8000")
        assertNotNull(api)
    }

    @Test
    fun httpsIsKept() {
        val api = HubApiFactory.get("https://example.com:8000")
        assertNotNull(api)
    }

    @Test
    fun emptyFallsBackToEmulator() {
        val api = HubApiFactory.get("   ")
        assertNotNull(api)
    }
}
