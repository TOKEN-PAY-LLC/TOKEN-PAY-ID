package space.tokenpay.id.ui.components

import androidx.compose.foundation.BorderStroke
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
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import space.tokenpay.id.R
import space.tokenpay.id.TpidConfig

/* =========================================================================
 * Brand marks — the real TOKEN PAY ID wordmark + circular T icon, shipped as
 * PNG resources inside the SDK. Colour (white/black) is selected by theme.
 * ========================================================================= */

@Composable
fun TpidWordmark(
    white: Boolean,
    modifier: Modifier = Modifier,
) {
    val painter = painterResource(
        id = if (white) R.drawable.tpid_wordmark_white else R.drawable.tpid_wordmark_black
    )
    Image(painter = painter, contentDescription = "TOKEN PAY ID", modifier = modifier)
}

@Composable
fun TpidIconMark(modifier: Modifier = Modifier) {
    Image(
        painter = painterResource(id = R.drawable.tpid_icon),
        contentDescription = "TOKEN PAY ID",
        modifier = modifier,
    )
}

/* =========================================================================
 * Primary button — pill, full-width. Dark theme ⇒ white/black; Light ⇒ black/white.
 * Matches .auth-btn from login.html.
 * ========================================================================= */

@Composable
fun TpidPrimaryButton(
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
    Button(
        onClick = onClick,
        enabled = enabled && !loading,
        shape = RoundedCornerShape(999.dp),
        colors = ButtonDefaults.buttonColors(
            containerColor = bg,
            contentColor = fg,
            disabledContainerColor = bg.copy(alpha = 0.35f),
            disabledContentColor = fg.copy(alpha = 0.65f),
        ),
        contentPadding = PaddingValues(vertical = 15.dp, horizontal = 20.dp),
        modifier = modifier.fillMaxWidth().heightIn(min = 52.dp),
    ) {
        if (loading) {
            CircularProgressIndicator(
                strokeWidth = 2.dp,
                color = fg,
                modifier = Modifier.size(18.dp),
            )
            Spacer(Modifier.width(10.dp))
        } else if (leadingIcon != null) {
            leadingIcon()
            Spacer(Modifier.width(10.dp))
        }
        Text(text, fontSize = 15.sp, fontWeight = FontWeight.Bold, letterSpacing = 0.2.sp)
    }
}

/** Secondary pill — outlined. */
@Composable
fun TpidSecondaryButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    leadingIcon: (@Composable () -> Unit)? = null,
) {
    val isDark = MaterialTheme.colorScheme.background.luminance() < 0.5f
    val border = if (isDark) Color.White.copy(alpha = 0.14f) else Color(0x1A000000)
    val fg = if (isDark) Color.White else Color(0xFF0B0B0D)
    val bg = if (isDark) Color(0x14FFFFFF) else Color(0x08000000)
    Button(
        onClick = onClick,
        enabled = enabled,
        shape = RoundedCornerShape(999.dp),
        colors = ButtonDefaults.buttonColors(containerColor = bg, contentColor = fg),
        border = BorderStroke(1.dp, border),
        contentPadding = PaddingValues(vertical = 14.dp, horizontal = 20.dp),
        modifier = modifier.fillMaxWidth().heightIn(min = 48.dp),
    ) {
        if (leadingIcon != null) { leadingIcon(); Spacer(Modifier.width(10.dp)) }
        Text(text, fontSize = 14.sp, fontWeight = FontWeight.SemiBold)
    }
}

/* =========================================================================
 * Field — uppercase label + rounded pill input, matches `.auth-field`.
 * ========================================================================= */

@Composable
fun TpidField(
    label: String,
    value: String,
    onValueChange: (String) -> Unit,
    placeholder: String = "",
    error: String? = null,
    keyboardType: KeyboardType = KeyboardType.Text,
    imeAction: ImeAction = ImeAction.Done,
    password: Boolean = false,
    enabled: Boolean = true,
    visualTransformation: VisualTransformation = if (password) PasswordVisualTransformation() else VisualTransformation.None,
    onSubmit: () -> Unit = {},
) {
    val isDark = MaterialTheme.colorScheme.background.luminance() < 0.5f
    val borderCol = if (isDark) Color.White.copy(alpha = 0.12f) else Color(0x1F000000)
    val bg = if (isDark) Color(0x0DFFFFFF) else Color(0x07000000)
    val fg = if (isDark) Color.White else Color(0xFF0B0B0D)
    val labelCol = if (isDark) Color.White.copy(alpha = 0.4f) else Color(0x7F000000)
    val placeholderCol = if (isDark) Color.White.copy(alpha = 0.25f) else Color(0x55000000)
    val eyeCol = if (isDark) Color.White.copy(alpha = 0.55f) else Color(0x99000000)
    val focus = LocalFocusManager.current

    // Password-reveal toggle — only rendered when [password] is true. The
    // reveal state survives configuration changes via rememberSaveable so a
    // rotation doesn't snap the field back to hidden characters.
    var reveal by rememberSaveable { mutableStateOf(false) }
    val effectiveTransformation = if (password && reveal) VisualTransformation.None else visualTransformation
    val surfaceAlpha = if (enabled) 1f else 0.55f
    Column(Modifier.fillMaxWidth().alpha(surfaceAlpha)) {
        Text(
            label,
            fontSize = 11.sp,
            fontWeight = FontWeight.Bold,
            color = labelCol,
            letterSpacing = 2.sp,
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
                cursorBrush = androidx.compose.ui.graphics.SolidColor(fg),
                keyboardOptions = KeyboardOptions(keyboardType = keyboardType, imeAction = imeAction),
                keyboardActions = KeyboardActions(onAny = { onSubmit(); focus.clearFocus() }),
                modifier = Modifier.weight(1f),
                decorationBox = { inner ->
                    if (value.isEmpty()) {
                        Text(placeholder, color = placeholderCol, fontSize = 15.sp)
                    }
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
            // 2.6.0 strict-monochrome: inline field error is emphasised via
            // weight rather than a pink accent. `onBackground` keeps the
            // same semantics on every OS theme.
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
 * Header — big wordmark logo centered. Used as card top.
 * ========================================================================= */

@Composable
fun TpidBrandHeader(
    branding: TpidConfig.Branding?,
    modifier: Modifier = Modifier,
) {
    val isDark = MaterialTheme.colorScheme.background.luminance() < 0.5f
    Column(
        modifier = modifier.fillMaxWidth(),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        TpidWordmark(
            white = isDark,
            modifier = Modifier.heightIn(max = 40.dp).widthIn(max = 240.dp),
        )
        if (branding?.appName != null) {
            Spacer(Modifier.height(10.dp))
            Text(
                "for ${branding.appName}",
                fontSize = 12.sp,
                color = if (isDark) Color.White.copy(alpha = 0.45f) else Color(0x7F000000),
            )
        }
    }
}

/* =========================================================================
 * Divider "or" — horizontal lines with centered text, matches .auth-alt-divider.
 * ========================================================================= */

@Composable
fun TpidOrDivider(text: String) {
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
            color = textCol,
            fontSize = 10.sp,
            fontWeight = FontWeight.SemiBold,
            letterSpacing = 2.sp,
            modifier = Modifier.padding(horizontal = 14.dp),
        )
        Divider(color = lineCol, modifier = Modifier.weight(1f))
    }
}

/* =========================================================================
 * Language toggle — tiny top-right chip, cycles RU → EN → ZH.
 * ========================================================================= */

@Composable
fun TpidLanguageChip(
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
            fontSize = 11.sp,
            fontWeight = FontWeight.Bold,
            letterSpacing = 1.sp,
            color = fg,
        )
    }
}

/* =========================================================================
 * Error banner — thin horizontal strip at the bottom of the card.
 * ========================================================================= */

@Composable
fun TpidErrorBanner(message: String) {
    // 2.6.0: strict B&W — errors are conveyed by a bold banner with an
    // inverted background (white-on-black on dark theme, black-on-white
    // on light theme) instead of pink/red accents. Colour-blind users
    // get an even stronger signal than before.
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
 * 2.6.0 — strict-monochrome success glyph. A stroked circle with a bold
 * check-mark tick, tinted with `onBackground` so it renders as
 * white-on-dark on the dark theme and black-on-light on the light theme.
 * Explicitly avoids `Icons.Filled.CheckCircle` with a green tint that the
 * earlier versions used.
 */
@Composable
fun SuccessGlyph(size: androidx.compose.ui.unit.Dp = 72.dp) {
    val fg = MaterialTheme.colorScheme.onBackground
    androidx.compose.foundation.Canvas(modifier = Modifier.size(size)) {
        val stroke = size.toPx() / 12f
        // Outer ring.
        drawCircle(
            color = fg,
            radius = (this.size.minDimension / 2f) - stroke / 2f,
            style = androidx.compose.ui.graphics.drawscope.Stroke(width = stroke),
        )
        // Check-mark: two line segments at roughly 30° and 60°.
        val c = this.size.minDimension / 2f
        val s = this.size.minDimension
        val p1 = androidx.compose.ui.geometry.Offset(s * 0.28f, s * 0.52f)
        val p2 = androidx.compose.ui.geometry.Offset(s * 0.46f, s * 0.68f)
        val p3 = androidx.compose.ui.geometry.Offset(s * 0.74f, s * 0.36f)
        drawLine(
            color = fg, start = p1, end = p2,
            strokeWidth = stroke,
            cap = androidx.compose.ui.graphics.StrokeCap.Round,
        )
        drawLine(
            color = fg, start = p2, end = p3,
            strokeWidth = stroke,
            cap = androidx.compose.ui.graphics.StrokeCap.Round,
        )
        // Touch `c` to keep the variable referenced if future tweaks need it.
        @Suppress("UNUSED_VARIABLE") val unused = c
    }
}

/** Text button (looks like a link). */
@Composable
fun TpidLinkButton(text: String, onClick: () -> Unit, modifier: Modifier = Modifier) {
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

/** Luminance of a Compose color — used to pick PNG variant and button styling. */
internal fun Color.luminance(): Float {
    val r = red; val g = green; val b = blue
    return (0.299f * r + 0.587f * g + 0.114f * b)
}
