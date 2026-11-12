// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.security

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import com.pathfindergod.spoke.data.network.HubEndpoint
import java.io.File
import java.io.FileOutputStream
import java.nio.charset.StandardCharsets
import java.nio.file.Files
import java.nio.file.StandardCopyOption
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec
import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json

enum class VaultState {
    EMPTY,
    READY,
    CORRUPT,
}

class VaultCorruptedException(message: String) : IllegalStateException(message)

interface CredentialVault {
    fun getState(): VaultState
    fun getHubUrl(): String?
    fun getApiKey(endpoint: String? = null): String?
    fun setApiKey(key: String?)
    fun getCertificatePin(endpoint: String? = null): String?
    fun setCertificatePin(pin: String?)
    fun setCredentials(hubUrl: String, apiKey: String?, pin: String? = null)
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
    val hubUrl: String? = null,
    val apiKey: String? = null,
    val certificatePin: String? = null,
)

class SpokeCredentialVault(
    private val storageDir: File,
    private val keyProvider: KeyProvider,
) : CredentialVault {

    private val json = Json { ignoreUnknownKeys = true }
    private val vaultFile = File(storageDir, VAULT_FILE_NAME)
    private val tempFile = File(storageDir, "$VAULT_FILE_NAME.tmp")

    @Volatile
    private var cachedState: VaultState = VaultState.EMPTY

    @Volatile
    private var cachedPayload: VaultPayload = VaultPayload()

    init {
        loadInternal()
    }

    @Synchronized
    override fun getState(): VaultState = cachedState

    @Synchronized
    override fun getHubUrl(): String? {
        if (cachedState != VaultState.READY) return null
        return cachedPayload.hubUrl
    }

    @Synchronized
    override fun getApiKey(endpoint: String?): String? {
        if (cachedState != VaultState.READY) return null
        val payload = cachedPayload
        if (endpoint != null && !isEndpointMatching(endpoint, payload.hubUrl)) {
            return null
        }
        return payload.apiKey
    }

    @Synchronized
    override fun setApiKey(key: String?) {
        if (cachedState == VaultState.CORRUPT) {
            throw VaultCorruptedException("Cannot update corrupted vault. Call clear() to explicitly reset.")
        }
        val current = cachedPayload
        val updated = current.copy(apiKey = key?.trim()?.ifEmpty { null })
        saveInternal(updated)
    }

    @Synchronized
    override fun getCertificatePin(endpoint: String?): String? {
        if (cachedState != VaultState.READY) return null
        val payload = cachedPayload
        if (endpoint != null && !isEndpointMatching(endpoint, payload.hubUrl)) {
            return null
        }
        return payload.certificatePin
    }

    @Synchronized
    override fun setCertificatePin(pin: String?) {
        if (cachedState == VaultState.CORRUPT) {
            throw VaultCorruptedException("Cannot update corrupted vault. Call clear() to explicitly reset.")
        }
        val current = cachedPayload
        val updated = current.copy(certificatePin = pin?.trim()?.ifEmpty { null })
        saveInternal(updated)
    }

    @Synchronized
    override fun setCredentials(hubUrl: String, apiKey: String?, pin: String?) {
        if (cachedState == VaultState.CORRUPT) {
            throw VaultCorruptedException("Cannot update corrupted vault. Call clear() to explicitly reset.")
        }
        val normalizedUrl = HubEndpoint.normalize(hubUrl)
        val updated = VaultPayload(
            hubUrl = normalizedUrl,
            apiKey = apiKey?.trim()?.ifEmpty { null },
            certificatePin = pin?.trim()?.ifEmpty { null } ?: cachedPayload.certificatePin,
        )
        saveInternal(updated)
    }

    @Synchronized
    override fun clear() {
        if (tempFile.exists()) {
            tempFile.delete()
        }
        if (vaultFile.exists()) {
            vaultFile.delete()
        }
        cachedState = VaultState.EMPTY
        cachedPayload = VaultPayload()
    }

    private fun isEndpointMatching(requested: String, bound: String?): Boolean {
        if (bound.isNullOrBlank()) return false
        val reqUri = try { java.net.URI(requested) } catch (_: Exception) { return false }
        val bndUri = try { java.net.URI(bound) } catch (_: Exception) { return false }
        val reqScheme = reqUri.scheme?.lowercase() ?: return false
        val bndScheme = bndUri.scheme?.lowercase() ?: return false
        val schemesMatch = reqScheme == bndScheme ||
            (reqScheme == "ws" && bndScheme == "http") ||
            (reqScheme == "http" && bndScheme == "ws") ||
            (reqScheme == "wss" && bndScheme == "https") ||
            (reqScheme == "https" && bndScheme == "wss")
        if (!schemesMatch) return false
        val reqHost = reqUri.host ?: return false
        val bndHost = bndUri.host ?: return false
        if (!reqHost.equals(bndHost, ignoreCase = true)) return false
        val reqPort = if (reqUri.port != -1) reqUri.port else (if (reqScheme == "https" || reqScheme == "wss") 443 else 80)
        val bndPort = if (bndUri.port != -1) bndUri.port else (if (bndScheme == "https" || bndScheme == "wss") 443 else 80)
        return reqPort == bndPort
    }

    private fun loadInternal() {
        if (!vaultFile.exists()) {
            cachedState = VaultState.EMPTY
            cachedPayload = VaultPayload()
            return
        }
        try {
            val bytes = vaultFile.readBytes()
            if (bytes.size < IV_SIZE_BYTES + TAG_SIZE_BYTES) {
                cachedState = VaultState.CORRUPT
                cachedPayload = VaultPayload()
                return
            }
            val iv = bytes.copyOfRange(0, IV_SIZE_BYTES)
            val ciphertext = bytes.copyOfRange(IV_SIZE_BYTES, bytes.size)
            val cipher = Cipher.getInstance(AES_GCM_TRANSFORMATION)
            val spec = GCMParameterSpec(TAG_SIZE_BITS, iv)
            cipher.init(Cipher.DECRYPT_MODE, keyProvider.getSecretKey(), spec)
            val plaintextBytes = cipher.doFinal(ciphertext)
            val plaintext = String(plaintextBytes, StandardCharsets.UTF_8)
            val payload = json.decodeFromString<VaultPayload>(plaintext)
            cachedPayload = payload
            cachedState = if (payload.apiKey == null && payload.hubUrl == null && payload.certificatePin == null) {
                VaultState.EMPTY
            } else {
                VaultState.READY
            }
        } catch (_: Exception) {
            cachedState = VaultState.CORRUPT
            cachedPayload = VaultPayload()
        }
    }

    private fun saveInternal(payload: VaultPayload) {
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

        try {
            FileOutputStream(tempFile).use { fos ->
                fos.write(output)
                fos.flush()
                fos.fd.sync()
            }
            Files.move(
                tempFile.toPath(),
                vaultFile.toPath(),
                StandardCopyOption.ATOMIC_MOVE,
                StandardCopyOption.REPLACE_EXISTING,
            )
            if (!vaultFile.exists() || vaultFile.length() != output.size.toLong()) {
                throw IllegalStateException("Atomic vault file write verification failed")
            }
            cachedPayload = payload
            cachedState = VaultState.READY
        } catch (e: Exception) {
            if (tempFile.exists()) {
                tempFile.delete()
            }
            throw e
        }
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
