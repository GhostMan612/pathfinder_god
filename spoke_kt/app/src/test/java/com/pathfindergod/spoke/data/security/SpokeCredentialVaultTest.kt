// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.security

import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.nio.file.Files
import java.util.concurrent.atomic.AtomicInteger
import javax.crypto.KeyGenerator
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class SpokeCredentialVaultTest {

    private lateinit var tempDir: File
    private lateinit var keyProvider: JvmSecretKeyProvider
    private lateinit var vault: SpokeCredentialVault

    @Before
    fun setUp() {
        tempDir = Files.createTempDirectory("spoke_vault_test").toFile()
        val keyGen = KeyGenerator.getInstance("AES")
        keyGen.init(256)
        val secretKey = keyGen.generateKey()
        keyProvider = JvmSecretKeyProvider(secretKey)
        vault = SpokeCredentialVault(tempDir, keyProvider)
    }

    @After
    fun tearDown() {
        tempDir.deleteRecursively()
    }

    @Test
    fun roundTripStoresAndRetrievesEncryptedCredentials() {
        assertEquals(VaultState.EMPTY, vault.getState())
        assertNull(vault.getApiKey())
        assertNull(vault.getCertificatePin())
        assertNull(vault.getHubUrl())

        vault.setCredentials(
            hubUrl = "https://hub.example.com:8000",
            apiKey = "test-api-key-12345",
            pin = "sha256/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
        )

        assertEquals(VaultState.READY, vault.getState())
        assertEquals("test-api-key-12345", vault.getApiKey("https://hub.example.com:8000"))
        assertEquals("sha256/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=", vault.getCertificatePin("https://hub.example.com:8000"))
        assertEquals("https://hub.example.com:8000/", vault.getHubUrl())

        val vaultFile = File(tempDir, SpokeCredentialVault.VAULT_FILE_NAME)
        assertTrue(vaultFile.exists())
        val rawBytes = vaultFile.readBytes()
        val rawString = String(rawBytes)
        assertFalse(rawString.contains("test-api-key-12345"))
        assertFalse(rawString.contains("hub.example.com"))
    }

    @Test
    fun credentialsAreBoundToApprovedEndpoint() {
        vault.setCredentials(
            hubUrl = "https://alpha.hub.local:8000",
            apiKey = "alpha-secret-key",
            pin = "sha256/AlphaPin=",
        )

        assertEquals("alpha-secret-key", vault.getApiKey("https://alpha.hub.local:8000"))
        assertEquals("alpha-secret-key", vault.getApiKey("https://alpha.hub.local:8000/"))
        assertEquals("sha256/AlphaPin=", vault.getCertificatePin("https://alpha.hub.local:8000"))

        assertNull(vault.getApiKey("https://beta.hub.local:8000"))
        assertNull(vault.getApiKey("http://alpha.hub.local:8000"))
        assertNull(vault.getCertificatePin("https://beta.hub.local:8000"))
    }

    @Test
    fun switchingHubsRequiresExplicitNewCredentialsAndDoesNotCarryOverPin() {
        vault.setCredentials(
            hubUrl = "https://alpha.hub.local:8000",
            apiKey = "alpha-secret-key",
            pin = "sha256/AlphaPin=",
        )
        assertEquals("alpha-secret-key", vault.getApiKey("https://alpha.hub.local:8000"))
        assertEquals("sha256/AlphaPin=", vault.getCertificatePin("https://alpha.hub.local:8000"))

        vault.setCredentials(
            hubUrl = "https://beta.hub.local:8000",
            apiKey = null,
            pin = null,
        )
        assertEquals("https://beta.hub.local:8000/", vault.getHubUrl())
        assertNull(vault.getApiKey("https://beta.hub.local:8000"))
        assertNull(vault.getApiKey("https://alpha.hub.local:8000"))
        assertNull(vault.getCertificatePin("https://beta.hub.local:8000"))
        assertNull(vault.getCertificatePin("https://alpha.hub.local:8000"))
    }

    @Test
    fun corruptedCiphertextSetsCorruptStateAndRefusesOverwrites() {
        vault.setCredentials(
            hubUrl = "https://hub.example.com:8000",
            apiKey = "valuable-key",
        )
        assertEquals(VaultState.READY, vault.getState())

        val vaultFile = File(tempDir, SpokeCredentialVault.VAULT_FILE_NAME)
        assertTrue(vaultFile.exists())
        val bytes = vaultFile.readBytes()
        bytes[bytes.size - 1] = (bytes[bytes.size - 1].toInt() xor 0xFF).toByte()
        vaultFile.writeBytes(bytes)

        val reloadedVault = SpokeCredentialVault(tempDir, keyProvider)
        assertEquals(VaultState.CORRUPT, reloadedVault.getState())
        assertNull(reloadedVault.getApiKey("https://hub.example.com:8000"))

        assertThrows(VaultCorruptedException::class.java) {
            reloadedVault.setApiKey("replacement-attempt")
        }
        assertThrows(VaultCorruptedException::class.java) {
            reloadedVault.setCredentials("https://hub.example.com:8000", "new-key")
        }

        reloadedVault.clear()
        assertEquals(VaultState.EMPTY, reloadedVault.getState())
        reloadedVault.setCredentials("https://hub.example.com:8000", "recovered-key")
        assertEquals(VaultState.READY, reloadedVault.getState())
        assertEquals("recovered-key", reloadedVault.getApiKey("https://hub.example.com:8000"))
    }

    @Test
    fun truncatedFileSetsCorruptState() {
        val vaultFile = File(tempDir, SpokeCredentialVault.VAULT_FILE_NAME)
        vaultFile.writeBytes(byteArrayOf(1, 2, 3, 4))

        val corruptVault = SpokeCredentialVault(tempDir, keyProvider)
        assertEquals(VaultState.CORRUPT, corruptVault.getState())
        assertNull(corruptVault.getApiKey())
    }

    @Test
    fun atomicBackupFileRecoversStateOnInterruptedWrite() {
        vault.setCredentials(
            hubUrl = "https://hub.example.com:8000",
            apiKey = "original-intact-key",
        )
        assertEquals(VaultState.READY, vault.getState())

        val vaultFile = File(tempDir, SpokeCredentialVault.VAULT_FILE_NAME)
        val backupFile = File(tempDir, "${SpokeCredentialVault.VAULT_FILE_NAME}.bak")
        vaultFile.copyTo(backupFile, overwrite = true)
        vaultFile.writeBytes(byteArrayOf(0, 0, 0, 0))

        val reloaded = SpokeCredentialVault(tempDir, keyProvider)
        assertEquals(VaultState.READY, reloaded.getState())
        assertEquals("original-intact-key", reloaded.getApiKey("https://hub.example.com:8000"))
    }

    @Test
    fun changeListenerFiresOnUpdates() {
        val changeCount = AtomicInteger(0)
        vault.setChangeListener { changeCount.incrementAndGet() }

        vault.setCredentials("https://hub.example.com:8000", "key1")
        assertEquals(1, changeCount.get())

        vault.setApiKey("key2")
        assertEquals(2, changeCount.get())

        vault.setCertificatePin("sha256/NewPin=")
        assertEquals(3, changeCount.get())

        vault.clear()
        assertEquals(4, changeCount.get())
    }

    @Test
    fun validPrimaryWithStaleBackupRetainsPrimaryWhenRestorationFails() {
        vault.setCredentials(
            hubUrl = "https://hub.example.com:8000",
            apiKey = "valid-primary-key",
        )
        assertEquals(VaultState.READY, vault.getState())

        val backupFile = File(tempDir, "${SpokeCredentialVault.VAULT_FILE_NAME}.bak")
        backupFile.writeBytes(byteArrayOf(1, 2, 3, 4, 5))

        val vaultFile = File(tempDir, SpokeCredentialVault.VAULT_FILE_NAME)
        FileOutputStream(vaultFile, true).use { _ ->
            val reloaded = SpokeCredentialVault(tempDir, keyProvider)
            assertEquals(VaultState.READY, reloaded.getState())
            assertEquals("valid-primary-key", reloaded.getApiKey("https://hub.example.com:8000"))
        }
    }

    @Test
    fun failedBackupRestorationDistinguishesCorruptFromEmpty() {
        val backupFile = File(tempDir, "${SpokeCredentialVault.VAULT_FILE_NAME}.bak")
        backupFile.writeBytes(byteArrayOf(1, 2, 3, 4))

        val vaultFile = File(tempDir, SpokeCredentialVault.VAULT_FILE_NAME)
        assertFalse(vaultFile.exists())

        FileOutputStream(backupFile, true).use { _ ->
            val reloaded = SpokeCredentialVault(tempDir, keyProvider)
            assertEquals(VaultState.CORRUPT, reloaded.getState())
            assertNull(reloaded.getApiKey())
        }
    }

    @Test
    fun failedDeletionOnClearThrowsIOExceptionAndPreservesState() {
        vault.setCredentials(
            hubUrl = "https://hub.example.com:8000",
            apiKey = "indestructible-key",
        )
        assertEquals(VaultState.READY, vault.getState())

        val vaultFile = File(tempDir, SpokeCredentialVault.VAULT_FILE_NAME)
        FileOutputStream(vaultFile, true).use { _ ->
            assertThrows(IOException::class.java) {
                vault.clear()
            }
            assertEquals(VaultState.READY, vault.getState())
            assertEquals("indestructible-key", vault.getApiKey("https://hub.example.com:8000"))
        }

        val reloaded = SpokeCredentialVault(tempDir, keyProvider)
        assertEquals(VaultState.READY, reloaded.getState())
        assertEquals("indestructible-key", reloaded.getApiKey("https://hub.example.com:8000"))
    }

    @Test
    fun staleBackupIsCleanedUpOnSuccessfulSave() {
        vault.setCredentials(
            hubUrl = "https://hub.example.com:8000",
            apiKey = "key-v1",
        )
        assertEquals(VaultState.READY, vault.getState())

        val backupFile = File(tempDir, "${SpokeCredentialVault.VAULT_FILE_NAME}.bak")
        backupFile.writeBytes(byteArrayOf(9, 9, 9, 9))
        assertTrue(backupFile.exists())

        vault.setCredentials(
            hubUrl = "https://hub.example.com:8000",
            apiKey = "key-v2",
        )
        assertEquals(VaultState.READY, vault.getState())
        assertEquals("key-v2", vault.getApiKey("https://hub.example.com:8000"))
        assertFalse(backupFile.exists())

        val reloaded = SpokeCredentialVault(tempDir, keyProvider)
        assertEquals(VaultState.READY, reloaded.getState())
        assertEquals("key-v2", reloaded.getApiKey("https://hub.example.com:8000"))
    }

    @Test
    fun saveFailsIfStaleBackupCannotBeRemoved() {
        vault.setCredentials(
            hubUrl = "https://hub.example.com:8000",
            apiKey = "original-key",
        )
        val backupFile = File(tempDir, "${SpokeCredentialVault.VAULT_FILE_NAME}.bak")
        backupFile.writeBytes(byteArrayOf(1, 2, 3))

        FileOutputStream(backupFile, true).use { _ ->
            assertThrows(IOException::class.java) {
                vault.setCredentials(
                    hubUrl = "https://hub.example.com:8000",
                    apiKey = "new-key",
                )
            }
            assertEquals(VaultState.READY, vault.getState())
            assertEquals("original-key", vault.getApiKey("https://hub.example.com:8000"))
        }

        val reloaded = SpokeCredentialVault(tempDir, keyProvider)
        assertEquals(VaultState.READY, reloaded.getState())
        assertEquals("original-key", reloaded.getApiKey("https://hub.example.com:8000"))
    }
}
