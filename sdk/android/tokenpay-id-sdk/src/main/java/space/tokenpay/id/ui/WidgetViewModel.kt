package space.tokenpay.id.ui

import androidx.compose.ui.graphics.ImageBitmap
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import space.tokenpay.id.TpidAuth
import space.tokenpay.id.TpidConfig
import space.tokenpay.id.TpidError
import space.tokenpay.id.TpidResult
import space.tokenpay.id.internal.ApiClient
import space.tokenpay.id.internal.QrRenderer
import space.tokenpay.id.internal.RemoteConfig
import space.tokenpay.id.internal.SecureStorage
import space.tokenpay.id.internal.Strings
import space.tokenpay.id.internal.TpidUpdater

/**
 * State-machine backing the widget UI. Each screen reads `state` and calls methods on the VM.
 */
internal class WidgetViewModel(
    private val appState: TpidAuth.State,
    private val prefillEmail: String?,
    private val onComplete: (TpidResult) -> Unit,
) : ViewModel() {

    private val _state = MutableStateFlow(initialState())
    val state: StateFlow<WidgetState> = _state.asStateFlow()

    // Cache of the server-delivered remote config — used both when applying
    // overrides at init time and when the user switches language at runtime.
    @Volatile
    private var remote: RemoteConfig = RemoteConfig()

    /**
     * 2.6.2 — track the currently in-flight network request so the user can
     * abort a stuck spinner via the Cancel-button on [LoadingScreen]. Also
     * remembers the step the loading was initiated from so cancellation
     * (or a hard timeout) routes back somewhere sensible instead of
     * dropping the user on Welcome.
     */
    @Volatile
    private var loadingJob: Job? = null
    @Volatile
    private var loadingFromStep: WidgetStep = WidgetStep.Welcome

    /**
     * 2.6.2 — flag set once the user has clicked the Update banner's pill
     * during this widget session. Prevents the banner from re-appearing
     * after [openUpdateDownloadUrl] has handed control to the browser.
     */
    @Volatile
    private var updateBannerDismissedThisSession: Boolean = false

    init {
        // Fire telemetry: first step shown
        appState.telemetry.track("widget.step_shown", mapOf("step" to "welcome"))
        // Kick off SDK config refresh (branding + pins)
        viewModelScope.launch {
            runCatching { appState.sdkConfigLoader.refreshConfig(appState.config.clientId) }
                .onSuccess { br ->
                    _state.update { it.copy(
                        branding = appState.config.brandingOverride ?: br,
                        tlsPinned = appState.api.hasActivePins(),
                    ) }
                }
        }
        // Kick off remote UI-override fetch (theme tokens, strings, flags,
        // update banner). Separate request from the SDK config loader so a
        // failure in one doesn't take down the other.
        viewModelScope.launch {
            val r = RemoteConfig.fetch(appState.api, appState.config.clientId)
            remote = r
            _state.update { cur ->
                cur.copy(
                    strings = mergeStrings(cur.language, r),
                    // 2.6.2: respect the per-session dismissed flag so the
                    // banner doesn't reappear right after the user clicked
                    // "Update" and we punted to the system browser.
                    showUpdateBanner = !updateBannerDismissedThisSession && (
                        r.isOlderThan(r.recommendedSdkVersion) ||
                            r.isOlderThan(r.minSdkVersion)
                    ),
                    // 2.6.0: forward the server-chosen download URL so the
                    // banner's Update pill has somewhere real to go. Stays
                    // null if the server omitted the field; the UI falls
                    // back to `https://tokenpay.space/sdk#android`.
                    updateDownloadUrl = r.downloadUrl,
                )
            }
        }
    }

    /**
     * Compose the visible strings map for [lang] by layering the server's
     * `strings_override[<lang>]` on top of the locally-bundled translations.
     */
    private fun mergeStrings(lang: TpidConfig.Language, r: RemoteConfig): Map<String, String> {
        val base = Strings.of(lang)
        val code = when (Strings.resolveLanguage(lang)) {
            TpidConfig.Language.RUSSIAN -> "ru"
            TpidConfig.Language.CHINESE -> "zh"
            else -> "en"
        }
        val ov = r.stringsOverride[code].orEmpty()
        return if (ov.isEmpty()) base else base + ov
    }

    private fun initialState(): WidgetState {
        val effLang = Strings.resolveLanguage(appState.config.language)
        val prefilled = !prefillEmail.isNullOrBlank()
        // 2.6.0: read the last-used account profile so the widget can open
        // with "Continue as <user>" instead of an empty email field every
        // time. Skipped when an explicit `prefillEmail` was passed — in
        // that case the integrator is driving multi-account UX themselves.
        val last = if (prefilled) null else appState.storage.readLastAccount()
        val initialStep = when {
            prefilled -> WidgetStep.Email
            last != null -> WidgetStep.ReturningUser
            else -> WidgetStep.Welcome
        }
        return WidgetState(
            step = initialStep,
            email = prefillEmail ?: last?.email.orEmpty(),
            lastAccount = last,
            branding = appState.config.brandingOverride ?: appState.sdkConfigLoader.cachedBranding(),
            antiPhishingDomain = appState.config.issuer.removePrefix("https://").removePrefix("http://").substringBefore("/"),
            tlsPinned = appState.api.hasActivePins(),
            language = effLang,
            strings = Strings.of(effLang),
        )
    }

    /**
     * 2.6.0 — account-memory step. Jump straight to password entry for the
     * remembered user. If the server has since disabled password login for
     * them (say, migrated to passkey-only), [submitPassword]'s outcome
     * handler will route to the right step automatically.
     */
    fun continueAsLast() {
        val s = _state.value
        val last = s.lastAccount ?: return
        val ageMs = System.currentTimeMillis() - last.lastAuthenticatedAtMs
        when {
            last.lastAuthenticatedAtMs > 0L && ageMs in 0L..REMEMBER_INSTANT_MS -> continueRememberedInstant(last)
            last.lastAuthenticatedAtMs > 0L && ageMs in 0L..REMEMBER_EMAIL_CODE_MS -> requestRememberedEmailCode(last)
            else -> {
                _state.update {
                    it.copy(step = WidgetStep.Password, email = last.email, password = "", code = "", error = null)
                }
                appState.telemetry.track("widget.step_shown", mapOf("step" to "password", "source" to "last_account"))
            }
        }
    }

    /** 2.6.0 — "Use another account" link on the returning-user card. */
    fun useAnotherAccount() {
        _state.update {
            it.copy(step = WidgetStep.Email, email = "", password = "", code = "", totp = "", error = null)
        }
        appState.telemetry.track("widget.step_shown", mapOf("step" to "email", "source" to "other_account"))
    }

    /** 2.6.0 — "Forget this account" link on the returning-user card. */
    fun forgetLastAccount() {
        appState.storage.clearLastAccount()
        _state.update {
            it.copy(step = WidgetStep.Welcome, lastAccount = null, email = "", error = null)
        }
        appState.telemetry.track("widget.last_account_forgotten")
    }

    /** Move from Welcome → Email. */
    fun goEmail() {
        _state.update { it.copy(step = WidgetStep.Email, error = null) }
        appState.telemetry.track("widget.step_shown", mapOf("step" to "email"))
    }

    /**
     * Move directly to the sign-up form. Called from the Welcome screen's
     * "Create account" secondary button and the Email screen's "No account?
     * Create one" footer link — both of which previously routed through
     * [goEmail] and confused users who wanted to register, not sign in.
     *
     * When the user already typed an email before clicking the link, it is
     * preserved so the Register form can prefill the `EmailChip`. Otherwise
     * the form asks for an email when sending the verification code.
     */
    fun goRegister() {
        _state.update { it.copy(step = WidgetStep.Register(codeSent = false), error = null) }
        appState.telemetry.track("widget.step_shown", mapOf("step" to "register"))
    }

    /** Change widget language at runtime. */
    fun setLanguage(lang: TpidConfig.Language) {
        val eff = Strings.resolveLanguage(lang)
        _state.update { it.copy(language = eff, strings = mergeStrings(eff, remote)) }
    }

    // ----------------------------------------------------------------- events

    fun updateEmail(value: String) { _state.update { it.copy(email = value.trim(), error = null) } }
    fun updatePassword(value: String) { _state.update { it.copy(password = value, error = null) } }
    fun updateCode(value: String) { _state.update { it.copy(code = value.filter { c -> c.isDigit() }.take(6), error = null) } }
    fun updateTotp(value: String) { _state.update { it.copy(totp = value.filter { c -> c.isDigit() }.take(6), error = null) } }

    fun submitEmail() {
        val s = _state.value
        if (!isValidEmail(s.email)) {
            _state.update { it.copy(error = s.strings["error_invalid_email"] ?: "Invalid email") }
            return
        }
        loadingJob?.cancel()
        loadingFromStep = WidgetStep.Email
        _state.update { it.copy(step = WidgetStep.Loading(s.strings["loading_checking"] ?: "Checking…"), error = null) }
        appState.telemetry.track("widget.step_submit_ok", mapOf("step" to "email"))
        loadingJob = viewModelScope.launch {
            val result = runCatching {
                withTimeout(LOGIN_TIMEOUT_MS) {
                    appState.api.accountCheck(s.email, appState.config.clientId)
                }
            }
            result.onSuccess { info ->
                val next = when {
                    info.exists -> WidgetStep.Password
                    // No account yet → open the sign-up form (was routing to
                    // Password which always 401'd).
                    else -> WidgetStep.Register(codeSent = false)
                }
                appState.telemetry.track("widget.step_shown", mapOf("step" to stepName(next), "existing" to info.exists))
                _state.update {
                    it.copy(
                        step = next,
                        accountInfo = info,
                        error = null,
                    )
                }
            }.onFailure { e ->
                // 2.6.2 — surface a localised "Request timed out" instead of
                // a stuck spinner when the mobile network drops mid-flight.
                val err = when (e) {
                    is TpidError -> e
                    is TimeoutCancellationException -> TpidError.Timeout
                    else -> TpidError.Unknown(e)
                }
                _state.update {
                    val msg = when (err) {
                        is TpidError.Timeout -> it.strings["err_title_timeout"] ?: "Request timed out"
                        is TpidError.NoNetwork -> it.strings["err_title_network"] ?: "No network"
                        else -> err.message
                    }
                    it.copy(step = WidgetStep.Email, error = msg)
                }
                appState.telemetry.track("widget.step_submit_error", mapOf("step" to "email", "code" to err.code))
            }
        }
    }

    /**
     * Submit the typed password. This is the FIRST call to `/auth/login` in
     * the widget's password flow; it is expected to return
     * `requires_email_code: true` on the happy path because the backend
     * enforces an e-mail second factor on every password login. On that
     * branch the widget flips to the [WidgetStep.EmailCode] step and the
     * user types the 6 digits that just landed in their inbox;
     * [submitEmailCode] then replays the SAME endpoint with `email_code`
     * filled in and receives either `requires_2fa: true` or the final token
     * pair.
     */
    fun submitPassword() {
        val s = _state.value
        if (s.password.length < 8) {
            _state.update { it.copy(error = s.strings["error_password_short"] ?: "Password too short") }
            return
        }
        loadingJob?.cancel()
        loadingFromStep = WidgetStep.Password
        _state.update { it.copy(step = WidgetStep.Loading(s.strings["loading_signing"] ?: "Signing in…"), error = null) }
        loadingJob = viewModelScope.launch {
            runCatching {
                withTimeout(LOGIN_TIMEOUT_MS) {
                    appState.api.login(
                        email = s.email,
                        password = s.password,
                        clientId = appState.config.clientId,
                        lang = s.language.code.takeIf { it != "system" },
                    )
                }
            }.onSuccess { outcome -> handleLoginOutcome(outcome, fromStep = WidgetStep.Password) }
              .onFailure { e -> failLogin(e, WidgetStep.Password, "password") }
        }
    }

    /**
     * Submit the 6-digit e-mail code that arrived after [submitPassword].
     * This replays `/auth/login` with `{email, password, email_code}` —
     * backend either responds with `requires_2fa: true` (go to [WidgetStep.TwoFactor])
     * or the final tokens.
     */
    fun submitEmailCode() {
        val s = _state.value
        if (s.code.length != 6) {
            _state.update { it.copy(error = s.strings["error_code_len"] ?: "Invalid code") }
            return
        }
        loadingJob?.cancel()
        loadingFromStep = WidgetStep.EmailCode
        _state.update { it.copy(step = WidgetStep.Loading(s.strings["loading_verifying"] ?: "Verifying…"), error = null) }
        loadingJob = viewModelScope.launch {
            if (s.password.isBlank()) {
                runCatching {
                    withTimeout(LOGIN_TIMEOUT_MS) {
                        appState.api.quickLogin(
                            email = s.email,
                            emailCode = s.code,
                            clientId = appState.config.clientId,
                            lang = s.language.code.takeIf { it != "system" },
                        )
                    }
                }
                    .onSuccess { outcome -> handleLoginOutcome(outcome, fromStep = WidgetStep.EmailCode) }
                    .onFailure { e -> failLogin(e, WidgetStep.EmailCode, "email_code") }
            } else {
                runCatching {
                    withTimeout(LOGIN_TIMEOUT_MS) {
                        appState.api.login(
                            email = s.email,
                            password = s.password,
                            clientId = appState.config.clientId,
                            emailCode = s.code,
                            lang = s.language.code.takeIf { it != "system" },
                        )
                    }
                }.onSuccess { outcome -> handleLoginOutcome(outcome, fromStep = WidgetStep.EmailCode) }
                  .onFailure { e -> failLogin(e, WidgetStep.EmailCode, "email_code") }
            }
        }
    }

    /**
     * Submit the TOTP / 2FA code after an e-mail code has already been
     * accepted. Replays `/auth/login` with all four secrets — this is the
     * only call that can produce [ApiClient.LoginOutcome.Success] when 2FA
     * is enabled on the account.
     */
    fun submitTotp() {
        val s = _state.value
        if (s.totp.length != 6) {
            _state.update { it.copy(error = s.strings["error_code_len"] ?: "Invalid code") }
            return
        }
        loadingJob?.cancel()
        loadingFromStep = WidgetStep.TwoFactor
        _state.update { it.copy(step = WidgetStep.Loading(s.strings["loading_verifying"] ?: "Verifying…"), error = null) }
        loadingJob = viewModelScope.launch {
            runCatching {
                withTimeout(LOGIN_TIMEOUT_MS) {
                    if (s.password.isBlank()) {
                        appState.api.quickLogin(
                            email = s.email,
                            emailCode = s.code,
                            clientId = appState.config.clientId,
                            twoFactorCode = s.totp,
                            lang = s.language.code.takeIf { it != "system" },
                        )
                    } else {
                        appState.api.login(
                            email = s.email,
                            password = s.password,
                            clientId = appState.config.clientId,
                            emailCode = s.code.ifEmpty { null },
                            twoFactorCode = s.totp,
                            lang = s.language.code.takeIf { it != "system" },
                        )
                    }
                }
            }.onSuccess { outcome -> handleLoginOutcome(outcome, fromStep = WidgetStep.TwoFactor) }
              .onFailure { e -> failLogin(e, WidgetStep.TwoFactor, "2fa") }
        }
    }

    /**
     * Shared branch-on-outcome so the three password-flow steps don't repeat
     * the same 15 lines of mapping. Uses [fromStep] to decide where to fall
     * back on a [ApiClient.LoginOutcome.RequiresEmailCode] after the code
     * step (rare — server would only send that if the user typed a stale
     * code and the code expired in-between).
     */
    private fun handleLoginOutcome(outcome: ApiClient.LoginOutcome, fromStep: WidgetStep) {
        when (outcome) {
            is ApiClient.LoginOutcome.Success -> persistAndComplete(outcome.success)
            is ApiClient.LoginOutcome.RequiresEmailCode -> {
                _state.update {
                    it.copy(
                        step = WidgetStep.EmailCode,
                        code = "",
                        error = null,
                    )
                }
                appState.telemetry.track("widget.step_shown",
                    mapOf("step" to "email_code", "reason" to "password_login"))
            }
            is ApiClient.LoginOutcome.RequiresTwoFactor -> {
                _state.update {
                    it.copy(
                        step = WidgetStep.TwoFactor,
                        totp = "",
                        error = null,
                        twoFactorMethods = listOf("totp"),
                    )
                }
                appState.telemetry.track("widget.step_shown", mapOf("step" to "2fa"))
            }
        }
    }

    private fun failLogin(e: Throwable, backStep: WidgetStep, telemetryStep: String) {
        // 2.6.2 — coroutine-level [withTimeout] surfaces as
        // [TimeoutCancellationException]; map it to the user-facing
        // [TpidError.Timeout] so the back-step shows a friendly message
        // ("Connection timed out") instead of an empty `null` cause string.
        // Without this users would see an indistinguishable spinner that
        // eventually flipped back with no explanation on flaky mobile
        // networks (the original "infinite spinner" report).
        val err = when (e) {
            is TpidError -> e
            is TimeoutCancellationException -> TpidError.Timeout
            else -> TpidError.Unknown(e)
        }
        when (err) {
            is TpidError.AccountLocked, is TpidError.EmailNotVerified, is TpidError.PhishingDetected,
            is TpidError.ConfigurationError -> {
                _state.update { it.copy(step = WidgetStep.ErrorFatal(err), error = null) }
                appState.telemetry.track("widget.error_shown", mapOf("code" to err.code))
            }
            else -> {
                _state.update {
                    val freshCode = if (backStep == WidgetStep.EmailCode) "" else it.code
                    val freshTotp = if (backStep == WidgetStep.TwoFactor) "" else it.totp
                    val msg = when (err) {
                        is TpidError.Timeout ->
                            it.strings["err_title_timeout"] ?: "Request timed out"
                        is TpidError.NoNetwork ->
                            it.strings["err_title_network"] ?: "No network"
                        is TpidError.ServerUnavailable ->
                            it.strings["err_title_server"] ?: "Server unavailable"
                        is TpidError.TlsFailure ->
                            it.strings["err_title_tls"] ?: "TLS connection failed"
                        is TpidError.StorageFailure ->
                            it.strings["err_title_storage"] ?: "Local storage failed"
                        else -> err.message
                    }
                    it.copy(step = backStep, error = msg,
                            code = freshCode, totp = freshTotp)
                }
                appState.telemetry.track("widget.step_submit_error",
                    mapOf("step" to telemetryStep, "code" to err.code))
            }
        }
    }

    /**
     * Request a one-time code email. [type] overrides the auto-detected value;
     * when left `null` we default to `"login"` for a known-existing account
     * (per the latest `accountCheck`) and `"register"` otherwise.
     */
    fun requestEmailCode(type: String? = null) {
        val s = _state.value
        val effectiveType = type ?: if (s.accountInfo?.exists == true) "login" else "register"
        loadingJob?.cancel()
        loadingFromStep = WidgetStep.Email
        _state.update { it.copy(step = WidgetStep.Loading(s.strings["loading_sending"] ?: "Sending code…"), error = null) }
        loadingJob = viewModelScope.launch {
            runCatching {
                withTimeout(LOGIN_TIMEOUT_MS) {
                    appState.api.requestEmailCode(s.email, appState.config.clientId, effectiveType)
                }
            }
                .onSuccess {
                    _state.update { it.copy(step = WidgetStep.EmailCode, error = null) }
                    appState.telemetry.track("widget.step_shown", mapOf("step" to "email_code"))
                }
                .onFailure { e ->
                    val err = when (e) {
                        is TpidError -> e
                        is TimeoutCancellationException -> TpidError.Timeout
                        else -> TpidError.Unknown(e)
                    }
                    _state.update {
                        val msg = when (err) {
                            is TpidError.Timeout -> it.strings["err_title_timeout"] ?: "Request timed out"
                            is TpidError.NoNetwork -> it.strings["err_title_network"] ?: "No network"
                            else -> err.message
                        }
                        it.copy(step = WidgetStep.Email, error = msg)
                    }
                }
        }
    }

    fun switchToEmailCode() {
        requestEmailCode()
    }

    fun switchToPasskey() {
        _state.update { it.copy(step = WidgetStep.Passkey, error = null) }
        appState.telemetry.track("widget.passkey_started")
    }

    fun switchToRecovery() {
        _state.update { it.copy(step = WidgetStep.Recovery, error = null) }
    }

    fun resetToStart() {
        _state.update {
            it.copy(step = WidgetStep.Email, password = "", code = "", totp = "", error = null)
        }
    }

    // -------------------------------------------------------------- sign-up

    fun updateRegUsername(value: String) {
        // Mirror the server regex `^[a-z0-9._]{3,30}$` at input time so the
        // widget can't compose a payload that `/auth/register` would reject
        // with `invalid_username`. Auto-lowercase and drop illegal characters
        // so the field silently sanitises pasted text instead of flashing
        // a validation error every keystroke.
        val sanitised = value.lowercase()
            .filter { ch -> ch in 'a'..'z' || ch in '0'..'9' || ch == '.' || ch == '_' }
            .take(30)
        _state.update { it.copy(regUsername = sanitised, error = null) }
    }
    fun updateRegPassword(value: String) {
        _state.update { it.copy(regPassword = value, error = null) }
    }
    fun updateRegCode(value: String) {
        _state.update { it.copy(regCode = value.filter { c -> c.isDigit() }.take(6), error = null) }
    }

    /**
     * Step 1 of sign-up: user has entered username + password. Request the
     * verification e-mail and flip [WidgetStep.Register.codeSent] so the code
     * input appears.
     */
    fun sendRegisterCode() {
        val s = _state.value
        if (s.regUsername.length < 3) {
            _state.update { it.copy(error = s.strings["error_username_short"] ?: "Username too short") }
            return
        }
        if (!s.regUsername.matches(Regex("^[a-z0-9._]{3,30}$"))) {
            _state.update {
                it.copy(error = s.strings["error_username_invalid"]
                    ?: "Lowercase letters, digits, dots and underscores only")
            }
            return
        }
        if (s.regPassword.length < 8) {
            _state.update { it.copy(error = s.strings["error_password_short"] ?: "Password too short") }
            return
        }
        loadingJob?.cancel()
        loadingFromStep = WidgetStep.Register(codeSent = false)
        _state.update { it.copy(step = WidgetStep.Loading(s.strings["loading_sending"] ?: "Sending code…"), error = null) }
        loadingJob = viewModelScope.launch {
            runCatching {
                withTimeout(LOGIN_TIMEOUT_MS) {
                    appState.api.requestEmailCode(s.email, appState.config.clientId, "register")
                }
            }.onSuccess {
                _state.update { it.copy(step = WidgetStep.Register(codeSent = true), error = null) }
                appState.telemetry.track("widget.step_shown", mapOf("step" to "register_code"))
            }.onFailure { e ->
                val err = when (e) {
                    is TpidError -> e
                    is TimeoutCancellationException -> TpidError.Timeout
                    else -> TpidError.Unknown(e)
                }
                _state.update {
                    val msg = when (err) {
                        is TpidError.Timeout -> it.strings["err_title_timeout"] ?: "Request timed out"
                        is TpidError.NoNetwork -> it.strings["err_title_network"] ?: "No network"
                        else -> err.message
                    }
                    it.copy(step = WidgetStep.Register(codeSent = false), error = msg)
                }
            }
        }
    }

    /**
     * Step 2 of sign-up: user entered the verification code. POST to
     * `/auth/register`; the server returns the final token pair so we skip
     * the OAuth code exchange entirely.
     */
    fun submitRegister() {
        val s = _state.value
        if (s.regCode.length != 6) {
            _state.update { it.copy(error = s.strings["error_code_len"] ?: "Invalid code") }
            return
        }
        loadingJob?.cancel()
        loadingFromStep = WidgetStep.Register(codeSent = true)
        _state.update { it.copy(step = WidgetStep.Loading(s.strings["loading_creating"] ?: "Creating account…"), error = null) }
        loadingJob = viewModelScope.launch {
            runCatching {
                withTimeout(LOGIN_TIMEOUT_MS) {
                    appState.api.register(
                        email = s.email,
                        password = s.regPassword,
                        username = s.regUsername,
                        emailCode = s.regCode,
                        clientId = appState.config.clientId,
                        lang = appState.config.language.name.lowercase().take(2),
                    )
                }
            }.onSuccess { success ->
                appState.telemetry.track("widget.register_success")
                persistAndComplete(success)
            }.onFailure { e ->
                val err = when (e) {
                    is TpidError -> e
                    is TimeoutCancellationException -> TpidError.Timeout
                    else -> TpidError.Unknown(e)
                }
                _state.update {
                    val msg = when (err) {
                        is TpidError.Timeout -> it.strings["err_title_timeout"] ?: "Request timed out"
                        is TpidError.NoNetwork -> it.strings["err_title_network"] ?: "No network"
                        else -> err.message
                    }
                    it.copy(step = WidgetStep.Register(codeSent = true), error = msg, regCode = "")
                }
                appState.telemetry.track("widget.step_submit_error", mapOf("step" to "register", "code" to err.code))
            }
        }
    }

    /**
     * U2 (pre.9 → 2.6.0): once a login has persisted a real session, keep a
     * reference so system-back / close-after-success returns **RESULT_OK**
     * with the session instead of the misleading [TpidResult.Cancelled].
     * The earlier behaviour made integrators think the user cancelled even
     * though the tokens were already in storage.
     */
    private var lastSuccess: TpidResult.Success? = null

    fun cancel() {
        val pending = lastSuccess
        if (pending != null) {
            appState.telemetry.track("widget.closed_cancel_after_success")
            onComplete(pending)
            return
        }
        // 2.6.2 — abort any in-flight request so a half-open socket on a
        // flaky mobile network doesn't keep the process alive after the
        // user already dismissed the widget.
        loadingJob?.cancel()
        loadingJob = null
        appState.telemetry.track("widget.closed_cancel", mapOf("step" to stepName(_state.value.step)))
        onComplete(TpidResult.Cancelled)
    }

    /**
     * 2.6.2 — Manual escape hatch from a stuck spinner.
     *
     * Triggered by the new "Cancel" button on [LoadingScreen]. Aborts the
     * currently-running network request and returns the user to the step
     * the loading was initiated from ([loadingFromStep]) — typically the
     * password / email-code / 2FA form they came from. No error message
     * is set: the user explicitly chose to cancel, so showing "Request
     * timed out" would be misleading.
     */
    fun cancelLoading() {
        val back = loadingFromStep
        loadingJob?.cancel()
        loadingJob = null
        if (_state.value.step is WidgetStep.Loading) {
            _state.update { it.copy(step = back, error = null) }
            appState.telemetry.track("widget.loading_cancelled", mapOf("step" to stepName(back)))
        }
    }

    fun back() {
        val cur = _state.value.step
        // U2: Back while on Success must commit — the user already authed;
        // dropping them to Cancelled would throw away a real session.
        if (cur == WidgetStep.Success) {
            cancel()   // cancel() now resolves to the pending success.
            return
        }
        // 2.6.2 — system-back from a stuck spinner aborts the request and
        // returns to the form (was: closed the entire widget, losing the
        // user's typed email/password).
        if (cur is WidgetStep.Loading) {
            cancelLoading()
            return
        }
        when (cur) {
            WidgetStep.Email -> _state.update { it.copy(step = WidgetStep.Welcome, error = null) }
            // 2.6.0: if we came from the ReturningUser card, "back" should
            // take the user back to that card rather than dropping them into
            // the Email step with a pre-filled field — that felt like the
            // remembered account was forgotten.
            WidgetStep.Password,
            WidgetStep.EmailCode,
            WidgetStep.TwoFactor,
            WidgetStep.Passkey,
            WidgetStep.Recovery -> _state.update {
                val backStep = if (it.lastAccount != null && it.email == it.lastAccount.email) {
                    WidgetStep.ReturningUser
                } else {
                    WidgetStep.Email
                }
                it.copy(step = backStep, password = "", code = "", totp = "", error = null)
            }
            is WidgetStep.Register -> _state.update {
                it.copy(step = WidgetStep.Email, regUsername = "", regPassword = "", regCode = "", error = null)
            }
            WidgetStep.QrCode -> {
                qrPollJob?.cancel()
                _state.update {
                    it.copy(
                        step = WidgetStep.Welcome,
                        qrSessionId = null, qrUrl = null,
                        qrImage = null, qrStatus = "loading",
                        error = null,
                    )
                }
            }
            else -> cancel()
        }
    }

    // ------------------------------------------------------------- QR login

    private var qrPollJob: Job? = null

    /**
     * Transition to the QR login step and start a fresh session. Cancels any
     * previous QR polling job so re-entering the step doesn't produce two
     * concurrent pollers.
     */
    fun goQr() {
        qrPollJob?.cancel()
        _state.update {
            it.copy(
                step = WidgetStep.QrCode,
                qrSessionId = null, qrUrl = null,
                qrImage = null, qrStatus = "loading",
                error = null,
            )
        }
        appState.telemetry.track("widget.step_shown", mapOf("step" to "qr"))
        startQrPolling()
    }

    /**
     * Regenerate the QR code (e.g. after expiry). Keeps the user on the step
     * but re-invokes `/auth/qr/login-init`.
     */
    fun refreshQr() {
        qrPollJob?.cancel()
        _state.update {
            it.copy(
                qrSessionId = null, qrUrl = null,
                qrImage = null, qrStatus = "loading",
                error = null,
            )
        }
        startQrPolling()
    }

    /**
     * Accept a `tokenpay.space/qr-login?sid=…` URL from the clipboard as an
     * alternative to rendering + scanning. Extracts the `sid` and jumps
     * straight into polling.
     */
    fun pasteQrLink(raw: String) {
        val sid = Regex("[?&]sid=([A-Za-z0-9\\-]+)").find(raw)?.groupValues?.get(1)
        if (sid == null) {
            _state.update {
                it.copy(qrStatus = "error",
                    error = it.strings["qr_paste_prompt"]
                        ?: "Paste the tokenpay.space/qr-login?sid=… link")
            }
            return
        }
        qrPollJob?.cancel()
        _state.update {
            it.copy(
                qrSessionId = sid, qrUrl = raw,
                qrImage = null, qrStatus = "pending",
                error = null,
            )
        }
        startQrPolling()
    }

    private fun startQrPolling() {
        qrPollJob = viewModelScope.launch {
            val s = _state.value
            val init: ApiClient.QrInit? = if (s.qrSessionId == null) {
                runCatching { appState.api.qrLoginInit(appState.config.clientId) }.getOrNull()
            } else {
                ApiClient.QrInit(s.qrSessionId, s.qrUrl ?: "https://tokenpay.space/qr-login?sid=${s.qrSessionId}", 300)
            }
            if (init == null) {
                _state.update {
                    it.copy(qrStatus = "error",
                        error = it.strings["qr_status_error"] ?: "Couldn't start QR session")
                }
                return@launch
            }
            val image: ImageBitmap? = withContext(Dispatchers.Default) {
                QrRenderer.render(init.qrUrl, pixelSize = 512)
            }
            if (image == null) {
                // ZXing couldn't build the bitmap for any reason — surface
                // a visible error instead of leaving the user staring at a
                // silent loading spinner. The QrScreen "error" branch also
                // shows the raw URL + a "Paste link" button so users on
                // devices where rendering fails can still complete the
                // flow by copy-paste.
                _state.update {
                    it.copy(
                        qrSessionId = init.sessionId,
                        qrUrl = init.qrUrl,
                        qrImage = null,
                        qrStatus = "error",
                        error = it.strings["qr_status_error"]
                            ?: "Couldn't render QR. Tap Refresh or paste the link.",
                    )
                }
                return@launch
            }
            _state.update {
                it.copy(
                    qrSessionId = init.sessionId,
                    qrUrl = init.qrUrl,
                    qrImage = image,
                    qrStatus = "pending",
                    error = null,
                )
            }
            val deadline = System.currentTimeMillis() + init.ttlSeconds * 1000L
            while (isActive && _state.value.step == WidgetStep.QrCode) {
                if (System.currentTimeMillis() >= deadline) {
                    _state.update { it.copy(qrStatus = "expired") }
                    break
                }
                val poll = runCatching { appState.api.qrLoginPoll(init.sessionId) }.getOrNull()
                when (poll) {
                    is ApiClient.QrPollResult.Approved -> {
                        appState.telemetry.track("widget.qr_approved", mapOf("sdk" to "android"))
                        persistAndComplete(poll.success)
                        return@launch
                    }
                    ApiClient.QrPollResult.Expired -> {
                        _state.update { it.copy(qrStatus = "expired") }
                        break
                    }
                    else -> { /* pending — keep polling */ }
                }
                delay(2_000)
            }
        }
    }

    // ---------------------------------------------------------------- helpers

    private fun continueRememberedInstant(last: SecureStorage.LastAccount) {
        loadingJob?.cancel()
        loadingFromStep = WidgetStep.ReturningUser
        _state.update {
            it.copy(step = WidgetStep.Loading(it.strings["loading_signing"] ?: "Signing in…"), email = last.email, password = "", code = "", error = null)
        }
        loadingJob = viewModelScope.launch {
            runCatching {
                withTimeout(LOGIN_TIMEOUT_MS) {
                    rememberedSessionSuccess(last)
                }
            }.onSuccess { success ->
                if (success != null) {
                    appState.telemetry.track("widget.remembered_instant_success")
                    persistAndComplete(success)
                } else {
                    requestRememberedEmailCode(last, cancelCurrent = false)
                }
            }.onFailure { e ->
                val err = normaliseError(e)
                if (err is TpidError.InvalidCredentials || err is TpidError.OAuthError) {
                    appState.storage.clearTokens()
                    requestRememberedEmailCode(last, cancelCurrent = false)
                } else {
                    showReturningError(err)
                }
            }
        }
    }

    private fun requestRememberedEmailCode(last: SecureStorage.LastAccount, cancelCurrent: Boolean = true) {
        if (cancelCurrent) loadingJob?.cancel()
        loadingFromStep = WidgetStep.ReturningUser
        _state.update {
            it.copy(step = WidgetStep.Loading(it.strings["loading_sending"] ?: "Sending code…"), email = last.email, password = "", code = "", error = null)
        }
        loadingJob = viewModelScope.launch {
            runCatching {
                withTimeout(LOGIN_TIMEOUT_MS) {
                    appState.api.requestEmailCode(last.email, appState.config.clientId, "login")
                }
            }.onSuccess {
                _state.update { it.copy(step = WidgetStep.EmailCode, email = last.email, password = "", code = "", error = null) }
                appState.telemetry.track("widget.step_shown", mapOf("step" to "email_code", "source" to "last_account"))
            }.onFailure { e ->
                showReturningError(normaliseError(e))
            }
        }
    }

    private suspend fun rememberedSessionSuccess(last: SecureStorage.LastAccount): TpidResult.Success? {
        val tokens = appState.storage.readTokens() ?: return null
        val user = tokens.user
        if (!user?.email.equals(last.email, ignoreCase = true)) return null
        val now = System.currentTimeMillis()
        val usable = if (tokens.expiresAtMs > now + 30_000) {
            tokens
        } else {
            val rt = tokens.refreshToken ?: return null
            appState.api.refreshToken(rt, appState.config.clientId)
        }
        return tokensToSuccess(usable, last)
    }

    private fun tokensToSuccess(tokens: SecureStorage.Tokens, last: SecureStorage.LastAccount): TpidResult.Success {
        val user = tokens.user?.takeIf { it.email.isNotBlank() } ?: space.tokenpay.id.TpidUser(
            id = "",
            email = last.email,
            emailVerified = true,
            name = last.displayName,
            avatarUrl = last.avatarUrl,
            locale = null,
            has2fa = false,
            hasPasskey = false,
            createdAt = "",
        )
        val expiresIn = ((tokens.expiresAtMs - System.currentTimeMillis()) / 1000L).coerceAtLeast(1L)
        return TpidResult.Success(
            accessToken = tokens.accessToken,
            refreshToken = tokens.refreshToken,
            idToken = tokens.idToken,
            expiresIn = expiresIn,
            tokenType = "Bearer",
            scope = tokens.scope,
            user = user,
        )
    }

    private fun normaliseError(e: Throwable): TpidError = when (e) {
        is TpidError -> e
        is TimeoutCancellationException -> TpidError.Timeout
        else -> TpidError.Unknown(e)
    }

    private fun showReturningError(err: TpidError) {
        _state.update {
            val msg = when (err) {
                is TpidError.Timeout -> it.strings["err_title_timeout"] ?: "Request timed out"
                is TpidError.NoNetwork -> it.strings["err_title_network"] ?: "No network"
                is TpidError.ServerUnavailable -> it.strings["err_title_server"] ?: "Server unavailable"
                is TpidError.TlsFailure -> it.strings["err_title_tls"] ?: "TLS connection failed"
                is TpidError.StorageFailure -> it.strings["err_title_storage"] ?: "Local storage failed"
                else -> err.message
            }
            it.copy(step = WidgetStep.ReturningUser, error = msg)
        }
        appState.telemetry.track("widget.step_submit_error", mapOf("step" to "returning_user", "code" to err.code))
    }

    private fun persistAndComplete(success: TpidResult.Success) {
        appState.storage.clearPkce()
        appState.storage.writeTokens(
            SecureStorage.Tokens(
                accessToken = success.accessToken,
                refreshToken = success.refreshToken,
                idToken = success.idToken,
                expiresAtMs = System.currentTimeMillis() + success.expiresIn * 1000L,
                scope = success.scope,
                userDto = SecureStorage.Tokens.TpidUserDto.from(success.user),
            )
        )
        // 2.6.0: persist a minimal profile for the "Continue as X" welcome
        // screen. Deliberately decoupled from [writeTokens] so an explicit
        // sign-out can wipe the session while keeping the friendly greeting.
        appState.storage.writeLastAccount(
            email = success.user.email,
            name = success.user.name?.takeIf { it.isNotBlank() },
            avatarUrl = success.user.avatarUrl?.takeIf { it.isNotBlank() },
        )
        // U2 fix: remember this session so system-back / close after Success
        // resolves to RESULT_OK, not Cancelled. ViewModelScope outlives the
        // 700 ms delay below — so there is NO `LaunchedEffect` cancellation
        // window that could swallow the callback. This is the Android
        // analogue of the JVM `pendingSuccess + LaunchedEffect` pattern.
        lastSuccess = success
        _state.update { it.copy(step = WidgetStep.Success, error = null) }
        appState.telemetry.track("widget.closed_success", mapOf("user_id" to success.user.id.takeLast(8)))
        viewModelScope.launch {
            kotlinx.coroutines.delay(700)
            onComplete(success)
        }
    }

    private fun stepName(s: WidgetStep): String = when (s) {
        WidgetStep.Welcome -> "welcome"
        WidgetStep.ReturningUser -> "returning_user"
        WidgetStep.Email -> "email"
        WidgetStep.Password -> "password"
        WidgetStep.EmailCode -> "email_code"
        WidgetStep.TwoFactor -> "2fa"
        WidgetStep.Passkey -> "passkey"
        WidgetStep.QrCode -> "qr"
        WidgetStep.Recovery -> "recovery"
        is WidgetStep.Register -> "register"
        is WidgetStep.Loading -> "loading"
        WidgetStep.Success -> "success"
        is WidgetStep.ErrorFatal -> "error_fatal"
    }

    private val emailRegex = Regex("^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$")
    private fun isValidEmail(e: String) = emailRegex.matches(e)

    // ------------------------------------------------------------ 2.6.1
    // Smart update driver: pulls the tarball via [TpidUpdater] and maps
    // every [TpidUpdater.Phase] onto the banner's observable [UpdaterState].
    // The banner in WidgetActivity listens to state.updater and drives
    // its animated morph from that — no direct coupling.
    // ------------------------------------------------------------
    private var updateJob: kotlinx.coroutines.Job? = null
    private val updater by lazy {
        TpidUpdater(
            context = appState.appContext,
            api = appState.api,
            clientId = appState.config.clientId,
        )
    }

    /**
     * 2.6.2 — User-facing "Update" click handler.
     *
     * Returns the URL the host activity should launch with
     * `Intent.ACTION_VIEW` so the user lands on the Play Store / docs page
     * where they can actually install the new version. Android Play
     * policy forbids replacing our own DEX at runtime, so the older
     * [startSmartUpdate] silently downloaded a tarball into private
     * cache — invisible to the user, who reasonably perceived "I clicked
     * Update and nothing changed". Now the click goes to the browser
     * (honest, actionable) and the banner auto-dismisses for the rest of
     * the session so it doesn't badger the user after they've been
     * redirected.
     *
     * The smart-update behaviour (config refresh + tarball pre-fetch) is
     * still available via [startSmartUpdate] for integrators who want to
     * pre-stage the artefact in their own update pipeline.
     */
    fun requestUpdateOpen(): String {
        val s0 = _state.value
        val latest = remote.recommendedSdkVersion ?: s0.sdkVersion
        // 2.6.2 — Prefer the human-friendly install page over the raw
        // tarball URL the server advertises in `remote.download_url` —
        // that field points at e.g. `.../tokenpay-id-android-2.6.2.tar.gz`,
        // which is the artefact our smart-update fetches programmatically
        // but is useless to a phone user (they'd get a 300 KB binary file
        // dumped into Downloads with no install instructions). When the
        // server *does* publish a non-artefact URL (e.g. a Play Store
        // listing) we honour it instead.
        val rawDl = remote.downloadUrl?.takeIf { it.isNotBlank() }
            ?: s0.updateDownloadUrl?.takeIf { it.isNotBlank() }
        val artefactExt = Regex(".+\\.(tar\\.gz|tgz|zip|aar|apk)(\\?.*)?$", RegexOption.IGNORE_CASE)
        val url = when {
            rawDl == null -> "https://tokenpay.space/sdk#android"
            artefactExt.matches(rawDl) -> "https://tokenpay.space/sdk#android"
            else -> rawDl
        }
        updateBannerDismissedThisSession = true
        _state.update {
            it.copy(
                showUpdateBanner = false,
                updater = it.updater.copy(state = UpdateBannerPhase.Idle),
            )
        }
        appState.telemetry.track(
            "widget.update_open_url",
            mapOf("sdk" to "android", "from" to s0.sdkVersion, "to" to latest, "url" to url),
        )
        // Pre-fetch fresh server config in the background so any string /
        // theme / feature-flag updates apply live for the rest of this
        // session — no user-visible spinner, no banner thrash.
        viewModelScope.launch(Dispatchers.IO) {
            runCatching {
                RemoteConfig.invalidateCache()
                val r = RemoteConfig.fetch(appState.api, appState.config.clientId)
                remote = r
                _state.update { cur -> cur.copy(strings = mergeStrings(cur.language, r)) }
            }
        }
        return url
    }

    /**
     * Kick off (or retry) an in-place smart update. Safe to call repeatedly —
     * any in-flight update is cancelled first so the banner can't split
     * into two phase streams.
     */
    fun startSmartUpdate() {
        updateJob?.cancel()
        val s0 = _state.value
        val latest = remote.recommendedSdkVersion ?: s0.sdkVersion
        _state.update {
            it.copy(
                updater = it.updater.copy(
                    state = UpdateBannerPhase.Running,
                    phaseText = it.strings["update_checking"] ?: "Checking for updates…",
                    progress = 0.03f,
                    indeterminate = true,
                    latestVersion = latest,
                ),
            )
        }
        appState.telemetry.track(
            "widget.update_started",
            mapOf("sdk" to "android", "from" to s0.sdkVersion, "to" to latest),
        )
        updateJob = viewModelScope.launch(Dispatchers.IO) {
            val terminal = updater.performUpdate { phase ->
                // Invoked on whichever thread the updater is driving from;
                // `_state.update` is thread-safe (MutableStateFlow).
                val t = _state.value.strings
                val ui = mapPhaseToUi(phase, latest, t)
                _state.update { it.copy(updater = it.updater.copy(
                    phaseText = ui.text,
                    progress = ui.progress,
                    indeterminate = ui.indeterminate,
                )) }
            }
            when (terminal) {
                is TpidUpdater.Phase.Done -> {
                    // Fresh config applies live — strings / theme / flags
                    // refresh in the running widget without a restart.
                    remote = terminal.newConfig
                    _state.update { cur ->
                        cur.copy(
                            strings = mergeStrings(cur.language, terminal.newConfig),
                            updateDownloadUrl = terminal.newConfig.downloadUrl,
                            // Server no longer considers us stale: either we
                            // downloaded a fresh tarball or the config
                            // refresh reset the recommended version.
                            showUpdateBanner = false,
                            updater = cur.updater.copy(state = UpdateBannerPhase.Done),
                        )
                    }
                    appState.telemetry.track(
                        "widget.update_done",
                        mapOf("sdk" to "android", "version" to latest),
                    )
                }
                is TpidUpdater.Phase.Failed -> {
                    _state.update {
                        it.copy(updater = it.updater.copy(state = UpdateBannerPhase.Failed))
                    }
                    appState.telemetry.track(
                        "widget.update_failed",
                        mapOf("sdk" to "android", "reason" to terminal.reason),
                    )
                }
                else -> { /* non-terminal — not reachable, compiler-exhaustiveness only */ }
            }
        }
    }

    /** Collapse a finished banner (called from the Compose auto-dismiss). */
    fun dismissUpdaterBanner() {
        _state.update { it.copy(updater = UpdaterState()) }
    }

    private data class UpdaterUi(
        val text: String,
        val progress: Float,
        val indeterminate: Boolean,
    )

    private fun mapPhaseToUi(
        phase: TpidUpdater.Phase,
        latest: String,
        t: Map<String, String>,
    ): UpdaterUi = when (phase) {
        is TpidUpdater.Phase.Checking -> UpdaterUi(
            t["update_checking"] ?: "Checking for updates…", 0.03f, true,
        )
        is TpidUpdater.Phase.Downloading -> {
            val ratio = if (phase.total > 0L) phase.bytes.toFloat() / phase.total else -1f
            val indet = ratio < 0f
            val mb = humanBytes(phase.bytes)
            val text = if (indet) {
                (t["update_downloading_unknown"] ?: "Downloading %1\$s…")
                    .replace("%1\$s", mb)
            } else {
                val total = humanBytes(phase.total)
                (t["update_downloading"] ?: "Downloading %1\$s / %2\$s")
                    .replace("%1\$s", mb)
                    .replace("%2\$s", total)
            }
            UpdaterUi(
                text = text,
                progress = if (indet) 0f else 0.05f + 0.70f * ratio.coerceIn(0f, 1f),
                indeterminate = indet,
            )
        }
        is TpidUpdater.Phase.Verifying -> UpdaterUi(
            t["update_verifying"] ?: "Verifying download…", 0.80f, false,
        )
        is TpidUpdater.Phase.Installing -> UpdaterUi(
            t["update_installing"] ?: "Installing…", 0.90f, false,
        )
        is TpidUpdater.Phase.RefreshingConfig -> UpdaterUi(
            t["update_refreshing"] ?: "Applying new settings…", 0.96f, false,
        )
        is TpidUpdater.Phase.Done -> UpdaterUi(
            (t["update_done"] ?: "Updated to %1\$s").replace("%1\$s", latest),
            1f, false,
        )
        is TpidUpdater.Phase.Failed -> UpdaterUi(
            (t["update_failed"] ?: "Update failed — please try again."),
            0f, false,
        )
    }

    private fun humanBytes(n: Long): String {
        if (n < 0) return ""
        if (n < 1024) return "$n B"
        val kb = n / 1024.0
        if (kb < 1024.0) return String.format(java.util.Locale.ROOT, "%.1f KB", kb)
        val mb = kb / 1024.0
        if (mb < 1024.0) return String.format(java.util.Locale.ROOT, "%.1f MB", mb)
        val gb = mb / 1024.0
        return String.format(java.util.Locale.ROOT, "%.2f GB", gb)
    }

    companion object {
        /**
         * 2.6.2 — Hard ceiling on every user-visible network request from
         * the widget. Slightly tighter than the old [ApiClient] 30 s
         * `callTimeout`: on flaky mobile networks the user sees a friendly
         * "Request timed out" within 18 s instead of staring at an
         * infinite spinner ([WidgetViewModel.failLogin] maps the
         * resulting [TimeoutCancellationException] to [TpidError.Timeout]).
         */
        internal const val LOGIN_TIMEOUT_MS: Long = 18_000
        private const val REMEMBER_INSTANT_MS: Long = 24L * 60L * 60L * 1000L
        private const val REMEMBER_EMAIL_CODE_MS: Long = 7L * 24L * 60L * 60L * 1000L

        fun factory(
            appState: TpidAuth.State,
            prefillEmail: String?,
            onComplete: (TpidResult) -> Unit,
        ) = object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T =
                WidgetViewModel(appState, prefillEmail, onComplete) as T
        }
    }
}

/** Observable state of the widget. */
internal data class WidgetState(
    val step: WidgetStep,
    val email: String = "",
    val password: String = "",
    val code: String = "",
    val totp: String = "",
    val branding: TpidConfig.Branding? = null,
    val antiPhishingDomain: String = "",
    val tlsPinned: Boolean = true,
    val error: String? = null,
    val accountInfo: space.tokenpay.id.internal.ApiClient.AccountCheckResponse? = null,
    val twoFactorMethods: List<String> = emptyList(),
    val language: TpidConfig.Language = TpidConfig.Language.ENGLISH,
    val strings: Map<String, String> = emptyMap(),
    /** `true` when the server reports a newer SDK than [BuildConfig.TPID_SDK_VERSION]. */
    val showUpdateBanner: Boolean = false,
    /** 2.6.0 — where the update banner's pill button should open. */
    val updateDownloadUrl: String? = null,
    // Sign-up form state — lives on the widget-level state so configuration
    // changes (rotation, process-death) survive without user retyping.
    val regUsername: String = "",
    val regPassword: String = "",
    val regCode: String = "",
    // QR login state (null unless the widget is / has been on the QR step).
    val qrSessionId: String? = null,
    val qrUrl: String? = null,
    val qrImage: ImageBitmap? = null,
    /** "loading" | "pending" | "approved" | "expired" | "error". */
    val qrStatus: String = "loading",
    /**
     * 2.6.0 — last-used account profile, if any. Loaded from [SecureStorage]
     * on widget init; non-null means the widget opens on
     * [WidgetStep.ReturningUser] with a "Continue as X" card.
     */
    val lastAccount: SecureStorage.LastAccount? = null,
    /**
     * 2.6.1 — Currently running SDK version, cached here so the banner can
     * show "Updated to 2.6.1" in its done state without a second lookup.
     * Defaults to [BuildConfig.TPID_SDK_VERSION] at construction time.
     */
    val sdkVersion: String = space.tokenpay.id.BuildConfig.TPID_SDK_VERSION,
    /**
     * 2.6.1 — Observable state of the smart-update banner.
     *
     * Separated from [showUpdateBanner] (which only reflects whether the
     * server advertised a newer SDK) because the banner stays visible
     * through every post-click transition — Running, Done, Failed — even
     * after we've locally "forgotten" that the server considered us stale.
     */
    val updater: UpdaterState = UpdaterState(),
)

/**
 * 2.6.1 — Observable progress state for the in-widget updater.
 *
 * Lives on [WidgetState] so the Compose banner is a pure projection of it.
 * The VM owns the only mutator ([WidgetViewModel.startSmartUpdate]); the
 * banner feeds UI events via callbacks (`onStart` / `onAutoDismiss`).
 */
internal data class UpdaterState(
    val state: UpdateBannerPhase = UpdateBannerPhase.Idle,
    /** Short progress label rendered to the left of the pill. */
    val phaseText: String = "",
    /** [0,1] determinate progress, ignored when [indeterminate] is true. */
    val progress: Float = 0f,
    /** True while the caller doesn't know the final download size. */
    val indeterminate: Boolean = true,
    /** Version the updater is pulling to; used for the `doneText` format. */
    val latestVersion: String? = null,
)

internal sealed class WidgetStep {
    data object Welcome : WidgetStep()
    /**
     * 2.6.0 — account-memory welcome card. Shown when
     * [SecureStorage.readLastAccount] returned a non-null profile.
     * Primary CTA: "Continue as <name/email>" (→ Password). Secondary:
     * "Use another account" (→ Email). Tertiary: "Forget this account".
     */
    data object ReturningUser : WidgetStep()
    data object Email : WidgetStep()
    data object Password : WidgetStep()
    data object EmailCode : WidgetStep()
    data object TwoFactor : WidgetStep()
    data object Passkey : WidgetStep()
    data object Recovery : WidgetStep()
    /**
     * QR login screen — the widget renders the QR returned by
     * `/auth/qr/login-init` and polls `login-poll/:sessionId` until the
     * phone confirms.
     */
    data object QrCode : WidgetStep()
    /**
     * Sign-up screen — see JVM counterpart. [codeSent] flips to `true`
     * once the user has received the verification e-mail.
     */
    data class Register(val codeSent: Boolean = false) : WidgetStep()
    data class Loading(val message: String) : WidgetStep()
    data object Success : WidgetStep()
    data class ErrorFatal(val error: TpidError) : WidgetStep()
}
