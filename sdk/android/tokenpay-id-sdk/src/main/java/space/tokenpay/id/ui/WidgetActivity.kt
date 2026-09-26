package space.tokenpay.id.ui

import android.os.Bundle
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.OnBackPressedCallback
import androidx.activity.compose.setContent
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.ExperimentalAnimationApi
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.wrapContentWidth
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
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import android.content.Intent
import android.net.Uri
import androidx.compose.ui.platform.LocalContext
import kotlinx.coroutines.delay
import space.tokenpay.id.TpidAuth
import space.tokenpay.id.TpidResult
import space.tokenpay.id.TpidWidget
import space.tokenpay.id.ui.components.TpidBrandHeader
import space.tokenpay.id.ui.components.TpidLanguageChip
import space.tokenpay.id.ui.components.luminance
import space.tokenpay.id.ui.screens.*
import space.tokenpay.id.ui.theme.TpidTheme

/**
 * Full-screen activity hosting the native auth widget.
 * Mirrors the `.auth-card` visual from `login.html` — centred card with blurred
 * dark/light background, wordmark header, back button, language chip and close.
 */
class WidgetActivity : ComponentActivity() {

    private lateinit var sessionId: String

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val state = TpidAuth.requireState()
        if (!state.config.allowScreenshots) {
            window.setFlags(WindowManager.LayoutParams.FLAG_SECURE, WindowManager.LayoutParams.FLAG_SECURE)
        }

        sessionId = TpidWidget.readSession(savedInstanceState, intent) ?: run {
            finish(); return
        }
        val prefill = intent.getStringExtra(TpidWidget.EXTRA_PREFILL_EMAIL)
            ?: state.config.prefillEmail

        setContent {
            TpidTheme(themeMode = state.config.theme) {
                val vm: WidgetViewModel = viewModel(
                    factory = WidgetViewModel.factory(
                        appState = state,
                        prefillEmail = prefill,
                        onComplete = { result ->
                            TpidWidget.deliver(sessionId, result)
                            finish()
                        },
                    )
                )
                DisposableEffect(Unit) {
                    val cb = object : OnBackPressedCallback(true) {
                        override fun handleOnBackPressed() { vm.back() }
                    }
                    onBackPressedDispatcher.addCallback(cb)
                    onDispose { cb.remove() }
                }
                WidgetHost(vm)
            }
        }
    }

    override fun onSaveInstanceState(outState: Bundle) {
        super.onSaveInstanceState(outState)
        outState.putString(TpidWidget.EXTRA_SESSION_ID, sessionId)
    }
}

@Composable
private fun WidgetHost(vm: WidgetViewModel) {
    val state by vm.state.collectAsState()
    val scroll = rememberScrollState()
    val isDark = MaterialTheme.colorScheme.background.luminance() < 0.5f
    val cardBg = if (isDark) Color(0xFF0E0E11) else Color.White
    val cardBorder = if (isDark) Color.White.copy(alpha = 0.08f) else Color(0x14000000)
    val pageBg = MaterialTheme.colorScheme.background

    // `BoxWithConstraints` gives us the parent viewport height at compose
    // time so we can pin the inner scrollable Column to at least that
    // height and then use `Arrangement.Center` to vertically centre the
    // card. A plain `contentAlignment = TopCenter` + scroll — the previous
    // layout — caused the card to stick to the top of the screen with a
    // huge empty band below it on tall phones (see pre.8 user bug
    // report). `Arrangement.Center` inside a `verticalScroll` column with
    // `heightIn(min = parentMaxHeight)` is the idiomatic Compose recipe
    // for "centre when it fits, scroll when it doesn't".
    BoxWithConstraints(
        modifier = Modifier
            .fillMaxSize()
            .background(pageBg),
    ) {
        val columnMinHeight = maxHeight
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .verticalScroll(scroll)
                .heightIn(min = columnMinHeight)
                .padding(horizontal = 20.dp, vertical = 16.dp),
            verticalArrangement = Arrangement.Center,
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
         Column(
            modifier = Modifier
                .widthIn(max = 420.dp)
                .fillMaxWidth()
                .clip(RoundedCornerShape(24.dp))
                .background(cardBg)
                .border(1.dp, cardBorder, RoundedCornerShape(24.dp))
                .padding(horizontal = 24.dp, vertical = 20.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            // Top bar: back (on non-welcome steps) + language chip + close
            Row(
                Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                if (state.step !is WidgetStep.Welcome && state.step !is WidgetStep.Success && state.step !is WidgetStep.ReturningUser) {
                    TopIconButton(icon = { Icon(Icons.Default.ArrowBack, contentDescription = "Back", modifier = Modifier.size(18.dp)) }, onClick = vm::back)
                } else {
                    Spacer(Modifier.size(36.dp))
                }
                Spacer(Modifier.weight(1f))
                TpidLanguageChip(current = state.language, onChange = vm::setLanguage)
                Spacer(Modifier.width(8.dp))
                TopIconButton(icon = { Icon(Icons.Default.Close, contentDescription = "Close", modifier = Modifier.size(18.dp)) }, onClick = vm::cancel)
            }

            Spacer(Modifier.height(20.dp))
            TpidBrandHeader(state.branding)
            Spacer(Modifier.height(16.dp))
            val bannerVisible = state.showUpdateBanner || state.updater.state != UpdateBannerPhase.Idle
            if (bannerVisible) {
                val ctx = LocalContext.current
                TpidUpdateBanner(
                    phase = state.updater.state,
                    // 2.6.2 — short, mobile-friendly banner copy. The full
                    // sentence used to overflow the pill row on narrow
                    // phone widths (≤ 360 dp); the version suffix is now
                    // appended only when known and different.
                    message = (state.strings["update_available"]
                        ?: "A newer TOKEN PAY ID SDK is available — please update.") +
                        (state.updater.latestVersion
                            ?.takeIf { it != state.sdkVersion }
                            ?.let { " ($it)" } ?: ""),
                    updateLabel = state.strings["btn_download_sdk"] ?: "Open SDK",
                    retryLabel = state.strings["btn_retry"] ?: "Retry",
                    doneText = (state.strings["update_done"] ?: "Updated to %1\$s")
                        .replace("%1\$s", state.updater.latestVersion ?: state.sdkVersion),
                    failedText = state.strings["update_failed"]
                        ?: "Update failed — please try again.",
                    phaseText = state.updater.phaseText,
                    progress = state.updater.progress,
                    indeterminate = state.updater.indeterminate,
                    onStart = {
                        // 2.6.2 — Honest "Update" behaviour on Android.
                        // Smart-update used to silently download a tarball
                        // into private cache (invisible to the user, hence
                        // the "I clicked Update and nothing changed" bug
                        // report). Now we hand the URL to the system
                        // browser so the user can actually install the
                        // new version, and dismiss the banner for the
                        // session so it doesn't bounce back the moment
                        // they re-open the widget.
                        val url = vm.requestUpdateOpen()
                        runCatching {
                            ctx.startActivity(
                                Intent(Intent.ACTION_VIEW, Uri.parse(url))
                                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                            )
                        }
                    },
                    onAutoDismiss = vm::dismissUpdaterBanner,
                )
                Spacer(Modifier.height(12.dp))
            } else {
                Spacer(Modifier.height(12.dp))
            }

            // Animated step transitions — every navigation fades + slides the
            // content so the widget feels alive instead of switching
            // instantaneously. Matches JVM + Swift behaviour.
            AnimatedStepContent(step = state.step) { step ->
                when (step) {
                    is WidgetStep.Welcome -> WelcomeScreen(state, vm)
                    is WidgetStep.ReturningUser -> ReturningUserScreen(state, vm)
                    is WidgetStep.Email -> EmailScreen(state, vm)
                    is WidgetStep.Password -> PasswordScreen(state, vm)
                    is WidgetStep.EmailCode -> EmailCodeScreen(state, vm)
                    is WidgetStep.TwoFactor -> TwoFactorScreen(state, vm)
                    is WidgetStep.Passkey -> PasskeyScreen(state, vm)
                    is WidgetStep.QrCode -> QrScreen(state, vm)
                    is WidgetStep.Recovery -> RecoveryScreen(state, vm)
                    is WidgetStep.Register -> RegisterScreen(state, vm, codeSent = step.codeSent)
                    is WidgetStep.Loading -> LoadingScreen(step.message, state, vm)
                    is WidgetStep.Success -> SuccessScreen(state)
                    is WidgetStep.ErrorFatal -> FatalErrorScreen(step.error, state, onRetry = vm::resetToStart, onClose = vm::cancel)
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
}

@Composable
private fun TopIconButton(icon: @Composable () -> Unit, onClick: () -> Unit) {
    val isDark = MaterialTheme.colorScheme.background.luminance() < 0.5f
    val bg = if (isDark) Color(0x14FFFFFF) else Color(0x0F000000)
    val fg = if (isDark) Color.White.copy(alpha = 0.75f) else Color(0x99000000)
    Box(
        modifier = Modifier
            .size(36.dp)
            .clip(CircleShape)
            .background(bg)
            .clickable(onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        androidx.compose.runtime.CompositionLocalProvider(LocalContentColor provides fg) { icon() }
    }
}

/**
 * Animated switcher between widget steps. Uses a forward/backward slide
 * based on the step's logical position in the state machine so the user
 * perceives "going deeper" vs. "coming back".
 */
@OptIn(ExperimentalAnimationApi::class)
@Composable
private fun AnimatedStepContent(
    step: WidgetStep,
    content: @Composable (WidgetStep) -> Unit,
) {
    AnimatedContent(
        targetState = step,
        transitionSpec = {
            val forward = stepOrder(targetState) >= stepOrder(initialState)
            val dx = if (forward) 48 else -48
            (fadeIn(tween(220)) + slideInHorizontally(tween(260)) { dx })
                .togetherWith(fadeOut(tween(140)) + slideOutHorizontally(tween(220)) { -dx })
        },
        label = "tpid-step-switcher",
    ) { current -> content(current) }
}

private fun stepOrder(s: WidgetStep): Int = when (s) {
    // 2.6.0: ReturningUser sits at the same ordinal as Welcome — they are
    // alternative entry points and the transition between them shouldn't
    // feel like navigating forward.
    WidgetStep.Welcome,
    WidgetStep.ReturningUser -> 0
    WidgetStep.Email        -> 1
    WidgetStep.Password,
    WidgetStep.EmailCode,
    WidgetStep.Passkey,
    WidgetStep.QrCode       -> 2
    is WidgetStep.Register  -> 2
    WidgetStep.TwoFactor    -> 3
    WidgetStep.Recovery     -> 4
    is WidgetStep.Loading   -> 5
    WidgetStep.Success      -> 6
    is WidgetStep.ErrorFatal -> 7
}

/**
 * 2.6.1 — Animated smart-update banner.
 *
 * Same visual language as the JVM counterpart in [space.tokenpay.id.jvm.TpidUpdateBanner]:
 * morphs through Idle → Running → Done|Failed, monochrome progress track
 * inside, stroked check on success. UI is purely declarative — all HTTP
 * and file I/O lives in [WidgetViewModel.startSmartUpdate] / [TpidUpdater].
 */
@Composable
private fun TpidUpdateBanner(
    phase: UpdateBannerPhase,
    message: String,
    updateLabel: String,
    retryLabel: String,
    doneText: String,
    failedText: String,
    phaseText: String,
    progress: Float,
    indeterminate: Boolean,
    onStart: () -> Unit,
    onAutoDismiss: () -> Unit,
) {
    val isDark = MaterialTheme.colorScheme.background.luminance() < 0.5f
    val bg = if (isDark) Color(0x18FFFFFF) else Color(0x10000000)
    val border = if (isDark) Color.White.copy(alpha = 0.18f) else Color(0x14000000)
    val fg = if (isDark) Color.White.copy(alpha = 0.85f) else Color(0xB3000000)
    val accent = if (isDark) Color.White else Color(0xFF0B0B0D)
    val accentFg = if (isDark) Color(0xFF0B0B0D) else Color.White
    val track = if (isDark) Color(0x28FFFFFF) else Color(0x18000000)

    if (phase == UpdateBannerPhase.Done) {
        LaunchedEffect(Unit) {
            delay(2_800)
            onAutoDismiss()
        }
    }

    val leftText = when (phase) {
        UpdateBannerPhase.Idle -> message
        UpdateBannerPhase.Running -> phaseText.ifBlank { message }
        UpdateBannerPhase.Done -> doneText
        UpdateBannerPhase.Failed -> failedText
    }

    @Composable
    fun BannerText() {
        AnimatedContent(
            targetState = leftText,
            transitionSpec = { (fadeIn(tween(180)) togetherWith fadeOut(tween(140))) },
            label = "update-banner-text",
        ) { t -> Text(t, color = fg, fontSize = 12.sp, fontWeight = FontWeight.Medium) }
        if (phase == UpdateBannerPhase.Running) {
            Spacer(Modifier.height(6.dp))
            UpdateProgressTrack(
                progress = progress.coerceIn(0f, 1f),
                indeterminate = indeterminate,
                trackColor = track,
                fillColor = accent,
            )
        }
    }

    @Composable
    fun BannerPill(modifier: Modifier = Modifier) {
        AnimatedContent(
            targetState = phase,
            transitionSpec = { (fadeIn(tween(180)) togetherWith fadeOut(tween(140))) },
            label = "update-banner-pill",
            modifier = modifier,
        ) { s ->
            when (s) {
                UpdateBannerPhase.Idle -> UpdatePill(updateLabel, accent, accentFg, onStart)
                UpdateBannerPhase.Running -> UpdateSpinner(accent)
                UpdateBannerPhase.Done -> UpdateCheck(accent)
                UpdateBannerPhase.Failed -> UpdatePill(retryLabel, accent, accentFg, onStart)
            }
        }
    }

    // 2.6.2 — adaptive layout. On narrow phone widths (banner width
    // ≤ 320 dp, e.g. 360 dp screens after the card's 20 dp horizontal
    // padding) the message + pill are stacked vertically so the long
    // localised "A newer SDK is available — please update" copy doesn't
    // squash the pill into a 60 dp slot. Wider screens keep the original
    // single-row layout.
    BoxWithConstraints(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .background(bg)
            .border(1.dp, border, RoundedCornerShape(12.dp))
            .padding(horizontal = 14.dp, vertical = 10.dp),
    ) {
        val narrow = maxWidth < 320.dp
        if (narrow) {
            Column(Modifier.fillMaxWidth()) {
                BannerText()
                Spacer(Modifier.height(10.dp))
                BannerPill(Modifier.fillMaxWidth().wrapContentWidth(Alignment.CenterHorizontally))
            }
        } else {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(Modifier.weight(1f)) {
                    BannerText()
                }
                Spacer(Modifier.width(12.dp))
                BannerPill()
            }
        }
    }
}

/** Pure UI state mirroring the one on JVM / Swift. */
internal enum class UpdateBannerPhase { Idle, Running, Done, Failed }

@Composable
private fun UpdatePill(label: String, bg: Color, fg: Color, onClick: () -> Unit) {
    Box(
        modifier = Modifier
            .clip(RoundedCornerShape(999.dp))
            .background(bg)
            .clickable(onClick = onClick)
            .padding(horizontal = 12.dp, vertical = 6.dp),
    ) {
        Text(label, color = fg, fontSize = 11.sp, fontWeight = FontWeight.Bold)
    }
}

@Composable
private fun UpdateSpinner(color: Color) {
    val t = rememberInfiniteTransition(label = "spinner")
    val angle by t.animateFloat(
        initialValue = 0f, targetValue = 360f,
        animationSpec = infiniteRepeatable(tween(1100, easing = LinearEasing), RepeatMode.Restart),
        label = "spinner-angle",
    )
    Canvas(modifier = Modifier.size(22.dp).padding(2.dp)) {
        val stroke = 2.4f * density
        drawArc(
            color = color,
            startAngle = angle,
            sweepAngle = 270f,
            useCenter = false,
            topLeft = Offset(stroke / 2, stroke / 2),
            size = Size(size.width - stroke, size.height - stroke),
            style = Stroke(width = stroke, cap = StrokeCap.Round),
        )
    }
}

@Composable
private fun UpdateCheck(color: Color) {
    val reveal by animateFloatAsState(
        targetValue = 1f,
        animationSpec = tween(360, easing = FastOutSlowInEasing),
        label = "check-reveal",
    )
    Canvas(modifier = Modifier.size(22.dp).padding(2.dp)) {
        val stroke = 2.4f * density
        val w = size.width; val h = size.height
        val p1 = Offset(w * 0.22f, h * 0.55f)
        val p2 = Offset(w * 0.42f, h * 0.75f)
        val p3 = Offset(w * 0.80f, h * 0.30f)
        val seg1 = 1f / 3f
        if (reveal <= seg1) {
            val f = reveal / seg1
            drawLine(color, p1, Offset(p1.x + (p2.x - p1.x) * f, p1.y + (p2.y - p1.y) * f),
                strokeWidth = stroke, cap = StrokeCap.Round)
        } else {
            drawLine(color, p1, p2, strokeWidth = stroke, cap = StrokeCap.Round)
            val f = ((reveal - seg1) / (1f - seg1)).coerceIn(0f, 1f)
            drawLine(color, p2, Offset(p2.x + (p3.x - p2.x) * f, p2.y + (p3.y - p2.y) * f),
                strokeWidth = stroke, cap = StrokeCap.Round)
        }
    }
}

@Composable
private fun UpdateProgressTrack(
    progress: Float,
    indeterminate: Boolean,
    trackColor: Color,
    fillColor: Color,
) {
    val t = rememberInfiniteTransition(label = "indet")
    val shuttle by t.animateFloat(
        initialValue = -0.4f, targetValue = 1f,
        animationSpec = infiniteRepeatable(tween(1200, easing = LinearEasing), RepeatMode.Restart),
        label = "indet-shuttle",
    )
    val animatedProgress by animateFloatAsState(
        targetValue = progress,
        animationSpec = tween(220, easing = FastOutSlowInEasing),
        label = "progress",
    )
    Canvas(modifier = Modifier.fillMaxWidth().height(4.dp)) {
        val h = size.height
        drawRoundRect(color = trackColor, cornerRadius = CornerRadius(h / 2, h / 2))
        if (indeterminate) {
            val sliver = 0.4f
            val startX = (shuttle * size.width).coerceAtLeast(0f)
            val endX = ((shuttle + sliver) * size.width).coerceAtMost(size.width)
            if (endX > startX) {
                drawRoundRect(
                    color = fillColor,
                    topLeft = Offset(startX, 0f),
                    size = Size(endX - startX, h),
                    cornerRadius = CornerRadius(h / 2, h / 2),
                )
            }
        } else {
            val w = animatedProgress.coerceIn(0f, 1f) * size.width
            if (w > 0f) {
                drawRoundRect(
                    color = fillColor,
                    size = Size(w, h),
                    cornerRadius = CornerRadius(h / 2, h / 2),
                )
            }
        }
    }
}
