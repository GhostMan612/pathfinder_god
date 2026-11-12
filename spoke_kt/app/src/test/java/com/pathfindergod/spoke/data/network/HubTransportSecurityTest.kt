// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.network

import com.pathfindergod.spoke.data.security.CredentialVault
import com.pathfindergod.spoke.data.security.VaultState
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class HubTransportSecurityTest {

    private class MockVault(
        private val boundHubUrl: String,
        private val key: String?,
    ) : CredentialVault {
        override fun getState(): VaultState = VaultState.READY
        override fun getHubUrl(): String = boundHubUrl
        override fun getApiKey(endpoint: String?): String? {
            if (endpoint != null && !endpoint.contains(boundHubUrl.replace("https://", "").replace("http://", "").replace("wss://", "").replace("ws://", "").trimEnd('/'))) {
                return null
            }
            return key
        }
        override fun setApiKey(key: String?) {}
        override fun getCertificatePin(endpoint: String?): String? = null
        override fun setCertificatePin(pin: String?) {}
        override fun setCredentials(hubUrl: String, apiKey: String?, pin: String?) {}
        override fun setChangeListener(listener: (() -> Unit)?) {}
        override fun clear() {}
    }

    @Test
    fun cleartextIsRefusedForRemoteHosts() {
        assertFalse(HubTransportSecurity.isCleartextPermitted("http://192.168.1.50:8000/api"))
        assertFalse(HubTransportSecurity.isCleartextPermitted("ws://192.168.1.50:8000/stream"))
        assertFalse(HubTransportSecurity.isCleartextPermitted("http://example.com/health"))
        assertFalse(HubTransportSecurity.isCleartextPermitted("ws://example.com/stream"))
        assertFalse(HubTransportSecurity.isCleartextPermitted("ftp://localhost:21"))
    }

    @Test
    fun cleartextIsPermittedOnlyForLocalhostAndEmulator() {
        assertTrue(HubTransportSecurity.isCleartextPermitted("http://10.0.2.2:8000/"))
        assertTrue(HubTransportSecurity.isCleartextPermitted("ws://10.0.2.2:8000/stream"))
        assertTrue(HubTransportSecurity.isCleartextPermitted("http://localhost:8000/api"))
        assertTrue(HubTransportSecurity.isCleartextPermitted("ws://localhost:8000/stream"))
        assertTrue(HubTransportSecurity.isCleartextPermitted("http://127.0.0.1:8000/test"))
        assertTrue(HubTransportSecurity.isCleartextPermitted("ws://127.0.0.1:8000/ws"))
    }

    @Test
    fun secureTransportsAreAlwaysPermitted() {
        assertTrue(HubTransportSecurity.isCleartextPermitted("https://hub.example.com/api"))
        assertTrue(HubTransportSecurity.isCleartextPermitted("wss://hub.example.com/stream"))
        assertTrue(HubTransportSecurity.isCleartextPermitted("https://192.168.1.50:8000/"))
        assertTrue(HubTransportSecurity.isCleartextPermitted("wss://192.168.1.50:8000/stream"))
    }

    @Test
    fun authorizedApiKeyWithheldForRemoteCleartextEvenWhenPaired() {
        val vault = MockVault("192.168.1.50:8000", "my-secret-key")
        assertNull(HubTransportSecurity.getAuthorizedApiKey("http://192.168.1.50:8000/api", vault))
        assertNull(HubTransportSecurity.getAuthorizedApiKey("ws://192.168.1.50:8000/stream", vault))
    }

    @Test
    fun authorizedApiKeyDeliveredForSecureAndLocalHosts() {
        val secureVault = MockVault("hub.example.com", "secret-token")
        assertEquals("secret-token", HubTransportSecurity.getAuthorizedApiKey("https://hub.example.com/api", secureVault))
        assertEquals("secret-token", HubTransportSecurity.getAuthorizedApiKey("wss://hub.example.com/stream", secureVault))

        val localVault = MockVault("10.0.2.2:8000", "local-token")
        assertEquals("local-token", HubTransportSecurity.getAuthorizedApiKey("http://10.0.2.2:8000/api", localVault))
        assertEquals("local-token", HubTransportSecurity.getAuthorizedApiKey("ws://10.0.2.2:8000/stream", localVault))
    }
}
