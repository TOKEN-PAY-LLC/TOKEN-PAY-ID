package space.tokenpay.id

/**
 * Errors that can terminate a widget session.
 */
sealed class TpidError(val code: String, message: String, cause: Throwable? = null) : Exception(message, cause) {

    /** User explicitly cancelled from within the widget UI. */
    data object UserCancelled : TpidError("user_cancelled", "User cancelled the flow")

    /** No network connection. */
    data object NoNetwork : TpidError("no_network", "No network connection")

    /** Request timed out after retry. */
    data object Timeout : TpidError("timeout", "Network request timed out")

    data class ServerUnavailable(val reason: String? = null) :
        TpidError("server_unavailable", reason ?: "Server unavailable")

    data class TlsFailure(val reason: String? = null) :
        TpidError("tls_failure", reason ?: "TLS handshake failed")

    data class StorageFailure(val reason: String? = null) :
        TpidError("storage_failure", reason ?: "Local secure storage failed")

    /** Server returned invalid credentials. */
    data class InvalidCredentials(val reason: String? = null) :
        TpidError("invalid_credentials", reason ?: "Invalid email or password")

    /** Account is locked (too many failed attempts / suspended). */
    data class AccountLocked(val until: String?) :
        TpidError("account_locked", "Account locked" + (until?.let { " until $it" } ?: ""))

    /** Email verification required before sign-in. */
    data object EmailNotVerified : TpidError("email_not_verified", "Email address not verified")

    /** 2FA required but not provided / wrong code. */
    data class TwoFactorRequired(val methods: List<String>) :
        TpidError("totp_required", "Two-factor authentication required")

    /** Passkey challenge failed. */
    data class PasskeyFailed(val reason: String) :
        TpidError("passkey_failed", "Passkey authentication failed: $reason")

    /** Rate limited. [retryAfterSec] — seconds until retry is allowed. */
    data class RateLimited(val retryAfterSec: Int) :
        TpidError("rate_limited", "Rate limited, retry in ${retryAfterSec}s")

    /** TLS pin mismatch — possible MITM. Widget aborts and clears stored tokens. */
    data class PhishingDetected(val hostname: String) :
        TpidError("phishing_detected", "TLS certificate pin mismatch for $hostname")

    /** Server returned an OAuth error. */
    data class OAuthError(val oauthCode: String, val description: String?) :
        TpidError("oauth_error", "$oauthCode: ${description ?: ""}")

    /** SDK misconfigured (bad clientId, redirectUri, etc.). */
    data class ConfigurationError(val reason: String) :
        TpidError("config_error", "Configuration error: $reason")

    /** Server unreachable or returned HTTP 5xx. */
    data class ServerError(val status: Int, val reason: String?) :
        TpidError("server_error", "Server error $status${reason?.let { ": $it" } ?: ""}")

    /**
     * Anything else. Prefer [throwable] for chained diagnostics;
     * [Throwable.getCause] is also wired for standard Java call sites.
     */
    data class Unknown(val throwable: Throwable?) :
        TpidError("unknown", throwable?.let { "${it.javaClass.simpleName}: ${it.message ?: "Unknown error"}" } ?: "Unknown error", throwable)
}
