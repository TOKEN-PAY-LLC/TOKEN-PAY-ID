package space.tokenpay.id.jvm

import androidx.compose.animation.*
import androidx.compose.animation.core.*
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.hoverable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsHoveredAsState
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Close
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.DialogWindow
import androidx.compose.ui.window.WindowPosition
import androidx.compose.ui.window.rememberDialogState
import androidx.compose.ui.graphics.ImageBitmap
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import space.tokenpay.id.jvm.internal.ApiClient
import space.tokenpay.id.jvm.internal.PkceUtils
import space.tokenpay.id.jvm.internal.QrRenderer
import space.tokenpay.id.jvm.internal.RemoteConfig
import space.tokenpay.id.jvm.internal.SdkBuildInfo
import space.tokenpay.id.jvm.internal.SecureStorage
import space.tokenpay.id.jvm.internal.Strings
import space.tokenpay.id.jvm.internal.TpidUpdater
import java.awt.Desktop
import java.net.URI
import java.util.concurrent.TimeUnit

private const val REMEMBER_INSTANT_MS: Long = 24L * 60L * 60L * 1000L
private const val REMEMBER_EMAIL_CODE_MS: Long = 7L * 24L * 60L * 60L * 1000L

/**
 * Separate (undecorated) dialog window rendering the TPID widget.
 *
 * The OS-native title bar is intentionally hidden: the widget paints its own
 * top row (close / back / language) matching the web widget exactly.
 */
@Composable
internal fun TpidWidgetDialog(onResult: (TpidResult) -> Unit) {
    // A wider desktop dialog keeps account and action rows readable. The
    // toolbar is top-aligned; long registration steps scroll within the card.
    val state = rememberDialogState(
        width = 480.dp, height = 540.dp,
        position = WindowPosition(Alignment.Center),
    )
    val scope = rememberCoroutineScope()
    val stateOrError: Any = remember { runCatching { TpidAuth.requireState() }.getOrElse { it } }

    when (stateOrError) {
        is TpidError -> FatalDialog(state, stateOrError, onResult)
        is TpidAuth.State -> {
            val theme = stateOrError.config.theme
            // Remote config: fire once per widget launch, apply overrides when
            // the value arrives. Never blocks first paint.
            var remote by remember { mutableStateOf(RemoteConfig()) }
            LaunchedEffect(stateOrError.config.clientId) {
                runCatching {
                    remote = RemoteConfig.fetch(stateOrError.api, stateOrError.config.clientId)
                }
                runCatching {
                    stateOrError.api.refreshPins(stateOrError.api.fetchTlsPins())
                }
            }
            DialogWindow(
                onCloseRequest = { onResult(TpidResult.Cancelled) },
                state = state,
                title = "TOKEN PAY ID",
                resizable = false,
                undecorated = true,
                transparent = true,
            ) {
                val dark = when (theme) {
                    TpidConfig.Theme.DARK -> true
                    TpidConfig.Theme.LIGHT -> false
                    TpidConfig.Theme.AUTO -> remember { isSystemDark() }
                }
                val baseScheme = if (dark) darkColorSchemeTpid() else lightColorSchemeTpid()
                val scheme = applyThemeTokens(baseScheme, remote.themeTokens, dark)
                MaterialTheme(
                    colorScheme = scheme,
                    typography = tpidTypography(),
                ) {
                    RootSurface(dark = dark) {
                        WidgetContent(
                            appState = stateOrError,
                            remote = remote,
                            onRemoteUpdated = { remote = it },
                            scope = scope,
                            onResult = onResult,
                        )
                    }
                }
            }
        }
    }
}

/**
 * Merge remote `theme_tokens` into a locally-built [ColorScheme]. Only the
 * keys we consciously allow flow through so an integrator can't accidentally
 * break contrast by handing us a 12-hex-string payload.
 */
private fun applyThemeTokens(
    base: ColorScheme,
    tokens: Map<String, String>,
    dark: Boolean,
): ColorScheme {
    if (tokens.isEmpty()) return base
    val keyPrefix = if (dark) "dark." else "light."
    fun pick(key: String): Color? {
        val v = tokens[keyPrefix + key] ?: tokens[key] ?: return null
        return runCatching { Color(java.lang.Long.parseLong(v.removePrefix("#"), 16) or 0xFF000000L) }.getOrNull()
    }
    return base.copy(
        primary          = pick("primary")          ?: base.primary,
        onPrimary        = pick("on_primary")       ?: base.onPrimary,
        background       = pick("background")       ?: base.background,
        onBackground     = pick("on_background")    ?: base.onBackground,
        surface          = pick("surface")          ?: base.surface,
        onSurface        = pick("on_surface")       ?: base.onSurface,
        surfaceVariant   = pick("surface_variant")  ?: base.surfaceVariant,
        onSurfaceVariant = pick("on_surface_variant") ?: base.onSurfaceVariant,
        outline          = pick("outline")          ?: base.outline,
        error            = pick("error")            ?: base.error,
    )
}

/**
 * Root surface of the widget window. Paints the ONE soft-rounded card the
 * user sees — matte solid colour, 1dp hairline border, 24dp drop shadow.
 *
 * Pre-2.5.0-pre.3 this composable painted an outer gradient rectangle AND
 * the `WidgetContent` below added a second shadow + border + background
 * Column inside it, producing a visibly smaller card with a dead frame
 * around it. In 2.5.0-pre.3 the window IS the card — no inner chrome, no
 * dead space, same rounded edges across Android, iOS and JVM.
 */
@Composable
private fun RootSurface(dark: Boolean, content: @Composable () -> Unit) {
    val card   = if (dark) Color(0xFF0E0E11) else Color.White
    val border = if (dark) Color.White.copy(alpha = 0.08f) else Color(0x14000000)
    Box(
        modifier = Modifier
            .fillMaxSize()
            .padding(4.dp) // breathing room for the drop-shadow
            .shadow(elevation = 24.dp, shape = RoundedCornerShape(22.dp), clip = false)
            .clip(RoundedCornerShape(22.dp))
            .background(card)
            .border(1.dp, border, RoundedCornerShape(22.dp)),
    ) {
        content()
    }
}

private fun lightColorSchemeTpid() = lightColorScheme(
    primary           = Color(0xFF0B0B0D),
    onPrimary         = Color.White,
    secondary         = Color(0xFF2E2E38),
    onSecondary       = Color.White,
    background        = Color(0xFFF5F5F7),
    onBackground      = Color(0xFF0B0B0D),
    surface           = Color.White,
    onSurface         = Color(0xFF0B0B0D),
    surfaceVariant    = Color(0xFFEEEEF0),
    onSurfaceVariant  = Color(0xFF55555A),
    outline           = Color(0xFFDCDCE0),
    // 2.6.0 strict-monochrome: `error` mirrors `onBackground` so the
    // Material default error-surface pipeline stays on the B&W palette.
    error             = Color(0xFF0B0B0D),
    onError           = Color.White,
)

private fun darkColorSchemeTpid() = darkColorScheme(
    primary           = Color.White,
    onPrimary         = Color(0xFF0B0B0D),
    secondary         = Color(0xFFE1E1E6),
    onSecondary       = Color(0xFF0B0B0D),
    background        = Color(0xFF050507),
    onBackground      = Color(0xFFF5F5F7),
    surface           = Color(0xFF0E0E11),
    onSurface         = Color(0xFFF5F5F7),
    surfaceVariant    = Color(0xFF14141A),
    onSurfaceVariant  = Color(0xFFB3B3BA),
    outline           = Color(0xFF2A2A31),
    // 2.6.0 strict-monochrome: `error` mirrors `onBackground` on dark.
    error             = Color(0xFFF5F5F7),
    onError           = Color(0xFF0B0B0D),
)

private fun isSystemDark(): Boolean {
    if (System.getProperty("os.name", "").startsWith("Windows", ignoreCase = true)) {
        val windowsDark = runCatching {
            val process = ProcessBuilder(
                "reg", "query",
                "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize",
                "/v", "AppsUseLightTheme",
            ).redirectErrorStream(true).start()
            if (!process.waitFor(1, TimeUnit.SECONDS)) {
                process.destroyForcibly()
                null
            } else {
                Regex("AppsUseLightTheme\\s+REG_DWORD\\s+0x([0-9a-fA-F]+)")
                    .find(process.inputStream.bufferedReader().readText())
                    ?.groupValues?.get(1)?.toInt(16) == 0
            }
        }.getOrNull()
        if (windowsDark != null) return windowsDark
    }
    val theme = System.getenv("GTK_THEME") ?: ""
    if (theme.contains("dark", ignoreCase = true)) return true
    // macOS "AppleInterfaceStyle" env var set by Dock notifications — best effort.
    val mac = System.getenv("AppleInterfaceStyle") ?: ""
    if (mac.equals("Dark", ignoreCase = true)) return true
    return false
}

@Composable
internal fun FatalDialog(state: androidx.compose.ui.window.DialogState, e: TpidError, onResult: (TpidResult) -> Unit) {
    DialogWindow(
        onCloseRequest = { onResult(TpidResult.Failure(e)) },
        state = state,
        title = "TOKEN PAY ID — Error",
        resizable = false,
        undecorated = true,
        transparent = true,
    ) {
        MaterialTheme(typography = tpidTypography()) {
            RootSurface(dark = true) {
                Column(
                    modifier = Modifier.fillMaxSize().padding(24.dp),
                    verticalArrangement = Arrangement.Center,
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    Text("Configuration error", fontSize = 20.sp, fontWeight = FontWeight.Bold, color = Color.White)
                    Spacer(Modifier.height(8.dp))
                    Text(e.message ?: e.code, fontSize = 13.sp, color = Color.White.copy(alpha = 0.7f))
                    Spacer(Modifier.height(24.dp))
                    Button(onClick = { onResult(TpidResult.Failure(e)) }) { Text("Close") }
                }
            }
        }
    }
}

@OptIn(ExperimentalAnimationApi::class)
@Composable
private fun WidgetContent(
    appState: TpidAuth.State,
    remote: RemoteConfig,
    onRemoteUpdated: (RemoteConfig) -> Unit,
    scope: CoroutineScope,
    onResult: (TpidResult) -> Unit,
) {
    val configLang = remember(appState) {
        TpidConfig.Language.fromCode(appState.config.language)
    }
    var language by remember { mutableStateOf(Strings.resolveLanguage(configLang)) }
    // Merge remote per-language overrides on top of the local defaults so a
    // remotely-pushed string wins.
    val t by remember(language, remote) {
        derivedStateOf {
            val base = Strings.of(language)
            val code = when (language) {
                TpidConfig.Language.RUSSIAN -> "ru"
                TpidConfig.Language.CHINESE -> "zh"
                else -> "en"
            }
            val overrides = remote.stringsOverride[code].orEmpty()
            if (overrides.isEmpty()) base else base + overrides
        }
    }
    // -----------------------------------------------------------------
    // 2.6.1 — Smart update state machine.
    //
    // The banner is visible whenever either (a) the server reports a
    // newer recommended/min SDK version, or (b) the user is currently
    // running an update / just finished one. The state machine is owned
    // here so we can auto-dismiss from Done and survive recompositions.
    // -----------------------------------------------------------------
    var serverSaysOlder by remember(remote) {
        mutableStateOf(
            remote.isOlderThan(remote.recommendedSdkVersion) ||
                remote.isOlderThan(remote.minSdkVersion)
        )
    }
    var updaterState by remember { mutableStateOf(UpdateBannerState.Idle) }
    var updaterUi by remember { mutableStateOf(UpdaterUiState("", 0f, true)) }
    val showUpdateBanner = serverSaysOlder || updaterState != UpdateBannerState.Idle

    val prefilled = !appState.config.prefillEmail.isNullOrBlank()
    // 2.6.0: read the remembered account profile so the widget can open with
    // a "Continue as X" card instead of an empty email field each time.
    val rememberedAccount = remember {
        if (prefilled) null else runCatching { appState.storage.readLastAccount() }.getOrNull()
    }
    var lastAccount by remember { mutableStateOf(rememberedAccount) }
    val initialStep: WidgetStep = when {
        prefilled -> WidgetStep.Email
        rememberedAccount != null -> WidgetStep.ReturningUser
        else -> WidgetStep.Welcome
    }
    var step by remember { mutableStateOf<WidgetStep>(initialStep) }
    var email by remember {
        mutableStateOf(appState.config.prefillEmail ?: rememberedAccount?.email ?: "")
    }
    var password by remember { mutableStateOf("") }
    var emailCode by remember { mutableStateOf("") }
    var totp by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }
    // Tracks whether the latest accountCheck reported the address as an existing
    // account. The server's /auth/send-code endpoint requires a `type` field,
    // and "login" for a non-existent account produces `404 Email not registered`.
    var accountExists by remember { mutableStateOf(false) }

    val scroll = rememberScrollState()

    // Sign-up form fields — scoped here so they survive recomposition but get
    // wiped when the user bounces back to Email. The username filter mirrors
    // the server's regex `^[a-z0-9._]{3,30}$` so the widget never sends a
    // payload that `/auth/register` would reject with `invalid_username`.
    var regUsername by remember { mutableStateOf("") }
    var regPassword by remember { mutableStateOf("") }
    var regCode by remember { mutableStateOf("") }

    // QR login state — lives at the widget level so going back to Welcome
    // and re-entering cancels the poll and starts a fresh session.
    var qrInit by remember { mutableStateOf<ApiClient.QrInit?>(null) }
    var qrImage by remember { mutableStateOf<ImageBitmap?>(null) }
    var qrStatus by remember { mutableStateOf("loading") } // loading | pending | approved | expired | error
    var qrRefreshTick by remember { mutableStateOf(0) }

    // B1 (pre.9 → 2.6.0): pending success token, captured at the moment the
    // backend returned a valid session and persisted through the Success
    // screen. Resolved by a single top-level `LaunchedEffect` below, not a
    // per-callback `scope.launch { delay; onResult(...) }` (which got
    // cancelled by recomposition once `step` flipped to `Success` and the
    // containing composable left the tree).
    var pendingSuccess by remember { mutableStateOf<TpidSession?>(null) }
    LaunchedEffect(pendingSuccess) {
        val s = pendingSuccess ?: return@LaunchedEffect
        // 2.6.0 — write the minimal "remembered account" profile so the
        // next open shows "Continue as X". Separate slot from the session
        // token so a plain sign-out does NOT erase the friendly greeting.
        runCatching {
            appState.storage.writeLastAccount(
                email = s.user.email,
                displayName = s.user.name?.takeIf { it.isNotBlank() },
                avatarUrl = s.user.avatarUrl?.takeIf { it.isNotBlank() },
            )
        }
        // Let the SuccessStep paint for ~600 ms so the user sees the final
        // state, then hand control back to the integrator. Because this
        // LaunchedEffect's key never flips back to `null` once set, there
        // is no recomposition branch that can cancel it before `onResult`.
        kotlinx.coroutines.delay(600)
        onResult(TpidResult.Success(s))
    }

    val goBack: () -> Unit = goBack@{
        // U2 — once a session was persisted, treat a system-close after
        // Success as a successful result, not Cancelled.
        val pending = pendingSuccess
        if (step is WidgetStep.Success && pending != null) {
            onResult(TpidResult.Success(pending))
            return@goBack
        }
        when (step) {
            WidgetStep.Email -> {
                // 2.6.0: if we came from the remembered-user card, go back
                // to it rather than Welcome — the remembered account is
                // still the default, not a dead end.
                step = if (lastAccount != null) WidgetStep.ReturningUser else WidgetStep.Welcome
                error = null
            }
            WidgetStep.Password, WidgetStep.EmailCode, WidgetStep.TwoFactor, WidgetStep.Passkey -> {
                val back = if (lastAccount != null && email == lastAccount?.email) {
                    WidgetStep.ReturningUser
                } else {
                    WidgetStep.Email
                }
                step = back; password = ""; emailCode = ""; totp = ""; error = null
            }
            is WidgetStep.Register -> {
                step = WidgetStep.Email
                regUsername = ""; regPassword = ""; regCode = ""; error = null
            }
            WidgetStep.QrCode -> {
                // Cancel the active QR poll via state reset; the LaunchedEffect
                // keyed on [step] will stop re-invoking the server.
                step = if (lastAccount != null) WidgetStep.ReturningUser else WidgetStep.Welcome
                qrInit = null; qrImage = null
                qrStatus = "loading"; error = null
            }
            else -> onResult(TpidResult.Cancelled)
        }
    }

    // No per-content card chrome — `RootSurface` already paints the rounded
    // card, border and drop-shadow for the whole window. `Alignment.Center`
    // Keep the toolbar at the top. Centering the entire column put the close
    // button in the middle of a tall blank window on short steps.
    val isDark = MaterialTheme.colorScheme.background.luminance() < 0.5f
    Box(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(scroll)
            .padding(horizontal = 24.dp, vertical = 14.dp),
        contentAlignment = Alignment.TopCenter,
    ) {
        Column(
            modifier = Modifier.fillMaxWidth(),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            // Top bar: back + language + close
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                val showBack = step !is WidgetStep.Welcome && step !is WidgetStep.Success && step !is WidgetStep.ReturningUser
                AnimatedVisibility(
                    visible = showBack,
                    enter = fadeIn(tween(180)) + scaleIn(tween(180), initialScale = 0.85f),
                    exit  = fadeOut(tween(120)) + scaleOut(tween(120), targetScale = 0.85f),
                ) {
                    TpidTopIconButton(
                        content = { Icon(Icons.Filled.ArrowBack, contentDescription = "Back", modifier = Modifier.size(18.dp)) },
                        onClick = goBack,
                    )
                }
                if (!showBack) Spacer(Modifier.size(36.dp))
                Spacer(Modifier.weight(1f))
                TpidLanguageChip(current = language, onChange = { language = it })
                Spacer(Modifier.width(8.dp))
                TpidTopIconButton(
                    content = { Icon(Icons.Filled.Close, contentDescription = "Close", modifier = Modifier.size(18.dp)) },
                    onClick = { onResult(TpidResult.Cancelled) },
                )
            }
            Spacer(Modifier.height(28.dp))
            TpidBrandHeader(appName = appState.config.brandingOverride?.appName ?: remote.clientName)
            Spacer(Modifier.height(28.dp))
            if (showUpdateBanner) {
                // A source SDK cannot replace the classes in a running host.
                // Open the release guide so the integrator can rebuild.
                val latestVer = remote.recommendedSdkVersion ?: SdkBuildInfo.version
                TpidUpdateBanner(
                    state = updaterState,
                    message = (t["update_available"]
                        ?: "A newer TOKEN PAY ID SDK is available — please update.") +
                        if (latestVer != SdkBuildInfo.version) " ($latestVer)" else "",
                    updateLabel = t["btn_download_sdk"] ?: "Open SDK",
                    retryLabel = t["btn_retry"] ?: "Retry",
                    doneText = t["update_done"]?.replace("%1\$s", latestVer)
                        ?: "Updated to $latestVer",
                    failedText = t["update_failed"] ?: "Update failed — please try again.",
                    phaseText = updaterUi.text,
                    progress = updaterUi.progress,
                    indeterminate = updaterUi.indeterminate,
                    onStart = {
                        openBrowser("https://tokenpay.space/sdk#jvm")
                        serverSaysOlder = false
                        updaterState = UpdateBannerState.Idle
                    },
                    onAutoDismiss = {
                        updaterState = UpdateBannerState.Idle
                    },
                )
                Spacer(Modifier.height(12.dp))
            }

            // Animated step transitions — every navigation between screens
            // fades and slides the content, so the widget feels alive instead
            // of switching instantly like the old version.
            AnimatedContent(
                targetState = step,
                transitionSpec = {
                    val forward = stepDirection(initialState, targetState)
                    val slide = if (forward) 24 else -24
                    (fadeIn(tween(220)) + slideInHorizontally(tween(260)) { slide })
                        .togetherWith(fadeOut(tween(160)) + slideOutHorizontally(tween(200)) { -slide })
                        .using(SizeTransform(clip = false))
                },
                label = "widget-step",
            ) { s ->
                when (s) {
                    WidgetStep.Welcome -> WelcomeStep(
                        t = t,
                        onSignIn = { step = WidgetStep.Email; error = null },
                        onCreateAccount = {
                            step = WidgetStep.Register(codeSent = false); error = null
                        },
                        onQr = {
                            qrInit = null; qrImage = null; qrStatus = "loading"
                            step = WidgetStep.QrCode; error = null
                        },
                    )
                    WidgetStep.ReturningUser -> ReturningUserStep(
                        t = t,
                        lastAccount = lastAccount,
                        error = error,
                        onContinue = {
                            val last = lastAccount ?: return@ReturningUserStep
                            email = last.email
                            password = ""
                            emailCode = ""
                            totp = ""
                            error = null
                            val ageMs = System.currentTimeMillis() - last.lastAuthenticatedAtMs
                            when {
                                last.lastAuthenticatedAtMs > 0L && ageMs in 0L..REMEMBER_INSTANT_MS -> {
                                    step = WidgetStep.Loading(t["loading_signing"] ?: "Signing in…")
                                    scope.launch {
                                        val instant = runCatching {
                                            val existing = appState.storage.readSession()
                                            require(existing?.user?.email?.equals(last.email, ignoreCase = true) == true) {
                                                "Saved session belongs to a different account"
                                            }
                                            if (existing != null && existing.isValid) existing
                                            else {
                                                val refresh = existing?.refreshToken ?: throw TpidError.InvalidCredentials("Session expired")
                                                val refreshed = appState.api.refreshToken(refresh, appState.config.clientId)
                                                val merged = if (refreshed.user.id.isEmpty()) refreshed.copy(user = existing.user) else refreshed
                                                appState.storage.writeSession(merged)
                                                merged
                                            }
                                        }
                                        instant.onSuccess {
                                            step = WidgetStep.Success(email)
                                            pendingSuccess = it
                                        }.onFailure {
                                            runCatching { appState.api.requestEmailCode(last.email, appState.config.clientId, "login") }
                                                .onSuccess {
                                                    step = WidgetStep.EmailCode
                                                    emailCode = ""
                                                }
                                                .onFailure { e ->
                                                    step = WidgetStep.ReturningUser
                                                    error = (e as? TpidError)?.message ?: t["err_title_generic"] ?: "Error"
                                                }
                                        }
                                    }
                                }
                                last.lastAuthenticatedAtMs > 0L && ageMs in 0L..REMEMBER_EMAIL_CODE_MS -> {
                                    step = WidgetStep.Loading(t["loading_sending"] ?: "Sending…")
                                    scope.launch {
                                        runCatching { appState.api.requestEmailCode(last.email, appState.config.clientId, "login") }
                                            .onSuccess {
                                                step = WidgetStep.EmailCode
                                                emailCode = ""
                                            }
                                            .onFailure { e ->
                                                step = WidgetStep.ReturningUser
                                                error = (e as? TpidError)?.message ?: t["err_title_generic"] ?: "Error"
                                            }
                                    }
                                }
                                else -> step = WidgetStep.Password
                            }
                        },
                        onUseAnother = {
                            email = ""; password = ""; emailCode = ""; totp = ""
                            error = null
                            step = WidgetStep.Email
                        },
                        onQr = {
                            qrInit = null; qrImage = null; qrStatus = "loading"
                            step = WidgetStep.QrCode; error = null
                        },
                        onForget = {
                            runCatching { appState.storage.clearLastAccount() }
                            lastAccount = null
                            email = ""
                            step = WidgetStep.Welcome
                        },
                    )
                    WidgetStep.Email -> EmailStep(
                        t = t,
                        email = email, onEmail = { email = it; error = null },
                        error = error,
                        onQr = {
                            qrInit = null; qrImage = null; qrStatus = "loading"
                            step = WidgetStep.QrCode; error = null
                        },
                        onContinue = onContinue@{
                            if (!email.matches(Regex("^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$"))) {
                                error = t["error_invalid_email"] ?: "Invalid email"; return@onContinue
                            }
                            step = WidgetStep.Loading(t["loading_checking"] ?: "Checking…")
                            scope.launch {
                                runCatching { appState.api.accountCheck(email, appState.config.clientId) }
                                    .onSuccess { info ->
                                        accountExists = info.exists
                                        val next: WidgetStep = when {
                                            info.exists -> WidgetStep.Password
                                            // No account → sign-up flow (was routing to
                                            // Password which always 401'd).
                                            else -> WidgetStep.Register(codeSent = false)
                                        }
                                        step = next
                                    }.onFailure { e ->
                                        step = WidgetStep.Email
                                        error = (e as? TpidError)?.message ?: t["err_title_generic"] ?: "Error"
                                    }
                            }
                        },
                        onCreate = {
                            step = WidgetStep.Register(codeSent = false); error = null
                        },
                    )
                    WidgetStep.Password -> PasswordStep(
                        t = t, email = email,
                        password = password, onPassword = { password = it; error = null },
                        error = error,
                        onSubmit = onSubmit@{
                            if (password.length < 8) {
                                error = t["error_password_short"] ?: "Too short"; return@onSubmit
                            }
                            step = WidgetStep.Loading(t["loading_signing"] ?: "Signing in…")
                            runLogin(appState, scope, email, password,
                                emailCode = null, twoFactorCode = null, lang = appState.config.language,
                                onSuccess = {
                                    // B1 fix: hand off to `pendingSuccess` — the
                                    // top-level LaunchedEffect then fires `onResult`
                                    // after the 600ms success flash.
                                    step = WidgetStep.Success(email)
                                    pendingSuccess = it
                                },
                                onEmailCode = { step = WidgetStep.EmailCode; emailCode = "" },
                                onTotp = { step = WidgetStep.TwoFactor; totp = "" },
                                onFail = { step = WidgetStep.Password; error = it.message ?: t["err_title_generic"] }
                            )
                        },
                    )
                    WidgetStep.EmailCode -> EmailCodeStep(
                        t = t, email = email,
                        code = emailCode, onCode = { emailCode = it.filter(Char::isDigit).take(6); error = null },
                        error = error,
                        onSubmit = onSubmit@{
                            if (emailCode.length != 6) {
                                error = t["error_code_len"] ?: "Invalid"; return@onSubmit
                            }
                            step = WidgetStep.Loading(t["loading_verifying"] ?: "Verifying…")
                            // Replay `/auth/login` with the e-mail OTP — the
                            // backend then either returns tokens or asks for
                            // a TOTP (requires_2fa). No /auth/verify hop,
                            // no /oauth/token exchange.
                            runLogin(appState, scope, email, password,
                                emailCode = emailCode, twoFactorCode = null, lang = appState.config.language,
                                onSuccess = {
                                    step = WidgetStep.Success(email)
                                    pendingSuccess = it
                                },
                                onEmailCode = {
                                    // Code expired between two clicks — stay on the
                                    // email-code step and ask for a fresh 6 digits.
                                    step = WidgetStep.EmailCode; emailCode = ""
                                },
                                onTotp = { step = WidgetStep.TwoFactor; totp = "" },
                                onFail = {
                                    step = WidgetStep.EmailCode
                                    error = it.message ?: t["err_title_generic"]
                                    emailCode = ""
                                }
                            )
                        }
                    )
                    WidgetStep.TwoFactor -> TotpStep(
                        t = t, totp = totp, onTotp = { totp = it.filter(Char::isDigit).take(6); error = null },
                        error = error,
                        onSubmit = onSubmit@{
                            if (totp.length != 6) {
                                error = t["error_code_len"] ?: "Invalid"; return@onSubmit
                            }
                            step = WidgetStep.Loading(t["loading_verifying"] ?: "Verifying…")
                            runLogin(appState, scope, email, password,
                                emailCode = emailCode.ifEmpty { null },
                                twoFactorCode = totp,
                                lang = appState.config.language,
                                onSuccess = {
                                    step = WidgetStep.Success(email)
                                    pendingSuccess = it
                                },
                                onEmailCode = { step = WidgetStep.EmailCode; emailCode = ""; totp = "" },
                                onTotp = { step = WidgetStep.TwoFactor; totp = "" },
                                onFail = { step = WidgetStep.TwoFactor; error = it.message ?: t["err_title_generic"]; totp = "" }
                            )
                        }
                    )
                    WidgetStep.Passkey -> PasskeyStep(t = t, onFallback = { step = WidgetStep.Password })
                    is WidgetStep.Register -> RegisterStep(
                        t = t, email = email,
                        username = regUsername,
                        onUsername = { raw ->
                            // Enforce the server's username rule at input time so the
                            // user can't compose a payload that would be rejected by
                            // `/auth/register` with `invalid_username`. Regex on the
                            // server: `^[a-z0-9._]{3,30}$`.
                            regUsername = raw.lowercase()
                                .filter { ch -> ch in 'a'..'z' || ch in '0'..'9' || ch == '.' || ch == '_' }
                                .take(30)
                            error = null
                        },
                        password = regPassword, onPassword = { regPassword = it; error = null },
                        code = regCode, onCode = { regCode = it.filter(Char::isDigit).take(6); error = null },
                        codeSent = s.codeSent, error = error,
                        onSendCode = onSend@{
                            if (regUsername.length < 3) {
                                error = t["error_username_short"] ?: "Username too short"; return@onSend
                            }
                            if (!regUsername.matches(Regex("^[a-z0-9._]{3,30}$"))) {
                                error = t["error_username_invalid"]
                                    ?: "Lowercase letters, digits, dots and underscores only"
                                return@onSend
                            }
                            if (regPassword.length < 8) {
                                error = t["error_password_short"] ?: "Password too short"; return@onSend
                            }
                            step = WidgetStep.Loading(t["loading_sending"] ?: "Sending code…")
                            scope.launch {
                                runCatching {
                                    appState.api.requestEmailCode(email, appState.config.clientId, "register")
                                }.onSuccess {
                                    step = WidgetStep.Register(codeSent = true)
                                }.onFailure { e ->
                                    step = WidgetStep.Register(codeSent = false)
                                    error = (e as? TpidError)?.message ?: t["err_title_generic"]
                                }
                            }
                        },
                        onSubmit = onSubmit@{
                            if (regCode.length != 6) {
                                error = t["error_code_len"] ?: "Invalid code"; return@onSubmit
                            }
                            step = WidgetStep.Loading(t["loading_creating"] ?: "Creating account…")
                            scope.launch {
                                runCatching {
                                    appState.api.register(email, regPassword, regUsername, regCode, appState.config)
                                }.onSuccess { session ->
                                    appState.storage.writeSession(session)
                                    step = WidgetStep.Success(email)
                                    // B1 fix: hand off to the shared LaunchedEffect
                                    // so the success flash always resolves even if
                                    // `scope` is cancelled mid-recomposition.
                                    pendingSuccess = session
                                }.onFailure { e ->
                                    step = WidgetStep.Register(codeSent = true)
                                    error = (e as? TpidError)?.message ?: t["err_title_generic"]
                                    regCode = ""
                                }
                            }
                        },
                    )
                    WidgetStep.QrCode -> QrStep(
                        t = t,
                        qrUrl = qrInit?.qrUrl,
                        qrImage = qrImage,
                        status = qrStatus,
                        error = error,
                        onRefresh = {
                            qrInit = null; qrImage = null; qrStatus = "loading"
                            error = null; qrRefreshTick++
                        },
                        onPaste = { pasted ->
                            // Accept a `tokenpay.space/qr-login?sid=…` URL from the
                            // clipboard as an alternative to rendering + scanning.
                            // Just extract `sid` and jump into polling.
                            val sid = Regex("[?&]sid=([A-Za-z0-9\\-]+)")
                                .find(pasted)?.groupValues?.get(1)
                            if (sid != null) {
                                qrInit = ApiClient.QrInit(sid, pasted, 300)
                                qrStatus = "pending"; error = null; qrRefreshTick++
                            } else {
                                qrStatus = "error"
                                error = t["qr_paste_prompt"]
                                    ?: "Paste the tokenpay.space/qr-login?sid=… link"
                            }
                        },
                    )
                    is WidgetStep.Loading -> LoadingStep(s.message)
                    is WidgetStep.Success -> SuccessStep(t = t, email = s.email)
                    is WidgetStep.Fatal -> FatalStep(
                        t = t, err = s.error,
                        onRetry = { step = WidgetStep.Email; error = null },
                        onClose = { onResult(TpidResult.Failure(s.error)) },
                    )
                }
            }

            // Initialise + poll QR session. Fires whenever the widget is on
            // the QR step and a new [qrRefreshTick] occurs (first entry or
            // user-pressed Refresh). The effect auto-cancels when the user
            // leaves the QR step (goBack, Success, Cancelled).
            if (step == WidgetStep.QrCode) {
                LaunchedEffect(qrRefreshTick) {
                    // Skip init if we already have a session from paste flow —
                    // just go straight into polling.
                    if (qrInit == null) {
                        qrStatus = "loading"
                        val init = runCatching {
                            appState.api.qrLoginInit(appState.config.clientId)
                        }.getOrNull()
                        if (init == null) {
                            qrStatus = "error"
                            error = t["qr_status_error"] ?: "Couldn't start QR session"
                            return@LaunchedEffect
                        }
                        qrInit = init
                        val rendered = withContext(Dispatchers.IO) {
                            QrRenderer.render(init.qrUrl, pixelSize = 512)
                        }
                        if (rendered == null) {
                            qrStatus = "error"
                            error = t["qr_status_error"] ?: "Couldn't render QR. Paste the link or try again."
                            return@LaunchedEffect
                        }
                        qrImage = rendered
                        qrStatus = "pending"
                    } else if (qrImage == null) {
                        val rendered = withContext(Dispatchers.IO) {
                            QrRenderer.render(qrInit!!.qrUrl, pixelSize = 512)
                        }
                        if (rendered == null) {
                            qrStatus = "error"
                            error = t["qr_status_error"] ?: "Couldn't render QR. Paste the link or try again."
                            return@LaunchedEffect
                        }
                        qrImage = rendered
                    }
                    val sid = qrInit?.sessionId ?: return@LaunchedEffect
                    val deadline = System.currentTimeMillis() + (qrInit?.ttlSeconds ?: 300) * 1000L
                    while (isActive && step == WidgetStep.QrCode) {
                        if (System.currentTimeMillis() >= deadline) {
                            qrStatus = "expired"; break
                        }
                        val poll = runCatching { appState.api.qrLoginPoll(sid) }.getOrNull()
                        when (poll) {
                            is ApiClient.QrPollResult.Approved -> {
                                appState.storage.writeSession(poll.session)
                                qrStatus = "approved"
                                delay(400)
                                step = WidgetStep.Success(poll.session.user.email)
                                // B1 fix: don't call onResult from inside this
                                // LaunchedEffect — as soon as `step` flips off
                                // `QrCode`, the enclosing `if (step == QrCode)`
                                // branch drops this LaunchedEffect from the tree
                                // and cancels the pending `delay(600)`. Hand off
                                // to the shared `pendingSuccess` state instead.
                                pendingSuccess = poll.session
                                return@LaunchedEffect
                            }
                            ApiClient.QrPollResult.Expired -> {
                                qrStatus = "expired"; break
                            }
                            else -> { /* pending — keep polling */ }
                        }
                        delay(2_000)
                    }
                }
            }

            Spacer(Modifier.height(24.dp))
            Text(
                "id.tokenpay.space",
                fontSize = 11.sp,
                color = if (isDark) Color.White.copy(alpha = 0.3f) else Color(0x55000000),
            )
            Spacer(Modifier.height(6.dp))
        }
    }
}

/**
 * Direction hint for the AnimatedContent slide — true if we advance forward
 * through the sign-in flow (e.g. Welcome → Email → Password), false if we're
 * moving backwards so the animation matches the user's mental model.
 */
private fun stepDirection(from: WidgetStep, to: WidgetStep): Boolean {
    fun ord(s: WidgetStep) = when (s) {
        WidgetStep.Welcome,
        WidgetStep.ReturningUser -> 0
        WidgetStep.Email -> 1
        WidgetStep.Password -> 2
        WidgetStep.EmailCode -> 2
        WidgetStep.Passkey -> 2
        WidgetStep.QrCode -> 2
        is WidgetStep.Register -> 2
        WidgetStep.TwoFactor -> 3
        is WidgetStep.Loading -> 4
        is WidgetStep.Success -> 5
        is WidgetStep.Fatal -> 5
    }
    return ord(to) >= ord(from)
}

/**
 * Single-call password login against `/api/v1/auth/login`. Branches on the
 * typed [ApiClient.LoginOutcome] so the caller can transition the widget to
 * the e-mail-code or 2FA step without re-issuing its own HTTP request.
 *
 * The previous implementation also did an OAuth-style `/oauth/token`
 * exchange, but the backend never had a code flow here — it returns the
 * token pair directly and the SDK used to crash with
 * `"authorization response missing 'code'"` every time a user with a valid
 * password tried to log in.
 */
private fun runLogin(
    app: TpidAuth.State,
    scope: CoroutineScope,
    email: String,
    password: String,
    emailCode: String?,
    twoFactorCode: String?,
    lang: String?,
    onSuccess: (TpidSession) -> Unit,
    onEmailCode: () -> Unit,
    onTotp: () -> Unit,
    onFail: (TpidError) -> Unit,
) {
    scope.launch {
        runCatching {
            if (password.isBlank() && !emailCode.isNullOrEmpty()) {
                app.api.quickLogin(
                    email = email,
                    emailCode = emailCode,
                    clientId = app.config.clientId,
                    twoFactorCode = twoFactorCode,
                    lang = lang,
                )
            } else {
                app.api.login(
                    email = email, password = password,
                    clientId = app.config.clientId,
                    emailCode = emailCode, twoFactorCode = twoFactorCode,
                    lang = lang,
                )
            }
        }.onSuccess { outcome ->
            when (outcome) {
                is ApiClient.LoginOutcome.Success -> {
                    app.storage.writeSession(outcome.session)
                    onSuccess(outcome.session)
                }
                is ApiClient.LoginOutcome.RequiresEmailCode -> onEmailCode()
                is ApiClient.LoginOutcome.RequiresTwoFactor -> onTotp()
            }
        }.onFailure {
            when (it) {
                is TpidError -> onFail(it)
                else -> onFail(TpidError.ServerError(0, it.message))
            }
        }
    }
}

// ----- Step sealed class -----

internal sealed class WidgetStep {
    data object Welcome : WidgetStep()
    /**
     * 2.6.0 — "Continue as <last user>" welcome card, shown when the SDK
     * has a remembered account profile ([SecureStorage.readLastAccount]).
     */
    data object ReturningUser : WidgetStep()
    data object Email : WidgetStep()
    data object Password : WidgetStep()
    data object EmailCode : WidgetStep()
    data object TwoFactor : WidgetStep()
    data object Passkey : WidgetStep()
    /**
     * QR login step. The widget calls `POST /auth/qr/login-init` to allocate
     * a session, renders the returned URL into a bitmap, and polls
     * `GET /auth/qr/login-poll/:sessionId` every 2s until the phone
     * confirms or the session expires.
     */
    data object QrCode : WidgetStep()
    /**
     * Sign-up screen — appears automatically when [accountCheck] reports the
     * entered email has no existing account. [codeSent] flips to `true` once
     * the server acknowledged `/auth/send-code` with `type = "register"`; the
     * UI morphs to reveal the 6-digit verification input.
     */
    data class Register(val codeSent: Boolean = false) : WidgetStep()
    data class Loading(val message: String) : WidgetStep()
    data class Success(val email: String) : WidgetStep()
    data class Fatal(val error: TpidError) : WidgetStep()
}

/**
 * Format a byte count as a short, locale-independent string (B / KB / MB).
 * Used by the update banner's progress label; no KiB/MiB pedantry — the
 * user just wants to see "1.4 MB of 2.1 MB" go up.
 */
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
