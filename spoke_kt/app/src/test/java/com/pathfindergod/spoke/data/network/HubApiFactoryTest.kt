// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.network

import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

class HubApiFactoryTest {
    @After
    fun tearDown() {
        HubApiFactory.shutdown()
    }

    @Test
    fun bareLanIpIsNormalizedAndRetrofitBuildsWithoutNetwork() {
        assertEquals("http://192.168.1.5:8000/", HubEndpoint.normalize(" 192.168.1.5:8000 "))
        assertNotNull(HubApiFactory.get("192.168.1.5:8000"))
    }

    @Test
    fun secureEndpointAndDefaultArePreserved() {
        assertEquals("https://example.com:8000/", HubEndpoint.normalize("https://example.com:8000/"))
        assertEquals("http://10.0.2.2:8000/", HubEndpoint.normalize(" "))
        assertNotNull(HubApiFactory.get("   "))
        assertEquals("wss://example.com:8000/stream", HubEndpoint.streamUrl("https://example.com:8000"))
        assertEquals("ws://10.0.2.2:8000/stream", HubEndpoint.streamUrl(""))
    }

    @Test
    fun malformedOrUnsafeUrlsAreRejectedBeforeConnecting() {
        val invalid = listOf(
            "ftp://example.com", "http://", "http://user:secret@example.com",
            "http://example.com/subpath", "https://example.com/?token=secret",
            "https://example.com/#fragment", "http://example.com:0",
        )
        invalid.forEach { value ->
            assertThrows(IllegalArgumentException::class.java) {
                HubApiFactory.get(value)
            }
        }
    }

    @Test
    fun productionCleartextPolicyMatchesBundledNetworkConfig() {
        assertTrue(HubEndpoint.requiresHttpsInRelease("192.168.1.5:8000"))
        assertFalse(HubEndpoint.requiresHttpsInRelease("https://example.com:443"))
        assertFalse(HubEndpoint.requiresHttpsInRelease("http://10.0.2.2:8000"))
        assertTrue(HubEndpoint.isEmulatorOnlyAddress("10.0.2.2:8000"))
        assertFalse(HubEndpoint.isEmulatorOnlyAddress("10.0.2.20:8000"))
        assertFalse(HubEndpoint.isEmulatorOnlyAddress("http://192.168.1.7:8000"))
    }
}
