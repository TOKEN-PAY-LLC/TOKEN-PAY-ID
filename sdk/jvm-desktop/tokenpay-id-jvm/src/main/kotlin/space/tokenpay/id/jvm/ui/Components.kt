package space.tokenpay.id.jvm

import androidx.compose.animation.AnimatedContent
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
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Visibility
import androidx.compose.material.icons.filled.VisibilityOff
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.delay
import space.tokenpay.id.jvm.internal.TpidUpdater

/* =========================================================================
 * Brand marks (PNG resources bundled in JAR).
 * ========================================================================= */

@Composable
internal fun TpidWordmark(white: Boolean, modifier: Modifier = Modifier) {
    Image(
        painter = painterResource(if (white) "tpid_wordmark_white.png" else "tpid_wordmark_black.png"),
        contentDescription = "TOKEN PAY ID",
        modifier = modifier,
    )
}

@Composable
internal fun TpidIconMark(modifier: Modifier = Modifier) {
    Image(
        painter = painterResource("tpid_icon.png"),
        contentDescription = "TOKEN PAY ID",
        modifier = modifier,
    )
}

@Composable
internal fun TpidBrandHeader(appName: String? = null) {
    val isDark = MaterialTheme.colorScheme.background.luminance() < 0.5f
    Column(
        modifier = Modifier.fillMaxWidth(),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        TpidWordmark(
            white = isDark,
            modifier = Modifier.heightIn(max = 40.dp).widthIn(max = 240.dp),
        )
        if (appName != null) {
            Spacer(Modifier.height(8.dp))
            Text(
                "for $appName",
                fontSize = 12.sp,
                color = if (isDark) Color.White.copy(alpha = 0.45f) else Color(0x7F000000),
            )
        }
    }
}

/* =========================================================================
 * Primary / secondary pill buttons.
 * ========================================================================= */

@Composable
internal fun TpidPrimaryButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    loading: Boolean = false,
    leadingIcon: (@Composable () -> Unit)? = null,
) {
    val isDark = MaterialTheme.colorScheme.background.luminance() < 0.5f
    val bg = if (isDark) Color.White else Color(0xFF0B0B0D)
    val fg = if (isDark) Color(0xFF0B0B0D) else Color.White
    Row(
        modifier = modifier
            .fillMaxWidth()
            .heightIn(min = 52.dp)
            .clip(RoundedCornerShape(999.dp))
            .background(if (enabled && !loading) bg else bg.copy(alpha = 0.4f))
            .then(if (enabled && !loading) Modifier.clickable(onClick = onClick) else Modifier)
            .padding(horizontal = 20.dp, vertical = 15.dp),
        horizontalArrangement = Arrangement.Center,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (loading) {
            CircularProgressIndicator(strokeWidth = 2.dp, color = fg, modifier = Modifier.size(18.dp))
            Spacer(Modifier.width(10.dp))
        } else if (leadingIcon != null) {
            leadingIcon(); Spacer(Modifier.width(10.dp))
        }
        Text(text, color = fg, fontSize = 15.sp, fontWeight = FontWeight.Bold, letterSpacing = 0.2.sp)
    }
}

@Composable
internal fun TpidSecondaryButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    leadingIcon: (@Composable () -> Unit)? = null,
) {
    val isDark = MaterialTheme.colorScheme.background.luminance() < 0.5f
    val bg = if (isDark) Color(0x14FFFFFF) else Color(0x08000000)
    val fg = if (isDark) Color.White else Color(0xFF0B0B0D)
    val border = if (isDark) Color.White.copy(alpha = 0.14f) else Color(0x1A000000)
    Row(
        modifier = modifier
            .fillMaxWidth()
            .heightIn(min = 48.dp)
            .clip(RoundedCornerShape(999.dp))
            .background(bg)
            .border(BorderStroke(1.dp, border), RoundedCornerShape(999.dp))
            .then(if (enabled) Modifier.clickable(onClick = onClick) else Modifier)
            .padding(horizontal = 20.dp, vertical = 14.dp),
        horizontalArrangement = Arrangement.Center,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (leadingIcon != null) { leadingIcon(); Spacer(Modifier.width(10.dp)) }
        Text(text, color = fg, fontSize = 14.sp, fontWeight = FontWeight.SemiBold)
    }
}

/* =========================================================================
 * Field — uppercase label + rounded pill input.
 * ========================================================================= */

@Composable
internal fun TpidField(
    label: String,
    value: String,
    onValueChange: (String) -> Unit,
    placeholder: String = "",
    error: String? = null,
    keyboardType: KeyboardType = KeyboardType.Text,
    password: Boolean = false,
    enabled: Boolean = true,
    visualTransformation: VisualTransformation = if (password) PasswordVisualTransformation() else VisualTransformation.None,
    onSubmit: () -> Unit = {},
) {
    val isDark = MaterialTheme.colorScheme.background.luminance() < 0.5f
    val bg = if (isDark) Color(0x0DFFFFFF) else Color(0x07000000)
    val borderCol = if (isDark) Color.White.copy(alpha = 0.12f) else Color(0x1F000000)
    val fg = if (isDark) Color.White else Color(0xFF0B0B0D)
    val labelCol = if (isDark) Color.White.copy(alpha = 0.4f) else Color(0x7F000000)
    val placeholderCol = if (isDark) Color.White.copy(alpha = 0.25f) else Color(0x55000000)
    val eyeCol = if (isDark) Color.White.copy(alpha = 0.55f) else Color(0x99000000)

    // Password-reveal toggle — only visible on password fields. State survives
    // rotation via rememberSaveable.
    var reveal by rememberSaveable { mutableStateOf(false) }
    val effectiveTransformation = if (password && reveal) VisualTransformation.None else visualTransformation
    val surfaceAlpha = if (enabled) 1f else 0.55f

    Column(Modifier.fillMaxWidth().alpha(surfaceAlpha)) {
        Text(
            label,
            fontSize = 11.sp, fontWeight = FontWeight.Bold,
            color = labelCol, letterSpacing = 2.sp,
            modifier = Modifier.padding(bottom = 10.dp, start = 2.dp),
        )
        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(14.dp))
                .background(bg)
                .border(1.dp, borderCol, RoundedCornerShape(14.dp))
                .padding(horizontal = 18.dp, vertical = 16.dp),
        ) {
            BasicTextField(
                value = value,
                onValueChange = onValueChange,
                singleLine = true,
                enabled = enabled,
                readOnly = !enabled,
                visualTransformation = effectiveTransformation,
                textStyle = TextStyle(color = fg, fontSize = 15.sp, fontWeight = FontWeight.Medium),
                cursorBrush = SolidColor(fg),
                keyboardOptions = KeyboardOptions(keyboardType = keyboardType, imeAction = ImeAction.Done),
                keyboardActions = KeyboardActions(onDone = { onSubmit() }),
                modifier = Modifier.weight(1f),
                decorationBox = { inner ->
                    if (value.isEmpty()) Text(placeholder, color = placeholderCol, fontSize = 15.sp)
                    inner()
                },
            )
            if (password && enabled) {
                Spacer(Modifier.width(8.dp))
                Box(
                    modifier = Modifier
                        .size(24.dp)
                        .clip(CircleShape)
                        .clickable { reveal = !reveal },
                    contentAlignment = Alignment.Center,
                ) {
                    Icon(
                        imageVector = if (reveal) Icons.Filled.VisibilityOff else Icons.Filled.Visibility,
                        contentDescription = if (reveal) "Hide password" else "Show password",
                        tint = eyeCol,
                        modifier = Modifier.size(18.dp),
                    )
                }
            }
        }
        if (error != null) {
            Spacer(Modifier.height(8.dp))
            // 2.6.0 strict-monochrome: inline field error is bold
            // `onBackground` instead of a pink tint.
            Text(
                error,
                color = MaterialTheme.colorScheme.onBackground,
                fontSize = 12.sp,
                fontWeight = FontWeight.SemiBold,
            )
        }
    }
}

/* =========================================================================
 * "or" divider.
 * ========================================================================= */

@Composable
internal fun TpidOrDivider(text: String) {
    val isDark = MaterialTheme.colorScheme.background.luminance() < 0.5f
    val lineCol = if (isDark) Color.White.copy(alpha = 0.08f) else Color(0x14000000)
    val textCol = if (isDark) Color.White.copy(alpha = 0.25f) else Color(0x55000000)
    Row(
        Modifier.fillMaxWidth().padding(vertical = 18.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Divider(color = lineCol, modifier = Modifier.weight(1f))
        Text(
            text.uppercase(),
            color = textCol, fontSize = 10.sp, fontWeight = FontWeight.SemiBold,
            letterSpacing = 2.sp, modifier = Modifier.padding(horizontal = 14.dp),
        )
        Divider(color = lineCol, modifier = Modifier.weight(1f))
    }
}

/* =========================================================================
 * Language chip.
 * ========================================================================= */

@Composable
internal fun TpidLanguageChip(
    current: TpidConfig.Language,
    onChange: (TpidConfig.Language) -> Unit,
) {
    val isDark = MaterialTheme.colorScheme.background.luminance() < 0.5f
    val fg = if (isDark) Color.White.copy(alpha = 0.55f) else Color(0x99000000)
    val bg = if (isDark) Color(0x14FFFFFF) else Color(0x0F000000)
    Row(
        Modifier
            .clip(RoundedCornerShape(999.dp))
            .background(bg)
            .clickable {
                val order = listOf(
                    TpidConfig.Language.RUSSIAN,
                    TpidConfig.Language.ENGLISH,
                    TpidConfig.Language.CHINESE,
                )
                val idx = order.indexOf(current).coerceAtLeast(0)
                onChange(order[(idx + 1) % order.size])
            }
            .padding(horizontal = 12.dp, vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            when (current) {
                TpidConfig.Language.RUSSIAN -> "RU"
                TpidConfig.Language.CHINESE -> "ZH"
                else -> "EN"
            },
            fontSize = 11.sp, fontWeight = FontWeight.Bold,
            letterSpacing = 1.sp, color = fg,
        )
    }
}

/* =========================================================================
 * Circular top-icon button (back / close).
 * ========================================================================= */

@Composable
internal fun TpidTopIconButton(
    content: @Composable () -> Unit,
    onClick: () -> Unit,
) {
    val isDark = MaterialTheme.colorScheme.background.luminance() < 0.5f
    val bg = if (isDark) Color(0x14FFFFFF) else Color(0x0F000000)
    Box(
        modifier = Modifier
            .size(36.dp)
            .clip(CircleShape)
            .background(bg)
            .clickable(onClick = onClick),
        contentAlignment = Alignment.Center,
    ) { content() }
}

@Composable
internal fun TpidErrorBanner(message: String) {
    // 2.6.0: strict-monochrome error banner. Replaces the earlier
    // pink/red on transparent-red banner with an `onBackground`-bordered
    // box and bold text. Still unmistakably an error visually.
    val isDark = MaterialTheme.colorScheme.background.luminance() < 0.5f
    val bg = if (isDark) Color.White.copy(alpha = 0.08f) else Color(0x0F000000)
    val fg = if (isDark) Color.White else Color(0xFF0B0B0D)
    val border = if (isDark) Color.White.copy(alpha = 0.28f) else Color(0x33000000)
    Box(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(10.dp))
            .background(bg)
            .border(1.dp, border, RoundedCornerShape(10.dp))
            .padding(horizontal = 14.dp, vertical = 10.dp),
    ) {
        Text(message, color = fg, fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
    }
}

/**
 * 2.6.0 — strict-monochrome success glyph. Stroked circle + check-mark,
 * all tinted with `onBackground`, so it renders as white-on-dark or
 * black-on-light without any chromatic accent.
 */
@Composable
internal fun SuccessGlyph(size: androidx.compose.ui.unit.Dp = 64.dp) {
    val fg = MaterialTheme.colorScheme.onBackground
    androidx.compose.foundation.Canvas(modifier = Modifier.size(size)) {
        val stroke = size.toPx() / 12f
        drawCircle(
            color = fg,
            radius = (this.size.minDimension / 2f) - stroke / 2f,
            style = androidx.compose.ui.graphics.drawscope.Stroke(width = stroke),
        )
        val s = this.size.minDimension
        val p1 = androidx.compose.ui.geometry.Offset(s * 0.28f, s * 0.52f)
        val p2 = androidx.compose.ui.geometry.Offset(s * 0.46f, s * 0.68f)
        val p3 = androidx.compose.ui.geometry.Offset(s * 0.74f, s * 0.36f)
        drawLine(fg, p1, p2, strokeWidth = stroke,
            cap = androidx.compose.ui.graphics.StrokeCap.Round)
        drawLine(fg, p2, p3, strokeWidth = stroke,
            cap = androidx.compose.ui.graphics.StrokeCap.Round)
    }
}

/**
 * Info-styled banner (neutral colour, not error). Currently used for the
 * "a newer SDK is available" hint driven by RemoteConfig.
 */
@Composable
internal fun TpidInfoBanner(message: String) {
    val isDark = MaterialTheme.colorScheme.background.luminance() < 0.5f
    val bg = if (isDark) Color(0x18FFFFFF) else Color(0x10000000)
    val fg = if (isDark) Color.White.copy(alpha = 0.78f) else Color(0xB3000000)
    Box(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(10.dp))
            .background(bg)
            .padding(horizontal = 14.dp, vertical = 10.dp),
    ) {
        Text(message, color = fg, fontSize = 12.sp, fontWeight = FontWeight.Medium)
    }
}

/**
 * Actionable update banner — strictly monochrome.
 *
 * The banner is a small state machine: idle → running → done|failed.
 *
 *  * **Idle**: short message + a high-contrast "Update" pill that invokes
 *    [onStart]. The pill morphs (no jump) into a progress track when the
 *    caller transitions the state.
 *  * **Running**: an indeterminate *or* determinate progress bar is drawn
 *    inside the pill slot along with the current phase label (e.g.
 *    "Downloading 1.2 / 2.1 MB"). The label is updated via [phaseText] and
 *    [progress] — both come from whatever drives [TpidUpdater].
 *  * **Done**: the bar turns into a stroked checkmark and the message
 *    swaps to [doneText]. The banner collapses itself after 2.8 s via the
 *    [onAutoDismiss] callback.
 *  * **Failed**: message swaps to [failedText] and the pill becomes a
 *    "Retry" button that re-fires [onStart].
 *
 * The banner stays purely declarative: it never knows about HTTP or file
 * I/O. [TpidUpdater] is driven by the host (see TpidWidgetDialog).
 */
@Composable
internal fun TpidUpdateBanner(
    state: UpdateBannerState,
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

    // Auto-dismiss after 2.8 s of .Done so the user sees the ✓ but isn't
    // stuck staring at a stale banner forever.
    if (state == UpdateBannerState.Done) {
        LaunchedEffect(Unit) {
            delay(2_800)
            onAutoDismiss()
        }
    }

    val leftText = when (state) {
        UpdateBannerState.Idle -> message
        UpdateBannerState.Running -> phaseText.ifBlank { message }
        UpdateBannerState.Done -> doneText
        UpdateBannerState.Failed -> failedText
    }

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .background(bg)
            .border(1.dp, border, RoundedCornerShape(12.dp))
            .padding(horizontal = 14.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        // Left column: label + (when running) progress track.
        Column(Modifier.weight(1f)) {
            AnimatedContent(
                targetState = leftText,
                transitionSpec = { (fadeIn(tween(180)) togetherWith fadeOut(tween(140))) },
                label = "update-banner-text",
            ) { t ->
                Text(
                    t,
                    color = fg,
                    fontSize = 12.sp,
                    fontWeight = FontWeight.Medium,
                )
            }
            if (state == UpdateBannerState.Running) {
                Spacer(Modifier.height(6.dp))
                TpidProgressTrack(
                    progress = progress.coerceIn(0f, 1f),
                    indeterminate = indeterminate,
                    trackColor = track,
                    fillColor = accent,
                )
            }
        }
        Spacer(Modifier.width(12.dp))

        // Right column: morphing pill (Update → spinner → check → retry).
        AnimatedContent(
            targetState = state,
            transitionSpec = { (fadeIn(tween(180)) togetherWith fadeOut(tween(140))) },
            label = "update-banner-pill",
        ) { s ->
            when (s) {
                UpdateBannerState.Idle -> UpdatePill(
                    label = updateLabel,
                    bg = accent,
                    fg = accentFg,
                    onClick = onStart,
                )
                UpdateBannerState.Running -> InlineSpinner(accent)
                UpdateBannerState.Done -> InlineCheck(accent)
                UpdateBannerState.Failed -> UpdatePill(
                    label = retryLabel,
                    bg = accent,
                    fg = accentFg,
                    onClick = onStart,
                )
            }
        }
    }
}

/** Pure visual state for the banner. Owned by the widget. */
internal enum class UpdateBannerState { Idle, Running, Done, Failed }

@Composable
private fun UpdatePill(label: String, bg: Color, fg: Color, onClick: () -> Unit) {
    Box(
        modifier = Modifier
            .clip(RoundedCornerShape(999.dp))
            .background(bg)
            .clickable(onClick = onClick)
            .padding(horizontal = 14.dp, vertical = 7.dp),
    ) {
        Text(label, color = fg, fontSize = 12.sp, fontWeight = FontWeight.Bold)
    }
}

/**
 * 24 dp indeterminate spinner that matches the banner's monochrome accent.
 * Rotates at 1 rev/sec so the user sees the update is actively doing work
 * even when [Downloading.total] is unknown (Content-Length omitted).
 */
@Composable
private fun InlineSpinner(color: Color) {
    val t = rememberInfiniteTransition(label = "spinner")
    val angle by t.animateFloat(
        initialValue = 0f,
        targetValue = 360f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 1100, easing = LinearEasing),
            repeatMode = RepeatMode.Restart,
        ),
        label = "spinner-angle",
    )
    Canvas(
        modifier = Modifier
            .size(22.dp)
            .padding(2.dp),
    ) {
        val stroke = 2.4f * density
        drawArc(
            color = color,
            startAngle = angle,
            sweepAngle = 270f,
            useCenter = false,
            topLeft = Offset(stroke / 2, stroke / 2),
            size = androidx.compose.ui.geometry.Size(
                size.width - stroke,
                size.height - stroke,
            ),
            style = Stroke(width = stroke, cap = StrokeCap.Round),
        )
    }
}

/** Stroked check-mark glyph the banner swaps in on success. */
@Composable
private fun InlineCheck(color: Color) {
    val reveal by animateFloatAsState(
        targetValue = 1f,
        animationSpec = tween(durationMillis = 360, easing = FastOutSlowInEasing),
        label = "check-reveal",
    )
    Canvas(modifier = Modifier.size(22.dp).padding(2.dp)) {
        val stroke = 2.4f * density
        // Check mark: two line segments.
        val w = size.width; val h = size.height
        val p1 = Offset(w * 0.22f, h * 0.55f)
        val p2 = Offset(w * 0.42f, h * 0.75f)
        val p3 = Offset(w * 0.80f, h * 0.30f)
        // Split the polyline on the reveal fraction.
        val seg1Len = 1f / 3f
        if (reveal <= seg1Len) {
            val t = reveal / seg1Len
            drawLine(color, p1, lerp(p1, p2, t), strokeWidth = stroke, cap = StrokeCap.Round)
        } else {
            drawLine(color, p1, p2, strokeWidth = stroke, cap = StrokeCap.Round)
            val t = ((reveal - seg1Len) / (1f - seg1Len)).coerceIn(0f, 1f)
            drawLine(color, p2, lerp(p2, p3, t), strokeWidth = stroke, cap = StrokeCap.Round)
        }
    }
}

/**
 * Monochrome progress track with [indeterminate] mode. When determinate
 * it draws a straight [0..1] fill; when indeterminate a 40 % wide sliver
 * shuttles back and forth at a constant speed.
 */
@Composable
private fun TpidProgressTrack(
    progress: Float,
    indeterminate: Boolean,
    trackColor: Color,
    fillColor: Color,
) {
    val t = rememberInfiniteTransition(label = "indet")
    val shuttle by t.animateFloat(
        initialValue = -0.4f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 1200, easing = LinearEasing),
            repeatMode = RepeatMode.Restart,
        ),
        label = "indet-shuttle",
    )
    val animatedProgress by animateFloatAsState(
        targetValue = progress,
        animationSpec = tween(durationMillis = 220, easing = FastOutSlowInEasing),
        label = "progress",
    )
    Canvas(
        modifier = Modifier
            .fillMaxWidth()
            .height(4.dp),
    ) {
        val h = size.height
        drawRoundRect(
            color = trackColor,
            cornerRadius = androidx.compose.ui.geometry.CornerRadius(h / 2, h / 2),
        )
        if (indeterminate) {
            val sliver = 0.4f
            val startX = (shuttle * size.width).coerceAtLeast(0f)
            val endX = ((shuttle + sliver) * size.width).coerceAtMost(size.width)
            if (endX > startX) {
                drawRoundRect(
                    color = fillColor,
                    topLeft = Offset(startX, 0f),
                    size = androidx.compose.ui.geometry.Size(endX - startX, h),
                    cornerRadius = androidx.compose.ui.geometry.CornerRadius(h / 2, h / 2),
                )
            }
        } else {
            val w = (animatedProgress.coerceIn(0f, 1f) * size.width)
            if (w > 0f) {
                drawRoundRect(
                    color = fillColor,
                    size = androidx.compose.ui.geometry.Size(w, h),
                    cornerRadius = androidx.compose.ui.geometry.CornerRadius(h / 2, h / 2),
                )
            }
        }
    }
}

private fun lerp(a: Offset, b: Offset, t: Float): Offset =
    Offset(a.x + (b.x - a.x) * t, a.y + (b.y - a.y) * t)

/**
 * Turn a [TpidUpdater.Phase] into a compact (phaseText, progress, indet)
 * triple suitable for [TpidUpdateBanner]. Localised strings come from
 * [TpidStrings] via the caller so the banner itself stays agnostic.
 */
internal data class UpdaterUiState(
    val text: String,
    val progress: Float,
    val indeterminate: Boolean,
)

internal fun TpidUpdater.Phase.toUiState(
    checkingLabel: String,
    downloadingFmt: (bytes: Long, total: Long) -> String,
    verifyingLabel: String,
    installingLabel: String,
    refreshingLabel: String,
    doneLabel: String,
    failedFmt: (reason: String) -> String,
): UpdaterUiState = when (this) {
    is TpidUpdater.Phase.Checking -> UpdaterUiState(checkingLabel, 0.03f, true)
    is TpidUpdater.Phase.Downloading -> {
        val ratio = if (total > 0L) bytes.toFloat() / total else -1f
        val indet = ratio < 0f
        UpdaterUiState(
            text = downloadingFmt(bytes, total),
            progress = if (indet) 0f else 0.05f + 0.70f * ratio.coerceIn(0f, 1f),
            indeterminate = indet,
        )
    }
    is TpidUpdater.Phase.Verifying -> UpdaterUiState(verifyingLabel, 0.80f, false)
    is TpidUpdater.Phase.Installing -> UpdaterUiState(installingLabel, 0.90f, false)
    is TpidUpdater.Phase.RefreshingConfig -> UpdaterUiState(refreshingLabel, 0.96f, false)
    is TpidUpdater.Phase.Done -> UpdaterUiState(doneLabel, 1f, false)
    is TpidUpdater.Phase.Failed -> UpdaterUiState(failedFmt(reason), 0f, false)
}

@Composable
internal fun TpidLinkButton(text: String, onClick: () -> Unit, modifier: Modifier = Modifier) {
    val isDark = MaterialTheme.colorScheme.background.luminance() < 0.5f
    val fg = if (isDark) Color.White.copy(alpha = 0.55f) else Color(0x99000000)
    Text(
        text,
        color = fg,
        fontSize = 13.sp,
        fontWeight = FontWeight.SemiBold,
        modifier = modifier.clickable(onClick = onClick).padding(vertical = 6.dp, horizontal = 10.dp),
    )
}

internal fun Color.luminance(): Float {
    val r = red; val g = green; val b = blue
    return (0.299f * r + 0.587f * g + 0.114f * b)
}
