package space.tokenpay.id

/**
 * Configuration for TOKEN PAY ID native widget.
 *
 * @property clientId Your public client key (`tpid_pk_...`). Required.
 * @property redirectUri OAuth redirect URI. Must match the one registered for your client.
 *           Typical value: `"${applicationId}:/auth/callback"`.
 * @property scopes OAuth scopes requested. Default: `[openid, profile, email]`.
 * @property issuer Base URL of the authorization server. Default: `https://id.tokenpay.space`.
 * @property theme Widget color theme. Default: [Theme.AUTO] (follows system).
 * @property language UI language. Default: [Language.SYSTEM].
 * @property presentation How the widget is shown. Default: [Presentation.MODAL].
 * @property prefillEmail Pre-fill the email field (for multi-account flows).
 * @property allowRegister Whether the widget shows the "Create account" option. Default: true.
 * @property allowPasskey Enable passkey/biometric authentication. Default: true.
 * @property allowRecovery Enable recovery flow in the widget. Default: true.
 * @property allowScreenshots Disable FLAG_SECURE for screenshots (debug only). Default: false.
 * @property pinTlsCertificates Enable TLS certificate pinning. Default: true. Disable only for dev.
 * @property enableTelemetry Send anonymous funnel events to TOKEN PAY. Default: true.
 * @property brandingOverride Force custom branding (normally fetched from server based on clientId).
 */
data class TpidConfig(
    val clientId: String,
    val redirectUri: String,
    val scopes: List<String> = listOf("openid", "profile", "email"),
    val issuer: String = "https://id.tokenpay.space",
    val theme: Theme = Theme.AUTO,
    val language: Language = Language.SYSTEM,
    val presentation: Presentation = Presentation.MODAL,
    val prefillEmail: String? = null,
    val allowRegister: Boolean = true,
    val allowPasskey: Boolean = true,
    val allowRecovery: Boolean = true,
    val allowScreenshots: Boolean = false,
    val pinTlsCertificates: Boolean = true,
    val enableTelemetry: Boolean = true,
    val brandingOverride: Branding? = null,
) {
    init {
        require(clientId.startsWith("tpid_pk_")) { "clientId must start with 'tpid_pk_'" }
        require(redirectUri.isNotBlank()) { "redirectUri required" }
        require(scopes.isNotEmpty()) { "at least one scope required" }
        require(issuer.startsWith("https://")) { "issuer must be HTTPS" }
    }

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

    enum class Presentation { MODAL, FULLSCREEN, EMBEDDED }

    data class Branding(
        val logoUrl: String?,
        val primaryColor: String?,
        val appName: String?,
        val appDomain: String?,
    )

    internal val scopeString: String get() = scopes.joinToString(" ")
}
