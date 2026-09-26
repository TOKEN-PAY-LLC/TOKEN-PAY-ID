package space.tokenpay.id.jvm.internal

import java.security.MessageDigest
import java.security.SecureRandom
import java.util.Base64

internal data class Pkce(val verifier: String, val challenge: String, val method: String = "S256")

/** PKCE (RFC 7636) + state/nonce generator using SecureRandom. */
internal object PkceUtils {
    private val rnd = SecureRandom()

    fun generate(): Pkce {
        val bytes = ByteArray(32).also(rnd::nextBytes)
        val verifier = Base64.getUrlEncoder().withoutPadding().encodeToString(bytes)
        val sha = MessageDigest.getInstance("SHA-256").digest(verifier.toByteArray(Charsets.US_ASCII))
        val challenge = Base64.getUrlEncoder().withoutPadding().encodeToString(sha)
        return Pkce(verifier, challenge)
    }

    fun randomState(): String {
        val b = ByteArray(24).also(rnd::nextBytes)
        return Base64.getUrlEncoder().withoutPadding().encodeToString(b)
    }

    fun randomNonce(): String = randomState()
}
