package space.tokenpay.id.jvm

import java.time.Instant

/**
 * Signed-in user profile.
 */
data class TpidUser(
    val id: String,
    val email: String,
    val emailVerified: Boolean = false,
    val name: String? = null,
    val avatarUrl: String? = null,
    val locale: String? = null,
)

/**
 * Active session holding tokens + user info.
 */
data class TpidSession(
    val accessToken: String,
    val refreshToken: String?,
    val idToken: String?,
    val expiresAt: Instant,
    val tokenType: String = "Bearer",
    val scope: String? = null,
    val user: TpidUser,
) {
    val isValid: Boolean get() = Instant.now().isBefore(expiresAt.minusSeconds(30))
}

/**
 * Result of a widget presentation.
 */
sealed class TpidResult {
    data class Success(val session: TpidSession) : TpidResult() {
        val accessToken: String get() = session.accessToken
        val user: TpidUser get() = session.user
    }
    data object Cancelled : TpidResult()
    data class Failure(val error: TpidError) : TpidResult()
}

/**
 * Typed error hierarchy.
 */
sealed class TpidError(val code: String, message: String) : RuntimeException(message) {
    data object UserCancelled : TpidError("user_cancelled", "User cancelled the widget")
    data object NoNetwork : TpidError("no_network", "No network connection")
    data object Timeout : TpidError("timeout", "Request timed out")
    data class InvalidCredentials(val reason: String?) : TpidError("invalid_credentials", reason ?: "Invalid email or password")
    data class AccountLocked(val until: String?) : TpidError("account_locked", "Account is locked${until?.let { " until $it" } ?: ""}")
    data object EmailNotVerified : TpidError("email_not_verified", "Email is not verified")
    data class RateLimited(val retryAfterSec: Int?) : TpidError("rate_limited", "Too many attempts, retry after ${retryAfterSec ?: 60}s")
    data class TwoFactorRequired(val methods: List<String>) : TpidError("totp_required", "Two-factor required: ${methods.joinToString(", ")}")
    data class ServerError(val status: Int, val reason: String?) : TpidError("server_error_$status", reason ?: "Server error $status")
    data class ConfigurationError(val reason: String) : TpidError("configuration_error", reason)
    data class OAuthError(val oauthCode: String, val description: String?) : TpidError("oauth_$oauthCode", description ?: oauthCode)
    data class PhishingDetected(val host: String) : TpidError("phishing_detected", "TLS pin mismatch for $host — aborted")
}

/** Device Flow (RFC 8628) handle — returned by [TpidAuth.startDeviceFlow]. */
data class TpidDeviceFlowSession(
    val deviceCode: String,
    val userCode: String,
    val verificationURI: String,
    val verificationURIComplete: String?,
    val expiresIn: Int,
    val interval: Int,
)
