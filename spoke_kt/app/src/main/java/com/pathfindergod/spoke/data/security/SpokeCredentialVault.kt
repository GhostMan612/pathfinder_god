// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.security

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import java.io.File
import java.io.FileOutputStream
import java.nio.charset.StandardCharsets
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec
import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json

interface CredentialVault {
    fun getApiKey(): String?
    fun setApiKey(key: String?)
    fun getCertificatePin(): String?
    fun setCertificatePin(pin: String?)
    fun getHubUrl(): String?
    fun setHubUrl(url: String?)
    fun clear()
}

interface KeyProvider {
    fun getSecretKey(): SecretKey
}

class AndroidKeystoreKeyProvider(
    private val keyAlias: String = SpokeCredentialVault.DEFAULT_KEY_ALIAS,
) : KeyProvider {
    override fun getSecretKey(): SecretKey {
        val keyStore = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        if (!keyStore.containsAlias(keyAlias)) {
            val keyGenerator = KeyGenerator.getInstance(
                KeyProperties.KEY_ALGORITHM_AES,
                "AndroidKeyStore",
            )
            val spec = KeyGenParameterSpec.Builder(
                keyAlias,
                KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT,
            )
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256)
                .build()
            keyGenerator.init(spec)
            keyGenerator.generateKey()
        }
        val entry = keyStore.getEntry(keyAlias, null) as? KeyStore.SecretKeyEntry
            ?: throw IllegalStateException("Failed to retrieve secret key for alias: $keyAlias")
        return entry.secretKey
    }
}

class JvmSecretKeyProvider(
    private val secretKey: SecretKey,
) : KeyProvider {
    override fun getSecretKey(): SecretKey = secretKey
}

@Serializable
internal data class VaultPayload(
    val apiKey: String? = null,
    val certificatePin: String? = null,
    val hubUrl: String? = null,
)

class SpokeCredentialVault(
    private val storageDir: File,
    private val keyProvider: KeyProvider,
) : CredentialVault {

    private val json = Json { ignoreUnknownKeys = true }
    private val vaultFile = File(storageDir, VAULT_FILE_NAME)

    @Synchronized
    override fun getApiKey(): String? = loadPayload().apiKey

    @Synchronized
    override fun setApiKey(key: String?) {
        val current = loadPayload()
        savePayload(current.copy(apiKey = key?.trim()?.ifEmpty { null }))
    }

    @Synchronized
    override fun getCertificatePin(): String? = loadPayload().certificatePin

    @Synchronized
    override fun setCertificatePin(pin: String?) {
        val current = loadPayload()
        savePayload(current.copy(certificatePin = pin?.trim()?.ifEmpty { null }))
    }

    @Synchronized
    override fun getHubUrl(): String? = loadPayload().hubUrl

    @Synchronized
    override fun setHubUrl(url: String?) {
        val current = loadPayload()
        savePayload(current.copy(hubUrl = url?.trim()?.ifEmpty { null }))
    }

    @Synchronized
    override fun clear() {
        if (vaultFile.exists()) {
            vaultFile.delete()
        }
    }

    private fun loadPayload(): VaultPayload {
        if (!vaultFile.exists()) return VaultPayload()
        return try {
            val bytes = vaultFile.readBytes()
            if (bytes.size < IV_SIZE_BYTES + TAG_SIZE_BYTES) {
                return VaultPayload()
            }
            val iv = bytes.copyOfRange(0, IV_SIZE_BYTES)
            val ciphertext = bytes.copyOfRange(IV_SIZE_BYTES, bytes.size)
            val cipher = Cipher.getInstance(AES_GCM_TRANSFORMATION)
            val spec = GCMParameterSpec(TAG_SIZE_BITS, iv)
            cipher.init(Cipher.DECRYPT_MODE, keyProvider.getSecretKey(), spec)
            val plaintextBytes = cipher.doFinal(ciphertext)
            val plaintext = String(plaintextBytes, StandardCharsets.UTF_8)
            json.decodeFromString<VaultPayload>(plaintext)
        } catch (_: Exception) {
            VaultPayload()
        }
    }

    private fun savePayload(payload: VaultPayload) {
        if (payload.apiKey == null && payload.certificatePin == null && payload.hubUrl == null) {
            clear()
            return
        }
        val plaintext = json.encodeToString(payload)
        val plaintextBytes = plaintext.toByteArray(StandardCharsets.UTF_8)

        val cipher = Cipher.getInstance(AES_GCM_TRANSFORMATION)
        cipher.init(Cipher.ENCRYPT_MODE, keyProvider.getSecretKey())
        val iv = cipher.iv
        val ciphertext = cipher.doFinal(plaintextBytes)

        val output = ByteArray(iv.size + ciphertext.size)
        System.arraycopy(iv, 0, output, 0, iv.size)
        System.arraycopy(ciphertext, 0, output, iv.size, ciphertext.size)

        if (!storageDir.exists()) {
            storageDir.mkdirs()
        }
        val tempFile = File(storageDir, "$VAULT_FILE_NAME.tmp")
        FileOutputStream(tempFile).use { fos ->
            fos.write(output)
            fos.flush()
        }
        if (vaultFile.exists()) {
            vaultFile.delete()
        }
        tempFile.renameTo(vaultFile)
    }

    companion object {
        const val DEFAULT_KEY_ALIAS = "spoke_hub_credentials_v1"
        const val VAULT_FILE_NAME = "spoke_vault.enc"
        private const val AES_GCM_TRANSFORMATION = "AES/GCM/NoPadding"
        private const val IV_SIZE_BYTES = 12
        private const val TAG_SIZE_BYTES = 16
        private const val TAG_SIZE_BITS = 128

        @Volatile
        private var instance: CredentialVault? = null

        fun get(context: Context): CredentialVault {
            return instance ?: synchronized(this) {
                instance ?: SpokeCredentialVault(
                    storageDir = File(context.filesDir, "security"),
                    keyProvider = AndroidKeystoreKeyProvider(),
                ).also { instance = it }
            }
        }

        fun init(vault: CredentialVault) {
            synchronized(this) {
                instance = vault
            }
        }

        fun instanceOrNull(): CredentialVault? = instance
    }
}
