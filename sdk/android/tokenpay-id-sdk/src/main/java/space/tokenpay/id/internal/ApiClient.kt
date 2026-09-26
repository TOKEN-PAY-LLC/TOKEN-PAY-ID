package space.tokenpay.id.internal

import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.*
import okhttp3.CertificatePinner
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import space.tokenpay.id.BuildConfig
import space.tokenpay.id.DeviceFlowSession
import space.tokenpay.id.TpidError
import space.tokenpay.id.TpidResult
import space.tokenpay.id.TpidUser
import java.io.IOException
import java.net.SocketTimeoutException
import java.net.UnknownHostException
import java.net.URLEncoder
import java.util.UUID
import java.util.concurrent.TimeUnit
import javax.net.ssl.SSLException

/**
 * Single thin HTTP client wrapping OkHttp, with optional TLS pinning and uniform error mapping.
 */
internal class ApiClient(
    private val issuer: String,
    private val pinTls: Boolean,
    private val storage: SecureStorage,
) {
    private val json = Json { ignoreUnknownKeys = true; isLenient = true; encodeDefaults = false }

    @Volatile
    private var activePins: List<String> = validPins(initialPins())

    @Volatile
    private var client: OkHttpClient = buildClient(activePins)

    fun hasActivePins(): Boolean = pinTls && activePins.isNotEmpty()

    private fun validPins(pins: List<String>): List<String> = pins.filter { pin ->
        pin.matches(Regex("^[A-Za-z0-9+/]{43}=$")) &&
        runCatching { android.util.Base64.decode(pin, android.util.Base64.DEFAULT).size == 32 }
            .getOrDefault(false)
    }.distinct()

    private fun initialPins(): List<String> = storage.getString(SecureStorage.KEY_TLS_PINS)
        ?.let { runCatching { json.decodeFromString<List<String>>(it) }.getOrNull() } ?: emptyList()

    private fun buildClient(pins: List<String>): OkHttpClient {
        val b = OkHttpClient.Builder()
            .connectTimeout(15, TimeUnit.SECONDS)
            .callTimeout(30, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .retryOnConnectionFailure(false)
        if (pinTls && pins.isNotEmpty()) {
            val pinner = CertificatePinner.Builder().apply {
                val host = issuer.substringAfter("https://").substringBefore("/")
                pins.forEach { add(host, "sha256/$it") }
            }.build()
            b.certificatePinner(pinner)
        }
        return b.build()
    }

    /**
     * Called by [SdkConfigLoader] after fetching fresh SPKI pins.
     */
    fun refreshPins(pins: List<String>) {
        val usable = validPins(pins)
        val arr = buildJsonArray { usable.forEach { add(it) } }
        storage.putString(SecureStorage.KEY_TLS_PINS, arr.toString())
        storage.putLong(SecureStorage.KEY_TLS_PINS_FETCHED, System.currentTimeMillis())
        activePins = usable
        client = buildClient(usable)
    }

    // -------------------------------------------------------------- helpers

    private fun Request.Builder.userAgent() = header(
        "User-Agent",
        "TokenPayID-Android-SDK/${BuildConfig.TPID_SDK_VERSION} (Android ${android.os.Build.VERSION.RELEASE})"
    )

    private fun Request.Builder.sdkHeaders() = this
        .userAgent()
        .header("Accept", "application/json")
        .header("X-TPID-SDK", "android:${BuildConfig.TPID_SDK_VERSION}")
        .header("X-TPID-Request-ID", UUID.randomUUID().toString())

    private fun url(path: String) = "${issuer.trimEnd('/')}${if (path.startsWith("/")) path else "/$path"}"

    private suspend fun execute(req: Request): Response = withContext(Dispatchers.IO) {
        try {
            client.newCall(req).execute()
        } catch (e: javax.net.ssl.SSLPeerUnverifiedException) {
            // Pin mismatch → clear tokens defensively and surface phishingDetected
            storage.clearTokens()
            throw TpidError.PhishingDetected(req.url.host)
        } catch (e: SocketTimeoutException) {
            throw TpidError.Timeout
        } catch (e: UnknownHostException) {
            throw TpidError.NoNetwork
        } catch (e: SSLException) {
            throw TpidError.TlsFailure(e.message)
        } catch (e: IOException) {
            throw TpidError.ServerUnavailable(e.message)
        }
    }

    private fun Response.bodyString(): String = use { it.body?.string().orEmpty() }

    private fun mapHttpError(resp: Response, body: String): TpidError {
        val code = resp.code
        val errObj = runCatching { json.parseToJsonElement(body).jsonObject }.getOrNull()
        val err = errObj?.get("error")?.jsonPrimitive?.content
        val msg = errObj?.get("error_description")?.jsonPrimitive?.content
            ?: errObj?.get("message")?.jsonPrimitive?.content

        return when {
            code == 401 || err == "invalid_grant" || err == "invalid_credentials" ->
                TpidError.InvalidCredentials(msg)
            code == 403 && err == "email_not_verified" -> TpidError.EmailNotVerified
            code == 423 || err == "account_locked" ->
                TpidError.AccountLocked(errObj?.get("locked_until")?.jsonPrimitive?.contentOrNull)
            code == 428 || err == "totp_required" -> {
                val methods = errObj?.get("methods")?.jsonArray?.map { it.jsonPrimitive.content } ?: listOf("totp")
                TpidError.TwoFactorRequired(methods)
            }
            code == 429 -> {
                val retry = resp.header("Retry-After")?.toIntOrNull()
                    ?: errObj?.get("retry_after")?.jsonPrimitive?.intOrNull
                    ?: 60
                TpidError.RateLimited(retry)
            }
            code in 500..599 -> TpidError.ServerUnavailable(msg ?: resp.message)
            err != null -> TpidError.OAuthError(err, msg)
            else -> TpidError.ServerError(code, msg ?: resp.message)
        }
    }

    // -------------------------------------------------------------- endpoints

    /** GET /api/v1/sdk/config[?client_id=...] */
    suspend fun fetchSdkConfig(clientId: String?): JsonObject {
        val u = url("/api/v1/sdk/config") + (clientId?.let { "?client_id=${URLEncoder.encode(it, "UTF-8")}" } ?: "")
        val resp = execute(Request.Builder().url(u).get().sdkHeaders().build())
        val body = resp.bodyString()
        if (!resp.isSuccessful) throw mapHttpError(resp, body)
        return json.parseToJsonElement(body).jsonObject
    }

    /** GET /api/v1/sdk/tls-pins */
    suspend fun fetchTlsPins(): List<String> {
        val resp = execute(Request.Builder().url(url("/api/v1/sdk/tls-pins")).get().sdkHeaders().build())
        val body = resp.bodyString()
        if (!resp.isSuccessful) throw mapHttpError(resp, body)
        return json.parseToJsonElement(body).jsonObject["pins"]?.jsonArray
            ?.mapNotNull { it.jsonPrimitive.contentOrNull } ?: emptyList()
    }

    /** POST /api/v1/auth/account-check { email, client_id } */
    @Serializable
    data class AccountCheckResponse(
        val exists: Boolean,
        val methods: List<String> = emptyList(),
        val suggestedNextStep: String = "password",
        val hasPasskey: Boolean = false,
        val has2fa: Boolean = false,
    )

    suspend fun accountCheck(email: String, clientId: String): AccountCheckResponse {
        val payload = buildJsonObject {
            put("email", email)
            put("client_id", clientId)
        }
        val resp = execute(
            Request.Builder()
                .url(url("/api/v1/auth/account-check"))
                .post(payload.toString().toRequestBody("application/json".toMediaType()))
                .sdkHeaders()
                .build()
        )
        val body = resp.bodyString()
        if (!resp.isSuccessful) throw mapHttpError(resp, body)
        val o = json.parseToJsonElement(body).jsonObject
        return AccountCheckResponse(
            exists = o["exists"]?.jsonPrimitive?.booleanOrNull ?: false,
            methods = o["methods"]?.jsonArray?.mapNotNull { it.jsonPrimitive.contentOrNull } ?: emptyList(),
            suggestedNextStep = o["suggested_next_step"]?.jsonPrimitive?.contentOrNull ?: "password",
            hasPasskey = o["has_passkey"]?.jsonPrimitive?.booleanOrNull ?: false,
            has2fa = o["has_2fa"]?.jsonPrimitive?.booleanOrNull ?: false,
        )
    }

    /**
     * Result of a single `/auth/login` call. The backend enforces a
     * mandatory e-mail-code second factor on every password login and may
     * additionally demand a TOTP — the call therefore returns an ADT instead
     * of a plain token, so the widget can branch on what to ask next.
     */
    sealed class LoginOutcome {
        /** Server sent a fresh 6-digit code to the user's mailbox. */
        data class RequiresEmailCode(val requires2FA: Boolean) : LoginOutcome()
        /** Password + e-mail code accepted, still need a TOTP / push approval. */
        data class RequiresTwoFactor(val emailCodeVerified: Boolean) : LoginOutcome()
        /** Full token pair — login is done. */
        data class Success(val success: TpidResult.Success) : LoginOutcome()
    }

    /**
     * POST /api/v1/auth/login — native password auth.
     *
     * The SDK used to treat this as an OAuth "authorization code" endpoint
     * and try to exchange the returned `code` via [exchangeCode]. The real
     * backend never had a code-flow here: on success it returns the full
     * `{accessToken, refreshToken, user, session_id}` payload directly, and
     * it ALSO enforces a mandatory e-mail-code second factor — so the first
     * call with just `{email, password}` replies with
     * `{requires_email_code: true}` and the caller is expected to retry the
     * same endpoint with `email_code` filled in.
     */
    suspend fun login(
        email: String,
        password: String,
        clientId: String,
        emailCode: String? = null,
        twoFactorCode: String? = null,
        lang: String? = null,
    ): LoginOutcome {
        val payload = buildJsonObject {
            put("email", email)
            put("password", password)
            put("client_id", clientId)
            if (!emailCode.isNullOrEmpty()) put("email_code", emailCode)
            if (!twoFactorCode.isNullOrEmpty()) put("two_factor_code", twoFactorCode)
            if (!lang.isNullOrEmpty()) put("lang", lang)
        }
        val resp = execute(
            Request.Builder()
                .url(url("/api/v1/auth/login"))
                .post(payload.toString().toRequestBody("application/json".toMediaType()))
                .sdkHeaders()
                .build()
        )
        val body = resp.bodyString()
        if (!resp.isSuccessful) throw mapHttpError(resp, body)
        val o = json.parseToJsonElement(body).jsonObject
        if (o["requires_email_code"]?.jsonPrimitive?.booleanOrNull == true) {
            return LoginOutcome.RequiresEmailCode(
                requires2FA = o["requires_2fa"]?.jsonPrimitive?.booleanOrNull ?: false
            )
        }
        if (o["requires_2fa"]?.jsonPrimitive?.booleanOrNull == true) {
            return LoginOutcome.RequiresTwoFactor(
                emailCodeVerified = o["email_code_verified"]?.jsonPrimitive?.booleanOrNull ?: false
            )
        }
        return LoginOutcome.Success(parseTokenResponse(o))
    }

    /**
     * POST /api/v1/auth/send-code — send a 6-digit one-time code to [email].
     *
     * The server rejects requests without a `type` field (`missing_fields: email
     * and type required`). Callers pass `"login"` for existing accounts and
     * `"register"` for fresh sign-ups so the server can route the email
     * template and throttle correctly. An earlier build of this SDK posted to
     * `/auth/magic-link/request` — an endpoint that never shipped — and every
     * code request returned `404 Endpoint not found`.
     */
    suspend fun requestEmailCode(email: String, clientId: String, type: String = "login") {
        val payload = buildJsonObject {
            put("email", email)
            put("client_id", clientId)
            put("type", type)
        }
        val resp = execute(
            Request.Builder()
                .url(url("/api/v1/auth/send-code"))
                .post(payload.toString().toRequestBody("application/json".toMediaType()))
                .sdkHeaders()
                .build()
        )
        val body = resp.bodyString()
        if (!resp.isSuccessful) throw mapHttpError(resp, body)
    }

    suspend fun quickLogin(
        email: String,
        emailCode: String,
        clientId: String,
        twoFactorCode: String? = null,
        lang: String? = null,
    ): LoginOutcome {
        val payload = buildJsonObject {
            put("email", email)
            put("email_code", emailCode)
            put("client_id", clientId)
            if (!twoFactorCode.isNullOrEmpty()) put("two_factor_code", twoFactorCode)
            if (!lang.isNullOrEmpty()) put("lang", lang)
        }
        val resp = execute(
            Request.Builder()
                .url(url("/api/v1/auth/quick-login"))
                .post(payload.toString().toRequestBody("application/json".toMediaType()))
                .sdkHeaders()
                .build()
        )
        val body = resp.bodyString()
        if (!resp.isSuccessful) throw mapHttpError(resp, body)
        val o = json.parseToJsonElement(body).jsonObject
        if (o["requires_2fa"]?.jsonPrimitive?.booleanOrNull == true) {
            return LoginOutcome.RequiresTwoFactor(emailCodeVerified = true)
        }
        return LoginOutcome.Success(parseTokenResponse(o))
    }

    /**
     * POST /api/v1/auth/verify — exchange the 6-digit code for an OAuth
     * authorization code. Replaces the pre-2.5.0-pre.3 `/auth/magic-link/verify`
     * call which returned 404.
     */
    suspend fun verifyEmailCode(
        email: String,
        code: String,
        clientId: String,
        redirectUri: String,
        scope: String,
        codeChallenge: String,
        state: String,
        nonce: String?,
    ): String {
        val payload = buildJsonObject {
            put("email", email)
            put("code", code)
            put("client_id", clientId)
            put("redirect_uri", redirectUri)
            put("scope", scope)
            put("code_challenge", codeChallenge)
            put("code_challenge_method", "S256")
            put("state", state)
            if (nonce != null) put("nonce", nonce)
        }
        val resp = execute(
            Request.Builder()
                .url(url("/api/v1/auth/verify"))
                .post(payload.toString().toRequestBody("application/json".toMediaType()))
                .sdkHeaders()
                .build()
        )
        val body = resp.bodyString()
        if (!resp.isSuccessful) throw mapHttpError(resp, body)
        val o = json.parseToJsonElement(body).jsonObject
        return o["code"]?.jsonPrimitive?.contentOrNull
            ?: throw TpidError.OAuthError("no_code", "Verify response missing code")
    }

    /**
     * POST `/api/v1/auth/register` — finish sign-up for a brand-new e-mail.
     *
     * Prerequisite: caller has already triggered [requestEmailCode] with
     * `type = "register"`, so the server has delivered a 6-digit code.
     *
     * Unlike OAuth `authorization_code` exchange, this endpoint returns the
     * final access / refresh token pair directly — the sign-up flow therefore
     * bypasses [exchangeCode] and completes in a single call.
     */
    suspend fun register(
        email: String,
        password: String,
        username: String,
        emailCode: String,
        clientId: String,
        lang: String?,
    ): TpidResult.Success {
        val payload = buildJsonObject {
            put("email", email)
            put("password", password)
            put("username", username)
            put("email_code", emailCode)
            put("client_id", clientId)
            put("lang", (lang ?: "").take(2).ifBlank { "en" })
        }
        val resp = execute(
            Request.Builder()
                .url(url("/api/v1/auth/register"))
                .post(payload.toString().toRequestBody("application/json".toMediaType()))
                .sdkHeaders()
                .build()
        )
        val body = resp.bodyString()
        if (!resp.isSuccessful) throw mapHttpError(resp, body)
        return parseTokenResponse(json.parseToJsonElement(body).jsonObject)
    }

    /**
     * POST /api/v1/oauth/token — exchange the authorization code for tokens.
     */
    suspend fun exchangeCode(
        code: String,
        clientId: String,
        redirectUri: String,
        codeVerifier: String,
    ): TpidResult.Success {
        val payload = buildJsonObject {
            put("grant_type", "authorization_code")
            put("code", code)
            put("client_id", clientId)
            put("redirect_uri", redirectUri)
            put("code_verifier", codeVerifier)
        }
        val resp = execute(
            Request.Builder()
                .url(url("/api/v1/oauth/token"))
                .post(payload.toString().toRequestBody("application/json".toMediaType()))
                .sdkHeaders()
                .build()
        )
        val body = resp.bodyString()
        if (!resp.isSuccessful) throw mapHttpError(resp, body)
        return parseTokenResponse(json.parseToJsonElement(body).jsonObject)
    }

    /** POST /api/v1/oauth/token with grant_type=refresh_token. */
    suspend fun refreshToken(refreshToken: String, clientId: String): SecureStorage.Tokens {
        val payload = buildJsonObject {
            put("grant_type", "refresh_token")
            put("refresh_token", refreshToken)
            put("client_id", clientId)
        }
        val resp = execute(
            Request.Builder()
                .url(url("/api/v1/oauth/token"))
                .post(payload.toString().toRequestBody("application/json".toMediaType()))
                .sdkHeaders()
                .build()
        )
        val body = resp.bodyString()
        if (!resp.isSuccessful) throw mapHttpError(resp, body)
        val success = parseTokenResponse(json.parseToJsonElement(body).jsonObject)
        return SecureStorage.Tokens(
            accessToken = success.accessToken,
            refreshToken = success.refreshToken,
            idToken = success.idToken,
            expiresAtMs = System.currentTimeMillis() + success.expiresIn * 1000L,
            scope = success.scope,
            userDto = SecureStorage.Tokens.TpidUserDto.from(success.user),
        )
    }

    /** POST /api/v1/oauth/revoke — revoke a token. */
    suspend fun revokeToken(token: String, clientId: String) {
        val payload = buildJsonObject {
            put("token", token)
            put("client_id", clientId)
        }
        runCatching {
            execute(
                Request.Builder()
                    .url(url("/api/v1/oauth/revoke"))
                    .post(payload.toString().toRequestBody("application/json".toMediaType()))
                    .sdkHeaders()
                    .build()
            ).close()
        }
    }

    // ---------------------------------------------------------- QR login

    data class QrInit(val sessionId: String, val qrUrl: String, val ttlSeconds: Int)

    /** POST /api/v1/auth/qr/login-init → { sessionId, qrUrl, ttl } */
    suspend fun qrLoginInit(clientId: String, sdk: String = "android"): QrInit {
        val payload = buildJsonObject {
            put("client_id", clientId)
            put("sdk", sdk)
        }
        val resp = execute(
            Request.Builder()
                .url(url("/api/v1/auth/qr/login-init"))
                .post(payload.toString().toRequestBody("application/json".toMediaType()))
                .sdkHeaders()
                .build()
        )
        val body = resp.bodyString()
        if (!resp.isSuccessful) throw mapHttpError(resp, body)
        val o = json.parseToJsonElement(body).jsonObject
        val sid = o["sessionId"]?.jsonPrimitive?.contentOrNull
            ?: o["session_id"]?.jsonPrimitive?.contentOrNull
            ?: throw TpidError.OAuthError("missing_sid", "qr-init missing sessionId")
        val qrUrl = o["qrUrl"]?.jsonPrimitive?.contentOrNull
            ?: o["qr_url"]?.jsonPrimitive?.contentOrNull
            ?: "https://tokenpay.space/qr-login?sid=$sid"
        val ttl = o["ttl"]?.jsonPrimitive?.intOrNull ?: 300
        return QrInit(sid, qrUrl, ttl)
    }

    sealed class QrPollResult {
        data object Pending : QrPollResult()
        data object Expired : QrPollResult()
        data class Approved(val success: TpidResult.Success) : QrPollResult()
    }

    /** GET /api/v1/auth/qr/login-poll/:sessionId */
    suspend fun qrLoginPoll(sessionId: String): QrPollResult {
        val resp = execute(
            Request.Builder()
                .url(url("/api/v1/auth/qr/login-poll/$sessionId"))
                .get()
                .sdkHeaders()
                .build()
        )
        val body = resp.bodyString()
        if (!resp.isSuccessful) throw mapHttpError(resp, body)
        val o = json.parseToJsonElement(body).jsonObject
        return when (o["status"]?.jsonPrimitive?.contentOrNull) {
            "approved" -> QrPollResult.Approved(parseTokenResponse(o))
            "expired" -> QrPollResult.Expired
            else -> QrPollResult.Pending
        }
    }

    // --------------------------------------------------------- device flow

    data class DeviceAuthResponse(
        val deviceCode: String,
        val userCode: String,
        val verificationUri: String,
        val verificationUriComplete: String,
        val expiresIn: Int,
        val interval: Int,
    )

    suspend fun deviceAuthorize(clientId: String, scope: String): DeviceAuthResponse {
        val payload = buildJsonObject {
            put("client_id", clientId)
            put("scope", scope)
        }
        val resp = execute(
            Request.Builder()
                .url(url("/api/v1/oauth/device"))
                .post(payload.toString().toRequestBody("application/json".toMediaType()))
                .sdkHeaders()
                .build()
        )
        val body = resp.bodyString()
        if (!resp.isSuccessful) throw mapHttpError(resp, body)
        val o = json.parseToJsonElement(body).jsonObject
        return DeviceAuthResponse(
            deviceCode = o["device_code"]!!.jsonPrimitive.content,
            userCode = o["user_code"]!!.jsonPrimitive.content,
            verificationUri = o["verification_uri"]!!.jsonPrimitive.content,
            verificationUriComplete = o["verification_uri_complete"]?.jsonPrimitive?.content
                ?: o["verification_uri"]!!.jsonPrimitive.content,
            expiresIn = o["expires_in"]!!.jsonPrimitive.int,
            interval = o["interval"]?.jsonPrimitive?.int ?: 5,
        )
    }

    /**
     * Poll the /oauth/device/token endpoint until success / error / timeout.
     * Returns [TpidResult.Success] on approval or [TpidResult.Failure] otherwise.
     */
    suspend fun pollDeviceToken(session: DeviceFlowSession, clientId: String): TpidResult {
        val deadline = System.currentTimeMillis() + session.expiresIn * 1000L
        var interval = session.interval.coerceAtLeast(1)
        while (System.currentTimeMillis() < deadline) {
            delay(interval * 1000L)
            val payload = buildJsonObject {
                put("grant_type", "urn:ietf:params:oauth:grant-type:device_code")
                put("device_code", session.deviceCode)
                put("client_id", clientId)
            }
            val resp = execute(
                Request.Builder()
                    .url(url("/api/v1/oauth/device/token"))
                    .post(payload.toString().toRequestBody("application/json".toMediaType()))
                    .sdkHeaders()
                    .build()
            )
            val body = resp.bodyString()
            if (resp.isSuccessful) {
                return parseTokenResponse(json.parseToJsonElement(body).jsonObject)
            }
            val err = runCatching { json.parseToJsonElement(body).jsonObject["error"]?.jsonPrimitive?.content }
                .getOrNull()
            when (err) {
                "authorization_pending" -> continue
                "slow_down" -> interval += 5
                "expired_token" -> return TpidResult.Failure(TpidError.OAuthError(err, "Code expired"))
                "access_denied" -> return TpidResult.Failure(TpidError.OAuthError(err, "User denied"))
                else -> return TpidResult.Failure(mapHttpError(resp, body))
            }
        }
        return TpidResult.Failure(TpidError.OAuthError("expired_token", "Device flow timed out"))
    }

    // ------------------------------------------------------------- telemetry

    suspend fun sendTelemetry(payload: JsonObject) {
        runCatching {
            execute(
                Request.Builder()
                    .url(url("/api/v1/telemetry/event"))
                    .post(payload.toString().toRequestBody("application/json".toMediaType()))
                    .sdkHeaders()
                    .build()
            ).close()
        }.onFailure { Log.d("TpidTelemetry", "send failed: ${it.message}") }
    }

    // ---------------------------------------------------- token parse helper

    private fun parseTokenResponse(o: JsonObject): TpidResult.Success {
        val accessToken = o["access_token"]?.jsonPrimitive?.contentOrNull
            ?: o["accessToken"]?.jsonPrimitive?.contentOrNull
            ?: throw TpidError.OAuthError("no_access_token", "Token response missing access_token")
        val refreshToken = o["refresh_token"]?.jsonPrimitive?.contentOrNull
            ?: o["refreshToken"]?.jsonPrimitive?.contentOrNull
        val idToken = o["id_token"]?.jsonPrimitive?.contentOrNull
            ?: o["idToken"]?.jsonPrimitive?.contentOrNull
        val expiresIn = o["expires_in"]?.jsonPrimitive?.longOrNull
            ?: o["expiresIn"]?.jsonPrimitive?.longOrNull ?: 3600L
        val scope = o["scope"]?.jsonPrimitive?.contentOrNull ?: ""
        val tokenType = o["token_type"]?.jsonPrimitive?.contentOrNull
            ?: o["tokenType"]?.jsonPrimitive?.contentOrNull ?: "Bearer"
        val userObj = o["user"]?.jsonObject
        val user = if (userObj != null) parseUser(userObj) else TpidUser(
            id = "", email = "", emailVerified = false,
            name = null, avatarUrl = null, locale = null,
            has2fa = false, hasPasskey = false, createdAt = "",
        )
        return TpidResult.Success(
            accessToken = accessToken,
            refreshToken = refreshToken,
            idToken = idToken,
            expiresIn = expiresIn,
            tokenType = tokenType,
            scope = scope,
            user = user,
        )
    }

    private fun parseUser(o: JsonObject): TpidUser = TpidUser(
        id = o["id"]?.jsonPrimitive?.contentOrNull ?: "",
        email = o["email"]?.jsonPrimitive?.contentOrNull ?: "",
        emailVerified = o["email_verified"]?.jsonPrimitive?.booleanOrNull ?: false,
        name = o["name"]?.jsonPrimitive?.contentOrNull,
        avatarUrl = o["avatar_url"]?.jsonPrimitive?.contentOrNull,
        locale = o["locale"]?.jsonPrimitive?.contentOrNull,
        has2fa = o["has_2fa"]?.jsonPrimitive?.booleanOrNull ?: false,
        hasPasskey = o["has_passkey"]?.jsonPrimitive?.booleanOrNull ?: false,
        createdAt = o["created_at"]?.jsonPrimitive?.contentOrNull ?: "",
    )
}
