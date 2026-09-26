package space.tokenpay.id.internal

import android.util.Base64
import java.security.MessageDigest
import java.security.SecureRandom

/**
 * Generates PKCE S256 verifier + challenge pairs per RFC 7636.
 */
internal object PkceUtils {
    private val secureRandom = SecureRandom()

    data class Pair(val verifier: String, val challenge: String, val method: String = "S256")

    /**
     * Generate a PKCE pair. Verifier is 43-char URL-safe base64 of 32 random bytes,
     * challenge = BASE64URL(SHA256(verifier)).
     */
    fun generate(): Pair {
        val verifierBytes = ByteArray(32).also { secureRandom.nextBytes(it) }
        val verifier = Base64.encodeToString(
            verifierBytes,
            Base64.URL_SAFE or Base64.NO_PADDING or Base64.NO_WRAP,
        )
        val sha = MessageDigest.getInstance("SHA-256").digest(verifier.toByteArray(Charsets.US_ASCII))
        val challenge = Base64.encodeToString(
            sha,
            Base64.URL_SAFE or Base64.NO_PADDING or Base64.NO_WRAP,
        )
        return Pair(verifier = verifier, challenge = challenge)
    }

    /**
     * Generate a cryptographically-random state string for CSRF protection.
     */
    fun randomState(sizeBytes: Int = 24): String {
        val bytes = ByteArray(sizeBytes).also { secureRandom.nextBytes(it) }
        return Base64.encodeToString(bytes, Base64.URL_SAFE or Base64.NO_PADDING or Base64.NO_WRAP)
    }

    /**
     * Generate a random nonce for OIDC.
     */
    fun randomNonce(): String = randomState(16)
}
