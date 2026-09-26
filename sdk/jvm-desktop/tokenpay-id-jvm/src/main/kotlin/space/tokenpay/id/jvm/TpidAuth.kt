package space.tokenpay.id.jvm

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import space.tokenpay.id.jvm.internal.ApiClient
import space.tokenpay.id.jvm.internal.SecureStorage

/**
 * Entry point for the TOKEN PAY ID JVM Desktop SDK.
 *
 * Call [initialize] once at application startup. All UI composables read from
 * the initialized state; calling them before [initialize] throws
 * [TpidError.ConfigurationError].
 */
object TpidAuth {

    internal data class State(
        val config: TpidConfig,
        val api: ApiClient,
        val storage: SecureStorage,
        val scope: CoroutineScope,
    )

    @Volatile
    private var state: State? = null
    private val lock = Any()

    fun initialize(config: TpidConfig) {
        synchronized(lock) {
            val storage = SecureStorage(config.clientId)
            val api = ApiClient(config.issuer, config.pinTLSCertificates, storage)
            state = State(config, api, storage, CoroutineScope(SupervisorJob() + Dispatchers.IO))
        }
    }

    internal fun requireState(): State =
        state ?: throw TpidError.ConfigurationError("TpidAuth.initialize(config) must be called before using the SDK")

    /** `true` if a cached, non-expired session exists. */
    val hasValidSession: Boolean
        get() {
            val s = state ?: return false
            val session = s.storage.readSession() ?: return false
            return session.isValid
        }

    /** Current user from cached session, or `null` if not signed in. */
    fun currentUser(): TpidUser? = state?.storage?.readSession()?.user

    /** Return a valid access token, refreshing via refresh_token if needed. */
    suspend fun getAccessToken(): String? {
        val s = state ?: return null
        val session = s.storage.readSession() ?: return null
        if (session.isValid) return session.accessToken
        val rt = session.refreshToken ?: return null
        return runCatching {
            val refreshed = s.api.refreshToken(rt, s.config.clientId)
            val merged = if (refreshed.user.id.isEmpty()) refreshed.copy(user = session.user) else refreshed
            s.storage.writeSession(merged)
            merged.accessToken
        }.getOrNull()
    }

    /** Sign the user out. `revokeOnServer=true` best-effort revokes the refresh token server-side. */
    fun signOut(revokeOnServer: Boolean = true) {
        val s = state ?: return
        val prev = s.storage.readSession()
        s.storage.clearSession()
        if (revokeOnServer && prev?.refreshToken != null) {
            s.scope.launch { s.api.revokeToken(prev.refreshToken, s.config.clientId) }
        }
    }

    /** Device Flow (RFC 8628) — for headless and TV/console apps. */
    suspend fun startDeviceFlow(): TpidDeviceFlowSession {
        val s = requireState()
        return s.api.deviceAuthorize(s.config.clientId, s.config.scopeString)
    }

    suspend fun pollDeviceFlow(session: TpidDeviceFlowSession): TpidSession {
        val s = requireState()
        val result = s.api.pollDeviceToken(session, s.config.clientId)
        s.storage.writeSession(result)
        return result
    }
}
