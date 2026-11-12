// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.security

import java.io.File
import java.nio.file.Files
import javax.crypto.KeyGenerator
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
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
        SpokeCredentialVault.init(
            SpokeCredentialVault(tempDir, keyProvider)
        )
    }

    @Test
    fun roundTripStoresAndRetrievesEncryptedCredentials() {
        assertNull(vault.getApiKey())
        assertNull(vault.getCertificatePin())
        assertNull(vault.getHubUrl())

        vault.setApiKey("test-api-key-12345")
        vault.setCertificatePin("sha256/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
        vault.setHubUrl("https://hub.example.com:8000")

        assertEquals("test-api-key-12345", vault.getApiKey())
        assertEquals("sha256/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=", vault.getCertificatePin())
        assertEquals("https://hub.example.com:8000", vault.getHubUrl())

        // Ensure file exists and does NOT contain raw plaintext secrets
        val vaultFile = File(tempDir, SpokeCredentialVault.VAULT_FILE_NAME)
        assertTrue(vaultFile.exists())
        val rawBytes = vaultFile.readBytes()
        val rawString = String(rawBytes)
        assertFalse("Ciphertext must not expose API key in plaintext", rawString.contains("test-api-key-12345"))
        assertFalse("Ciphertext must not expose Hub URL in plaintext", rawString.contains("hub.example.com"))
    }

    @Test
    fun whitespaceIsTrimmedAndBlanksTreatedAsNull() {
        vault.setApiKey("   ")
        assertNull(vault.getApiKey())

        vault.setApiKey("  secret-key  ")
        assertEquals("secret-key", vault.getApiKey())

        vault.setApiKey(null)
        assertNull(vault.getApiKey())
    }

    @Test
    fun clearWipesEncryptedStorageFile() {
        vault.setApiKey("my-secret-key")
        val vaultFile = File(tempDir, SpokeCredentialVault.VAULT_FILE_NAME)
        assertTrue(vaultFile.exists())

        vault.clear()
        assertFalse(vaultFile.exists())
        assertNull(vault.getApiKey())
    }

    @Test
    fun corruptedCiphertextFailsClosedWithoutCrashing() {
        vault.setApiKey("super-secret-key")
        val vaultFile = File(tempDir, SpokeCredentialVault.VAULT_FILE_NAME)
        assertTrue(vaultFile.exists())

        val bytes = vaultFile.readBytes()
        // Corrupt a byte in the encrypted ciphertext / tag
        bytes[bytes.size - 1] = (bytes[bytes.size - 1].toInt() xor 0xFF).toByte()
        vaultFile.writeBytes(bytes)

        // Must fail closed: return null instead of throwing an unhandled exception
        assertNull(vault.getApiKey())
    }

    @Test
    fun truncatedFileFailsClosed() {
        val vaultFile = File(tempDir, SpokeCredentialVault.VAULT_FILE_NAME)
        vaultFile.writeBytes(byteArrayOf(1, 2, 3, 4)) // Truncated (< IV + TAG size)

        assertNull(vault.getApiKey())
        assertNull(vault.getCertificatePin())
    }

    @Test
    fun differentKeyFailsClosedWithoutPlaintextExposure() {
        vault.setApiKey("vault-secret-value")

        // Create a second vault using a different AES-256 key over the same storage file
        val keyGen2 = KeyGenerator.getInstance("AES")
        keyGen2.init(256)
        val otherKeyProvider = JvmSecretKeyProvider(keyGen2.generateKey())
        val otherVault = SpokeCredentialVault(tempDir, otherKeyProvider)

        // Decryption must fail closed
        assertNull(otherVault.getApiKey())
    }
}
