package space.tokenpay.id.jvm

import java.net.URI

/**
 * Configuration for the TOKEN PAY ID JVM Desktop SDK.
 *
 * Pass an instance to [TpidAuth.initialize] at application startup.
 */
data class TpidConfig(
    /** Public API key, format `tpid_pk_...`. */
    val clientId: String,

    /** Custom URI scheme for loopback redirect, e.g. `cupol-vpn://auth/callback`. */
    val redirectUri: String,

    /** OAuth 2.0 scopes. */
    val scopes: List<String> = listOf("openid", "profile", "email"),

    /** Issuer base URL. Override only for staging. */
    val issuer: URI = URI.create("https://id.tokenpay.space"),

    /** Require TLS certificate pinning. MUST be true in production. */
    val pinTLSCertificates: Boolean = true,

    /** UI theme. */
    val theme: Theme = Theme.AUTO,

    /** UI language. `null` = auto-detect from `Locale.getDefault()`. */
    val language: String? = null,

    /** Send telemetry events (no PII) — users can opt-out. */
    val enableTelemetry: Boolean = true,

    /** Allow passkey / biometric sign-in when available. */
    val allowPasskey: Boolean = true,

    /** Optional prefilled email. */
    val prefillEmail: String? = null,

    /** Partner branding override. `null` = fetch from `/sdk/config`. */
    val brandingOverride: Branding? = null,

    /** Per-request logger (redacts PII). */
    val logger: ((String) -> Unit)? = null,
) {
    init {
        require(clientId.isNotBlank()) { "clientId is required" }
        require(clientId.startsWith("tpid_pk_")) { "clientId must start with tpid_pk_" }
        require(redirectUri.isNotBlank()) { "redirectUri is required" }
        require(scopes.isNotEmpty()) { "scopes must be non-empty" }
    }

    val scopeString: String get() = scopes.joinToString(" ")

    enum class Theme { LIGHT, DARK, AUTO }

    enum class Language(val code: String) {
        SYSTEM("system"),
        RUSSIAN("ru"),
        ENGLISH("en"),
        CHINESE("zh");
        companion object {
            fun fromCode(code: String?): Language = values().firstOrNull { it.code == code } ?: SYSTEM
        }
    }

    data class Branding(
        val appName: String,
        val primaryColor: Long = 0xFF000000,
        val logoUrl: String? = null,
    )
}
