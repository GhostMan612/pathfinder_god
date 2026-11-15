// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.network

import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Test

class TestHubUrlTest {
    @Test fun explicitArgumentOverridesSettings() {
        assertEquals(
            "http://192.168.1.7:8000",
            TestHubUrl.choose(" 192.168.1.7:8000/ ", "http://192.168.1.8:8000", false),
        )
    }

    @Test fun savedCustomHttpsEndpointWorks() {
        assertEquals(
            "https://hub.example.test:443",
            TestHubUrl.choose(null, "https://hub.example.test:443/", false),
        )
    }

    @Test fun physicalDeviceCannotSilentlyUseEmulatorAddress() {
        assertEquals(
            "http://10.0.2.2:8000",
            TestHubUrl.choose(null, "http://10.0.2.2:8000", true),
        )
        assertThrows(IllegalStateException::class.java) {
            TestHubUrl.choose(null, "http://10.0.2.2:8000", false)
        }
        // Even an explicit emulator-only URL is invalid on a real handset.
        assertThrows(IllegalStateException::class.java) {
            TestHubUrl.choose("http://10.0.2.2:8000", "", false)
        }
    }

    @Test fun malformedTransportOrCredentialsAreRejected() {
        assertThrows(IllegalArgumentException::class.java) {
            TestHubUrl.choose("ftp://hub.example.test", "", false)
        }
        assertThrows(IllegalArgumentException::class.java) {
            TestHubUrl.choose("http://name:secret@hub.example.test", "", false)
        }
    }

    @Test fun physicalDeviceCannotSilentlyUseLoopback() {
        // A saved 127.0.0.1 reached the smoke test as a bare ConnectException
        // because only 10.0.2.2 was validated. Loopback is equally meaningless
        // on a handset: it names the phone, not the laptop.
        assertThrows(IllegalStateException::class.java) {
            TestHubUrl.choose(null, "http://127.0.0.1:8000", false)
        }
        assertThrows(IllegalStateException::class.java) {
            TestHubUrl.choose("http://localhost:8000", "", false)
        }
        // Deliberately still allowed on an emulator: `adb reverse` can map the
        // device's loopback onto the host, and 10.0.2.2 stays the default.
        assertEquals(
            "http://127.0.0.1:8000",
            TestHubUrl.choose(null, "http://127.0.0.1:8000", true),
        )
    }
}
