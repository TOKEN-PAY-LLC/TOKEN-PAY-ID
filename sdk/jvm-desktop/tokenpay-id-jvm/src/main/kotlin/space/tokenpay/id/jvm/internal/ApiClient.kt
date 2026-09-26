package space.tokenpay.id.jvm.internal

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import okhttp3.CertificatePinner
import okhttp3.Headers
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import space.tokenpay.id.jvm.TpidConfig
import space.tokenpay.id.jvm.TpidDeviceFlowSession
import space.tokenpay.id.jvm.TpidError
import space.tokenpay.id.jvm.TpidSession
import space.tokenpay.id.jvm.TpidUser
import java.io.IOException
import java.net.URI
import java.net.URLEncoder
import java.time.Instant
import java.util.concurrent.TimeUnit
import javax.net.ssl.SSLPeerUnverifiedException

internal class ApiClient(
    private val issuer: URI,
    private val pinTLS: Boolean,
    private val storage: SecureStorage,
) {
    private val json = Json { ignoreUnknownKeys = true }
    private val jsonMime = "application/json".toMediaType()
    @Volatile private var activePins: List<String> = emptyList()
    @Volatile private var client: OkHttpClient = buildClient(issuer, activePins)

    fun hasActivePins(): Boolean = pinTLS && activePins.isNotEmpty()

    fun refreshPins(pins: List<String>) {
        val usable = pins.filter { pin ->
            pin.matches(Regex("^[A-Za-z0-9+/]{43}=$")) &&
                runCatching { java.util.Base64.getDecoder().decode(pin).size == 32 }.getOrDefault(false)
        }.distinct()
        activePins = usable
        client = buildClient(issuer, usable)
    }

    private fun buildClient(issuer: URI, pins: List<String>): OkHttpClient {
        val b = OkHttpClient.Builder()
            .connectTimeout(15, TimeUnit.SECONDS)
            .readTimeout(25, TimeUnit.SECONDS)
            .writeTimeout(15, TimeUnit.SECONDS)
            .followRedirects(false)
        if (pinTLS && pins.isNotEmpty()) {
            val host = issuer.host
            if (host != null) {
                val pinner = CertificatePinner.Builder().apply {
                    pins.forEach { add(host, "sha256/$it") }
                }.build()
                b.certificatePinner(pinner)
            }
        }
        return b.build()
    }

    // ---------- HTTP utils ----------

    private suspend fun execute(req: Request): Response = withContext(Dispatchers.IO) {
        try { client.newCall(req).execute() }
        catch (e: SSLPeerUnverifiedException) {
            throw TpidError.PhishingDetected(req.url.host)
        }
        catch (e: IOException) {
            throw if (e.message?.contains("timeout", true) == true) TpidError.Timeout else TpidError.NoNetwork
        }
    }

    private fun defaultHeaders(builder: Request.Builder): Request.Builder = builder
        .header("User-Agent", "${SdkBuildInfo.userAgent} (${System.getProperty("os.name")}; ${System.getProperty("os.version")})")
        .header("X-TPID-SDK", SdkBuildInfo.sdkHeader)
        .header("Accept", "application/json")

    private fun post(path: String, body: JsonObject): Request = defaultHeaders(
        Request.Builder().url(issuer.resolve(path).toString())
            .post(body.toString().toRequestBody(jsonMime))
    ).build()

    private fun postForm(path: String, form: Map<String, String>): Request = defaultHeaders(
        Request.Builder().url(issuer.resolve(path).toString())
            .post(RequestBody.create("application/x-www-form-urlencoded".toMediaType(),
                form.map { "${URLEncoder.encode(it.key, "UTF-8")}=${URLEncoder.encode(it.value, "UTF-8")}" }.joinToString("&")))
    ).build()

    private fun get(path: String): Request =
        defaultHeaders(Request.Builder().url(issuer.resolve(path).toString())).build()

    // ---------- Endpoints ----------

    data class AccountCheckResponse(
        val exists: Boolean,
        val hasPassword: Boolean,
        val hasPasskey: Boolean,
        val suggestedNextStep: String?,
    )

    suspend fun accountCheck(email: String, clientId: String): AccountCheckResponse {
        val req = post("/api/v1/auth/account-check", JsonObject(mapOf(
            "email" to JsonPrimitive(email),
            "client_id" to JsonPrimitive(clientId),
        )))
        execute(req).use { resp ->
            val body = resp.body?.string().orEmpty()
            if (!resp.isSuccessful) throw parseServerError(resp, body)
            val o = json.parseToJsonElement(body).jsonObject
            return AccountCheckResponse(
                exists = o["exists"]?.jsonPrimitive?.content?.toBoolean() ?: false,
                hasPassword = o["has_password"]?.jsonPrimitive?.content?.toBoolean() ?: false,
                hasPasskey = o["has_passkey"]?.jsonPrimitive?.content?.toBoolean() ?: false,
                suggestedNextStep = o["suggested_next_step"]?.jsonPrimitive?.content,
            )
        }
    }

    /**
     * Outcome of a single `POST /api/v1/auth/login` call. The backend runs
     * password login as a two- or three-step state machine (password →
     * e-mail code → optional TOTP), and this ADT captures what the server
     * is asking for next.
     */
    sealed class LoginOutcome {
        data class RequiresEmailCode(val requires2FA: Boolean) : LoginOutcome()
        data class RequiresTwoFactor(val emailCodeVerified: Boolean) : LoginOutcome()
        data class Success(val session: TpidSession) : LoginOutcome()
    }

    /**
     * Password login against the real backend. Older versions of the SDK
     * treated this as an OAuth "authorization code" endpoint and then
     * exchanged the returned `code` via [exchangeCode], but the real
     * server never had a code flow here — on success it returns
     * `{accessToken, refreshToken, user, session_id}` directly, and on
     * the first call without an `email_code` it replies with
     * `{requires_email_code: true}` after e-mailing a fresh 6-digit OTP.
     * The widget therefore calls this up to three times:
     *   1. {email, password}                                 → RequiresEmailCode
     *   2. {email, password, email_code}                     → Success or RequiresTwoFactor
     *   3. {email, password, email_code, two_factor_code}    → Success
     */
    suspend fun login(
        email: String,
        password: String,
        clientId: String,
        emailCode: String? = null,
        twoFactorCode: String? = null,
        lang: String? = null,
    ): LoginOutcome {
        val req = post("/api/v1/auth/login", JsonObject(buildMap {
            put("client_id", JsonPrimitive(clientId))
            put("email", JsonPrimitive(email))
            put("password", JsonPrimitive(password))
            if (!emailCode.isNullOrEmpty()) put("email_code", JsonPrimitive(emailCode))
            if (!twoFactorCode.isNullOrEmpty()) put("two_factor_code", JsonPrimitive(twoFactorCode))
            if (!lang.isNullOrEmpty()) put("lang", JsonPrimitive(lang))
        }))
        execute(req).use { resp ->
            val body = resp.body?.string().orEmpty()
            if (!resp.isSuccessful) throw parseServerError(resp, body)
            val o = json.parseToJsonElement(body).jsonObject
            val requiresEmailCode = o["requires_email_code"]?.jsonPrimitive?.content?.toBooleanStrictOrNull() ?: false
            if (requiresEmailCode) {
                val requires2FA = o["requires_2fa"]?.jsonPrimitive?.content?.toBooleanStrictOrNull() ?: false
                return LoginOutcome.RequiresEmailCode(requires2FA)
            }
            val requires2FA = o["requires_2fa"]?.jsonPrimitive?.content?.toBooleanStrictOrNull() ?: false
            if (requires2FA) {
                val emailCodeVerified = o["email_code_verified"]?.jsonPrimitive?.content?.toBooleanStrictOrNull() ?: false
                return LoginOutcome.RequiresTwoFactor(emailCodeVerified)
            }
            // Happy path: backend returned the final token pair under
            // camelCase keys alongside a `user` object.
            val accessToken = o["accessToken"]?.jsonPrimitive?.content
                ?: o["access_token"]?.jsonPrimitive?.content
                ?: throw TpidError.ServerError(resp.code, "login response missing accessToken")
            val refreshToken = o["refreshToken"]?.jsonPrimitive?.content
                ?: o["refresh_token"]?.jsonPrimitive?.content
            val idToken = o["idToken"]?.jsonPrimitive?.content ?: o["id_token"]?.jsonPrimitive?.content
            val expiresIn = o["expiresIn"]?.jsonPrimitive?.content?.toLongOrNull()
                ?: o["expires_in"]?.jsonPrimitive?.content?.toLongOrNull() ?: 3600L
            val tokenType = o["tokenType"]?.jsonPrimitive?.content
                ?: o["token_type"]?.jsonPrimitive?.content ?: "Bearer"
            val scope = o["scope"]?.jsonPrimitive?.content
            val userObj = o["user"]?.jsonObject
            val user: TpidUser = if (userObj != null) TpidUser(
                id = userObj["id"]?.jsonPrimitive?.content ?: "",
                email = userObj["email"]?.jsonPrimitive?.content ?: email,
                emailVerified = userObj["email_verified"]?.jsonPrimitive?.content?.toBooleanStrictOrNull()
                    ?: userObj["emailVerified"]?.jsonPrimitive?.content?.toBooleanStrictOrNull()
                    ?: false,
                name = userObj["name"]?.jsonPrimitive?.content,
                avatarUrl = userObj["avatar_url"]?.jsonPrimitive?.content ?: userObj["picture"]?.jsonPrimitive?.content,
                locale = userObj["locale"]?.jsonPrimitive?.content,
            ) else TpidUser(id = "unknown", email = email)
            return LoginOutcome.Success(
                TpidSession(accessToken, refreshToken, idToken,
                    Instant.now().plusSeconds(expiresIn), tokenType, scope, user)
            )
        }
    }

    suspend fun exchangeCode(code: String, verifier: String, config: TpidConfig): TpidSession {
        val req = postForm("/api/v1/oauth/token", mapOf(
            "grant_type" to "authorization_code",
            "code" to code,
            "redirect_uri" to config.redirectUri,
            "client_id" to config.clientId,
            "code_verifier" to verifier,
        ))
        execute(req).use { resp ->
            val body = resp.body?.string().orEmpty()
            if (!resp.isSuccessful) throw parseServerError(resp, body)
            val o = json.parseToJsonElement(body).jsonObject
            val accessToken = o["access_token"]?.jsonPrimitive?.content
                ?: throw TpidError.ServerError(resp.code, "no access_token")
            val refreshToken = o["refresh_token"]?.jsonPrimitive?.content
            val idToken = o["id_token"]?.jsonPrimitive?.content
            val expiresIn = o["expires_in"]?.jsonPrimitive?.content?.toLongOrNull() ?: 3600L
            val tokenType = o["token_type"]?.jsonPrimitive?.content ?: "Bearer"
            val scope = o["scope"]?.jsonPrimitive?.content

            // fetch userinfo
            val ui = get("/api/v1/oauth/userinfo").newBuilder().header("Authorization", "Bearer $accessToken").build()
            val user: TpidUser = execute(ui).use { u ->
                val ub = u.body?.string().orEmpty()
                if (!u.isSuccessful) TpidUser(id = "unknown", email = "")
                else {
                    val uo = json.parseToJsonElement(ub).jsonObject
                    TpidUser(
                        id = uo["sub"]?.jsonPrimitive?.content ?: "",
                        email = uo["email"]?.jsonPrimitive?.content ?: "",
                        emailVerified = uo["email_verified"]?.jsonPrimitive?.content?.toBoolean() ?: false,
                        name = uo["name"]?.jsonPrimitive?.content,
                        avatarUrl = uo["picture"]?.jsonPrimitive?.content,
                        locale = uo["locale"]?.jsonPrimitive?.content,
                    )
                }
            }
            return TpidSession(accessToken, refreshToken, idToken, Instant.now().plusSeconds(expiresIn), tokenType, scope, user)
        }
    }

    suspend fun refreshToken(refreshToken: String, clientId: String): TpidSession {
        val req = postForm("/api/v1/oauth/token", mapOf(
            "grant_type" to "refresh_token",
            "refresh_token" to refreshToken,
            "client_id" to clientId,
        ))
        execute(req).use { resp ->
            val body = resp.body?.string().orEmpty()
            if (!resp.isSuccessful) throw parseServerError(resp, body)
            val o = json.parseToJsonElement(body).jsonObject
            val accessToken = o["access_token"]?.jsonPrimitive?.content
                ?: throw TpidError.ServerError(resp.code, "no access_token")
            return TpidSession(
                accessToken = accessToken,
                refreshToken = o["refresh_token"]?.jsonPrimitive?.content ?: refreshToken,
                idToken = o["id_token"]?.jsonPrimitive?.content,
                expiresAt = Instant.now().plusSeconds(o["expires_in"]?.jsonPrimitive?.content?.toLongOrNull() ?: 3600L),
                tokenType = o["token_type"]?.jsonPrimitive?.content ?: "Bearer",
                scope = o["scope"]?.jsonPrimitive?.content,
                user = TpidUser(id = "", email = ""),
            )
        }
    }

    suspend fun revokeToken(token: String, clientId: String) {
        val req = postForm("/api/v1/oauth/revoke", mapOf("token" to token, "client_id" to clientId))
        runCatching { execute(req).use { it.body?.string() } }
    }

    /**
     * POST /api/v1/auth/send-code
     *
     * The server rejects requests without a `type` field since late 2025
     * (`missing_fields: email and type required`). Callers pass `"login"` for
     * existing accounts and `"register"` for fresh sign-ups so the server
     * can route the email template and throttle correctly.
     */
    suspend fun requestEmailCode(email: String, clientId: String, type: String = "login") {
        val req = post("/api/v1/auth/send-code", JsonObject(mapOf(
            "email" to JsonPrimitive(email),
            "client_id" to JsonPrimitive(clientId),
            "type" to JsonPrimitive(type),
        )))
        execute(req).use { resp ->
            val body = resp.body?.string().orEmpty()
            if (!resp.isSuccessful) throw parseServerError(resp, body)
        }
    }

    suspend fun quickLogin(
        email: String,
        emailCode: String,
        clientId: String,
        twoFactorCode: String? = null,
        lang: String? = null,
    ): LoginOutcome {
        val req = post("/api/v1/auth/quick-login", JsonObject(buildMap {
            put("client_id", JsonPrimitive(clientId))
            put("email", JsonPrimitive(email))
            put("email_code", JsonPrimitive(emailCode))
            if (!twoFactorCode.isNullOrEmpty()) put("two_factor_code", JsonPrimitive(twoFactorCode))
            if (!lang.isNullOrEmpty()) put("lang", JsonPrimitive(lang))
        }))
        execute(req).use { resp ->
            val body = resp.body?.string().orEmpty()
            if (!resp.isSuccessful) throw parseServerError(resp, body)
            val o = json.parseToJsonElement(body).jsonObject
            val requires2FA = o["requires_2fa"]?.jsonPrimitive?.content?.toBooleanStrictOrNull() ?: false
            if (requires2FA) {
                val emailCodeVerified = o["email_code_verified"]?.jsonPrimitive?.content?.toBooleanStrictOrNull() ?: true
                return LoginOutcome.RequiresTwoFactor(emailCodeVerified)
            }
            val accessToken = o["accessToken"]?.jsonPrimitive?.content
                ?: o["access_token"]?.jsonPrimitive?.content
                ?: throw TpidError.ServerError(resp.code, "quick-login response missing accessToken")
            val refreshToken = o["refreshToken"]?.jsonPrimitive?.content
                ?: o["refresh_token"]?.jsonPrimitive?.content
            val idToken = o["idToken"]?.jsonPrimitive?.content ?: o["id_token"]?.jsonPrimitive?.content
            val expiresIn = o["expiresIn"]?.jsonPrimitive?.content?.toLongOrNull()
                ?: o["expires_in"]?.jsonPrimitive?.content?.toLongOrNull() ?: 3600L
            val tokenType = o["tokenType"]?.jsonPrimitive?.content
                ?: o["token_type"]?.jsonPrimitive?.content ?: "Bearer"
            val scope = o["scope"]?.jsonPrimitive?.content
            val userObj = o["user"]?.jsonObject
            val user: TpidUser = if (userObj != null) TpidUser(
                id = userObj["id"]?.jsonPrimitive?.content ?: "",
                email = userObj["email"]?.jsonPrimitive?.content ?: email,
                emailVerified = userObj["email_verified"]?.jsonPrimitive?.content?.toBooleanStrictOrNull()
                    ?: userObj["emailVerified"]?.jsonPrimitive?.content?.toBooleanStrictOrNull()
                    ?: false,
                name = userObj["name"]?.jsonPrimitive?.content,
                avatarUrl = userObj["avatar_url"]?.jsonPrimitive?.content ?: userObj["picture"]?.jsonPrimitive?.content,
                locale = userObj["locale"]?.jsonPrimitive?.content,
            ) else TpidUser(id = "unknown", email = email)
            return LoginOutcome.Success(
                TpidSession(accessToken, refreshToken, idToken,
                    Instant.now().plusSeconds(expiresIn), tokenType, scope, user)
            )
        }
    }

    suspend fun verifyEmailCode(email: String, code: String, config: TpidConfig, codeChallenge: String, state: String, nonce: String): String {
        val req = post("/api/v1/auth/verify", JsonObject(buildMap {
            put("email", JsonPrimitive(email))
            put("code", JsonPrimitive(code))
            put("client_id", JsonPrimitive(config.clientId))
            put("redirect_uri", JsonPrimitive(config.redirectUri))
            put("scope", JsonPrimitive(config.scopeString))
            put("code_challenge", JsonPrimitive(codeChallenge))
            put("code_challenge_method", JsonPrimitive("S256"))
            put("state", JsonPrimitive(state))
            put("nonce", JsonPrimitive(nonce))
        }))
        execute(req).use { resp ->
            val body = resp.body?.string().orEmpty()
            if (!resp.isSuccessful) throw parseServerError(resp, body)
            val o = json.parseToJsonElement(body).jsonObject
            return o["code"]?.jsonPrimitive?.content
                ?: throw TpidError.ServerError(resp.code, "no code")
        }
    }

    /**
     * POST `/api/v1/auth/register` — complete sign-up.
     *
     * Prerequisite: the caller must have already requested an email verification
     * code via [requestEmailCode] with `type = "register"`.
     *
     * Unlike [login], this endpoint returns `accessToken`, `refreshToken` and
     * the `user` object directly (no OAuth `code` to exchange). We map that
     * response straight into [TpidSession] so the widget completes in one call.
     *
     * The server field naming has shifted over time — this method accepts both
     * camelCase (`accessToken`) and snake_case (`access_token`) tokens so the
     * widget keeps working when the backend rolls either variant.
     */
    suspend fun register(
        email: String,
        password: String,
        username: String,
        emailCode: String,
        config: TpidConfig,
    ): TpidSession {
        val req = post("/api/v1/auth/register", JsonObject(mapOf(
            "email" to JsonPrimitive(email),
            "password" to JsonPrimitive(password),
            "username" to JsonPrimitive(username),
            "email_code" to JsonPrimitive(emailCode),
            "client_id" to JsonPrimitive(config.clientId),
            "lang" to JsonPrimitive((config.language ?: "").take(2).ifBlank { "en" }),
        )))
        execute(req).use { resp ->
            val body = resp.body?.string().orEmpty()
            if (!resp.isSuccessful) throw parseServerError(resp, body)
            val o = json.parseToJsonElement(body).jsonObject
            val access = o["accessToken"]?.jsonPrimitive?.content
                ?: o["access_token"]?.jsonPrimitive?.content
                ?: throw TpidError.ServerError(resp.code, "register response missing access token")
            val refresh = o["refreshToken"]?.jsonPrimitive?.content
                ?: o["refresh_token"]?.jsonPrimitive?.content
            val expiresIn = o["expiresIn"]?.jsonPrimitive?.content?.toLongOrNull()
                ?: o["expires_in"]?.jsonPrimitive?.content?.toLongOrNull()
                ?: 3600L

            // Populate TpidUser from the userinfo blob the server embedded, or
            // fall back to /oauth/userinfo for the canonical OIDC claims.
            val userObj = o["user"] as? JsonObject
            val user = if (userObj != null) {
                TpidUser(
                    id = userObj["id"]?.jsonPrimitive?.content
                        ?: userObj["sub"]?.jsonPrimitive?.content ?: "",
                    email = userObj["email"]?.jsonPrimitive?.content ?: email,
                    emailVerified = userObj["email_verified"]?.jsonPrimitive?.content?.toBoolean() ?: true,
                    name = userObj["name"]?.jsonPrimitive?.content ?: userObj["username"]?.jsonPrimitive?.content,
                    avatarUrl = userObj["avatar_url"]?.jsonPrimitive?.content ?: userObj["picture"]?.jsonPrimitive?.content,
                    locale = userObj["locale"]?.jsonPrimitive?.content,
                )
            } else {
                TpidUser(id = "", email = email, name = username)
            }

            return TpidSession(
                accessToken = access,
                refreshToken = refresh,
                idToken = o["idToken"]?.jsonPrimitive?.content ?: o["id_token"]?.jsonPrimitive?.content,
                expiresAt = Instant.now().plusSeconds(expiresIn),
                tokenType = o["tokenType"]?.jsonPrimitive?.content ?: o["token_type"]?.jsonPrimitive?.content ?: "Bearer",
                scope = o["scope"]?.jsonPrimitive?.content,
                user = user,
            )
        }
    }

    // -------------------- QR LOGIN (desktop-side) --------------------

    data class QrInit(val sessionId: String, val qrUrl: String, val ttlSeconds: Int)

    /**
     * Initiate a QR login session. The server allocates a short-lived
     * `sessionId` and returns the [qrUrl] the desktop widget must render into
     * a QR image; scanning that URL with a signed-in phone confirms the
     * desktop sign-in via `/auth/qr/login-confirm/:sessionId`.
     */
    suspend fun qrLoginInit(clientId: String, sdk: String = "jvm-desktop"): QrInit {
        val req = post("/api/v1/auth/qr/login-init", JsonObject(mapOf(
            "client_id" to JsonPrimitive(clientId),
            "sdk"       to JsonPrimitive(sdk),
        )))
        execute(req).use { resp ->
            val body = resp.body?.string().orEmpty()
            if (!resp.isSuccessful) throw parseServerError(resp, body)
            val o = json.parseToJsonElement(body).jsonObject
            val sid = o["sessionId"]?.jsonPrimitive?.content
                ?: o["session_id"]?.jsonPrimitive?.content
                ?: throw TpidError.ServerError(resp.code, "qr-init: missing sessionId")
            val qrUrl = o["qrUrl"]?.jsonPrimitive?.content
                ?: o["qr_url"]?.jsonPrimitive?.content
                ?: "https://tokenpay.space/qr-login?sid=$sid"
            val ttl = o["ttl"]?.jsonPrimitive?.content?.toIntOrNull() ?: 300
            return QrInit(sid, qrUrl, ttl)
        }
    }

    /**
     * Represents one snapshot of the QR session status.
     *
     * `approved` means the phone has confirmed the login; the session is
     * consumed server-side and must not be polled again.
     */
    sealed class QrPollResult {
        data object Pending : QrPollResult()
        data object Expired : QrPollResult()
        data class Approved(val session: TpidSession) : QrPollResult()
    }

    suspend fun qrLoginPoll(sessionId: String): QrPollResult {
        val req = get("/api/v1/auth/qr/login-poll/$sessionId")
        execute(req).use { resp ->
            val body = resp.body?.string().orEmpty()
            if (!resp.isSuccessful) throw parseServerError(resp, body)
            val o = json.parseToJsonElement(body).jsonObject
            return when (o["status"]?.jsonPrimitive?.content) {
                "approved" -> {
                    val accessToken = o["accessToken"]?.jsonPrimitive?.content
                        ?: o["access_token"]?.jsonPrimitive?.content
                        ?: throw TpidError.ServerError(resp.code, "approved QR missing access token")
                    val refreshToken = o["refreshToken"]?.jsonPrimitive?.content
                        ?: o["refresh_token"]?.jsonPrimitive?.content
                    val userObj = o["user"] as? JsonObject
                    val user = if (userObj != null) {
                        TpidUser(
                            id = userObj["id"]?.jsonPrimitive?.content ?: userObj["sub"]?.jsonPrimitive?.content ?: "",
                            email = userObj["email"]?.jsonPrimitive?.content ?: "",
                            emailVerified = userObj["email_verified"]?.jsonPrimitive?.content?.toBoolean() ?: true,
                            name = userObj["name"]?.jsonPrimitive?.content,
                            avatarUrl = userObj["avatar_url"]?.jsonPrimitive?.content ?: userObj["picture"]?.jsonPrimitive?.content,
                            locale = userObj["locale"]?.jsonPrimitive?.content,
                        )
                    } else {
                        TpidUser(id = "", email = "")
                    }
                    QrPollResult.Approved(TpidSession(
                        accessToken = accessToken,
                        refreshToken = refreshToken,
                        idToken = o["idToken"]?.jsonPrimitive?.content ?: o["id_token"]?.jsonPrimitive?.content,
                        expiresAt = Instant.now().plusSeconds(o["expiresIn"]?.jsonPrimitive?.content?.toLongOrNull() ?: o["expires_in"]?.jsonPrimitive?.content?.toLongOrNull() ?: 3600L),
                        tokenType = "Bearer",
                        scope = null,
                        user = user,
                    ))
                }
                "expired" -> QrPollResult.Expired
                else -> QrPollResult.Pending
            }
        }
    }

    suspend fun deviceAuthorize(clientId: String, scope: String): TpidDeviceFlowSession {
        val req = postForm("/api/v1/oauth/device", mapOf("client_id" to clientId, "scope" to scope))
        execute(req).use { resp ->
            val body = resp.body?.string().orEmpty()
            if (!resp.isSuccessful) throw parseServerError(resp, body)
            val o = json.parseToJsonElement(body).jsonObject
            return TpidDeviceFlowSession(
                deviceCode = o["device_code"]!!.jsonPrimitive.content,
                userCode = o["user_code"]!!.jsonPrimitive.content,
                verificationURI = o["verification_uri"]!!.jsonPrimitive.content,
                verificationURIComplete = o["verification_uri_complete"]?.jsonPrimitive?.content,
                expiresIn = o["expires_in"]!!.jsonPrimitive.content.toInt(),
                interval = o["interval"]?.jsonPrimitive?.content?.toIntOrNull() ?: 5,
            )
        }
    }

    suspend fun pollDeviceToken(session: TpidDeviceFlowSession, clientId: String): TpidSession {
        val deadline = System.currentTimeMillis() + session.expiresIn * 1000L
        var interval = session.interval
        while (System.currentTimeMillis() < deadline) {
            val req = postForm("/api/v1/oauth/device/token", mapOf(
                "grant_type" to "urn:ietf:params:oauth:grant-type:device_code",
                "device_code" to session.deviceCode,
                "client_id" to clientId,
            ))
            val response = execute(req)
            val body = response.body?.string().orEmpty()
            response.close()
            if (response.isSuccessful) {
                val o = json.parseToJsonElement(body).jsonObject
                val access = o["access_token"]?.jsonPrimitive?.content
                    ?: throw TpidError.ServerError(response.code, "no access_token")
                return TpidSession(
                    accessToken = access,
                    refreshToken = o["refresh_token"]?.jsonPrimitive?.content,
                    idToken = o["id_token"]?.jsonPrimitive?.content,
                    expiresAt = Instant.now().plusSeconds(o["expires_in"]?.jsonPrimitive?.content?.toLongOrNull() ?: 3600L),
                    tokenType = o["token_type"]?.jsonPrimitive?.content ?: "Bearer",
                    scope = o["scope"]?.jsonPrimitive?.content,
                    user = TpidUser(id = "", email = "")
                )
            }
            val errCode = runCatching { json.parseToJsonElement(body).jsonObject["error"]?.jsonPrimitive?.content }.getOrNull()
            when (errCode) {
                "authorization_pending" -> { /* continue */ }
                "slow_down" -> interval += 5
                "access_denied" -> throw TpidError.OAuthError(errCode, "User denied the request")
                "expired_token" -> throw TpidError.OAuthError(errCode, "Device code expired")
                else -> if (!response.isSuccessful) throw parseServerError(response, body)
            }
            Thread.sleep(interval * 1000L)
        }
        throw TpidError.OAuthError("expired_token", "Device flow timeout")
    }

    suspend fun fetchSdkConfig(clientId: String): JsonObject {
        val req = get("/api/v1/sdk/config?client_id=${URLEncoder.encode(clientId, "UTF-8")}")
        execute(req).use { resp ->
            val body = resp.body?.string().orEmpty()
            if (!resp.isSuccessful) throw parseServerError(resp, body)
            return json.parseToJsonElement(body).jsonObject
        }
    }

    suspend fun fetchTlsPins(): List<String> {
        val req = get("/api/v1/sdk/tls-pins")
        execute(req).use { resp ->
            val body = resp.body?.string().orEmpty()
            if (!resp.isSuccessful) return emptyList()
            val o = json.parseToJsonElement(body).jsonObject
            return o["pins"]?.jsonArray?.map { it.jsonPrimitive.content }?.filter { it.isNotBlank() && !it.startsWith("REPLACE_") } ?: emptyList()
        }
    }

    private fun parseServerError(resp: Response, body: String): TpidError {
        val errCode = runCatching {
            json.parseToJsonElement(body).jsonObject["error"]?.let {
                if (it is JsonObject) it["code"]?.jsonPrimitive?.content
                else it.jsonPrimitive.content
            }
        }.getOrNull() ?: ""
        val reason = runCatching {
            json.parseToJsonElement(body).jsonObject["error"]?.let {
                if (it is JsonObject) it["message"]?.jsonPrimitive?.content
                else null
            }
        }.getOrNull()

        return when {
            errCode == "invalid_credentials" || errCode == "invalid_grant" -> TpidError.InvalidCredentials(reason)
            errCode == "account_locked" -> TpidError.AccountLocked(reason)
            errCode == "email_not_verified" -> TpidError.EmailNotVerified
            errCode == "totp_required" -> TpidError.TwoFactorRequired(listOf("totp"))
            errCode == "rate_limited" || resp.code == 429 -> {
                val ra = resp.header("Retry-After")?.toIntOrNull()
                TpidError.RateLimited(ra)
            }
            resp.code in 500..599 -> TpidError.ServerError(resp.code, reason)
            else -> TpidError.ServerError(resp.code, reason ?: errCode.ifBlank { body.take(200) })
        }
    }
}
