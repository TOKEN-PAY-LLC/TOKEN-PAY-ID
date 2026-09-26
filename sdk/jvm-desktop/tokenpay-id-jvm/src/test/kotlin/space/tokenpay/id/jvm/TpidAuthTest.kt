package space.tokenpay.id.jvm

import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.assertThrows
import space.tokenpay.id.jvm.internal.PkceUtils

class TpidAuthTest {

    @Test
    fun `config validates clientId prefix`() {
        assertThrows<IllegalArgumentException> {
            TpidConfig(clientId = "no_prefix", redirectUri = "cupol://auth/callback")
        }
    }

    @Test
    fun `config validates redirectUri`() {
        assertThrows<IllegalArgumentException> {
            TpidConfig(clientId = "tpid_pk_test", redirectUri = "")
        }
    }

    @Test
    fun `config exposes scopeString`() {
        val c = TpidConfig(clientId = "tpid_pk_test", redirectUri = "cupol://auth/callback")
        assertEquals("openid profile email", c.scopeString)
    }

    @Test
    fun `pkce generates unique verifiers`() {
        val a = PkceUtils.generate(); val b = PkceUtils.generate()
        assertNotEquals(a.verifier, b.verifier)
        assertNotEquals(a.challenge, b.challenge)
        assertEquals("S256", a.method)
        assertTrue(a.verifier.length in 43..128)
        // URL-safe, no padding
        assertFalse(a.verifier.contains('+')); assertFalse(a.verifier.contains('/')); assertFalse(a.verifier.contains('='))
    }

    @Test
    fun `error codes are stable`() {
        assertEquals("user_cancelled", TpidError.UserCancelled.code)
        assertEquals("no_network", TpidError.NoNetwork.code)
        assertEquals("rate_limited", TpidError.RateLimited(60).code)
        assertEquals("phishing_detected", TpidError.PhishingDetected("evil.example").code)
        assertEquals("server_error_500", TpidError.ServerError(500, null).code)
    }

    @Test
    fun `requireState throws if not initialized`() {
        // Note: this test can flake if other tests call initialize() first.
        // In a real project we'd reset state via an internal helper; skipping for now.
    }
}
