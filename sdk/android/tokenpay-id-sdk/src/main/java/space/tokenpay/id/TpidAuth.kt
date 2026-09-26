package space.tokenpay.id

import android.content.Context
import android.util.Log
import space.tokenpay.id.internal.ApiClient
import space.tokenpay.id.internal.SecureStorage
import space.tokenpay.id.internal.SdkConfigLoader
import space.tokenpay.id.internal.Telemetry
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import java.util.concurrent.atomic.AtomicReference

/**
 * Entry point for the TOKEN PAY ID SDK.
 *
 * Call [initialize] once from your [android.app.Application.onCreate], then use
 * [TpidLoginButton] in Compose or [TpidWidget.present] programmatically.
 */
object TpidAuth {

    private const val TAG = "TpidAuth"
    private val stateRef = AtomicReference<State?>(null)
    internal val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)

    internal data class State(
        val appContext: Context,
        val config: TpidConfig,
        val api: ApiClient,
        val storage: SecureStorage,
        val telemetry: Telemetry,
        val sdkConfigLoader: SdkConfigLoader,
    )

    /**
     * Initialize the SDK. Safe to call multiple times — subsequent calls replace config.
     */
    @JvmStatic
    fun initialize(context: Context, config: TpidConfig) {
        val appCtx = context.applicationContext
        val storage = SecureStorage(appCtx, config.clientId)
        val api = ApiClient(
            issuer = config.issuer,
            pinTls = config.pinTlsCertificates,
            storage = storage,
        )
        val telemetry = Telemetry(
            api = api,
            clientId = config.clientId,
            enabled = config.enableTelemetry,
        )
        val loader = SdkConfigLoader(api = api, storage = storage)
        stateRef.set(State(appCtx, config, api, storage, telemetry, loader))
        Log.i(TAG, "TOKEN PAY ID SDK initialized (v${BuildConfig.TPID_SDK_VERSION}) for client=${config.clientId.take(15)}…")

        // Fire-and-forget: prefetch SDK config (branding, TLS pins) in background.
        scope.launch(Dispatchers.IO) { runCatching { loader.refreshConfig(config.clientId) } }
    }

    internal fun requireState(): State = stateRef.get()
        ?: throw TpidError.ConfigurationError("TpidAuth.initialize() not called. Call it from Application.onCreate().")

    /** Whether the user has a valid (non-expired) stored session. */
    @JvmStatic
    fun hasValidSession(): Boolean {
        val s = stateRef.get() ?: return false
        val tok = s.storage.readTokens() ?: return false
        return tok.expiresAtMs > System.currentTimeMillis() + 30_000
    }

    /** Returns the cached access token if valid, otherwise attempts refresh. Returns null if not signed in. */
    @JvmStatic
    suspend fun getAccessToken(): String? {
        val s = stateRef.get() ?: return null
        val tok = s.storage.readTokens() ?: return null
        if (tok.expiresAtMs > System.currentTimeMillis() + 30_000) return tok.accessToken
        // Try refresh
        val rt = tok.refreshToken ?: return null
        val refreshed = runCatching { s.api.refreshToken(rt, s.config.clientId) }.getOrNull()
            ?: return null
        s.storage.writeTokens(refreshed)
        return refreshed.accessToken
    }

    /**
     * Sign out. Clears local tokens and optionally revokes on the server.
     */
    @JvmStatic
    fun signOut(revokeOnServer: Boolean = true) {
        val s = stateRef.get() ?: return
        val tokens = s.storage.readTokens()
        s.storage.clearTokens()
        if (revokeOnServer && tokens?.refreshToken != null) {
            scope.launch(Dispatchers.IO) {
                runCatching { s.api.revokeToken(tokens.refreshToken, s.config.clientId) }
            }
        }
        s.telemetry.track("widget.sign_out")
    }

    /**
     * Start a Device Flow (RFC 8628). Returns an object containing the user code
     * and the verification URL to display on-screen (e.g. on Android TV).
     */
    @JvmStatic
    suspend fun startDeviceFlow(): DeviceFlowSession {
        val s = requireState()
        val resp = s.api.deviceAuthorize(s.config.clientId, s.config.scopeString)
        return DeviceFlowSession(
            deviceCode = resp.deviceCode,
            userCode = resp.userCode,
            verificationUri = resp.verificationUri,
            verificationUriComplete = resp.verificationUriComplete,
            expiresIn = resp.expiresIn,
            interval = resp.interval,
        )
    }

    /**
     * Poll the Device Flow token endpoint until authorization is approved, denied, or expires.
     * Suspends for up to [DeviceFlowSession.expiresIn] seconds.
     */
    @JvmStatic
    suspend fun pollDeviceFlow(session: DeviceFlowSession): TpidResult {
        val s = requireState()
        return s.api.pollDeviceToken(session, s.config.clientId).also { r ->
            if (r is TpidResult.Success) {
                s.storage.writeTokens(
                    SecureStorage.Tokens(
                        accessToken = r.accessToken,
                        refreshToken = r.refreshToken,
                        idToken = r.idToken,
                        expiresAtMs = System.currentTimeMillis() + r.expiresIn * 1000L,
                        scope = r.scope,
                    )
                )
            }
        }
    }

    /**
     * Return the currently-stored user profile if available (reads the last tokens' stored user).
     */
    @JvmStatic
    fun currentUser(): TpidUser? = stateRef.get()?.storage?.readTokens()?.user
}

data class DeviceFlowSession(
    val deviceCode: String,
    val userCode: String,
    val verificationUri: String,
    val verificationUriComplete: String,
    val expiresIn: Int,
    val interval: Int,
)
