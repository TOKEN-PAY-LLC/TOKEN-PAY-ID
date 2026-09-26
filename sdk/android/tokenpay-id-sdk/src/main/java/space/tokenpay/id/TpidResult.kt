package space.tokenpay.id

/**
 * Result of a widget session.
 */
sealed class TpidResult {
    /** User authenticated successfully. */
    data class Success(
        val accessToken: String,
        val refreshToken: String?,
        val idToken: String?,
        val expiresIn: Long,
        val tokenType: String = "Bearer",
        val scope: String,
        val user: TpidUser,
    ) : TpidResult()

    /** User dismissed the widget without completing auth. */
    data object Cancelled : TpidResult()

    /** Widget finished with an error. Inspect [error] for the reason. */
    data class Failure(val error: TpidError) : TpidResult()
}

/**
 * Authenticated user profile returned alongside tokens.
 */
data class TpidUser(
    val id: String,
    val email: String,
    val emailVerified: Boolean,
    val name: String?,
    val avatarUrl: String?,
    val locale: String?,
    val has2fa: Boolean,
    val hasPasskey: Boolean,
    val createdAt: String,
)
