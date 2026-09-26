package space.tokenpay.id.jvm

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.ContentPaste
import androidx.compose.material.icons.filled.Error
import androidx.compose.material.icons.filled.QrCode2
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.FilterQuality
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import java.awt.Desktop
import java.awt.Toolkit
import java.awt.datatransfer.DataFlavor
import java.net.URI

internal fun openBrowser(url: String) {
    runCatching { if (Desktop.isDesktopSupported()) Desktop.getDesktop().browse(URI.create(url)) }
}

/**
 * 2.6.0 — "Continue as X" welcome card for returning users. Shown in place
 * of [WelcomeStep] when [space.tokenpay.id.jvm.internal.SecureStorage.readLastAccount]
 * returned a non-null profile. Purely monochrome: no coloured avatars, no
 * green primaries.
 */
@Composable
internal fun ReturningUserStep(
    t: Map<String, String>,
    lastAccount: space.tokenpay.id.jvm.internal.SecureStorage.LastAccount?,
    error: String?,
    onContinue: () -> Unit,
    onUseAnother: () -> Unit,
    onQr: () -> Unit,
    onForget: () -> Unit,
) {
    if (lastAccount == null) {
        // Defensive — the dialog should never land here without a profile.
        onUseAnother(); return
    }
    val displayName = lastAccount.displayName?.takeIf { it.isNotBlank() } ?: lastAccount.email
    val continueFmt = t["welcome_continue_as"] ?: "Continue as %s"
    val continueLabel = runCatching { continueFmt.format(displayName) }
        .getOrDefault("Continue as $displayName")

    val ageMs = System.currentTimeMillis() - lastAccount.lastAuthenticatedAtMs
    val hintKey = when {
        lastAccount.lastAuthenticatedAtMs > 0L && ageMs in 0L..86_400_000L -> "remembered_session_hint"
        lastAccount.lastAuthenticatedAtMs > 0L && ageMs in 0L..604_800_000L -> "remembered_code_hint"
        else -> "remembered_password_hint"
    }
    Column(Modifier.fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally) {
        ScreenSubtitle(t["signin_title"] ?: "Welcome back")
        Spacer(Modifier.height(24.dp))
        Row(
            Modifier.fillMaxWidth()
                .clip(RoundedCornerShape(20.dp))
                .background(MaterialTheme.colorScheme.onBackground.copy(alpha = 0.045f))
                .border(1.dp, MaterialTheme.colorScheme.onBackground.copy(alpha = 0.12f), RoundedCornerShape(20.dp))
                .padding(16.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            AccountInitial(displayName)
            Spacer(Modifier.width(14.dp))
            Column {
                Text(displayName, fontSize = 16.sp, fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.onBackground)
                if (lastAccount.email != displayName) {
                    Spacer(Modifier.height(4.dp))
                    Text(lastAccount.email, fontSize = 12.sp,
                        color = MaterialTheme.colorScheme.onBackground.copy(alpha = 0.6f))
                }
            }
        }
        Spacer(Modifier.height(12.dp))
        Text(t[hintKey].orEmpty(), fontSize = 11.sp, textAlign = TextAlign.Center,
            color = MaterialTheme.colorScheme.onBackground.copy(alpha = 0.55f))
        if (error != null) {
            Spacer(Modifier.height(12.dp))
            Text(error, fontSize = 12.sp, textAlign = TextAlign.Center,
                color = MaterialTheme.colorScheme.onBackground)
        }
        Spacer(Modifier.height(20.dp))
        TpidPrimaryButton(text = continueLabel, onClick = onContinue)
        Spacer(Modifier.height(10.dp))
        TpidSecondaryButton(
            text = t["welcome_other_account"] ?: "Use another account",
            onClick = onUseAnother,
        )
        Spacer(Modifier.height(14.dp))
        TpidLinkButton(
            text = t["alt_qr"] ?: "Sign in with QR code",
            onClick = onQr,
            modifier = Modifier.fillMaxWidth().wrapContentWidth(Alignment.CenterHorizontally),
        )
        Spacer(Modifier.height(4.dp))
        TpidLinkButton(
            text = t["welcome_forget"] ?: "Forget this account",
            onClick = onForget,
            modifier = Modifier.fillMaxWidth().wrapContentWidth(Alignment.CenterHorizontally),
        )
    }
}

@Composable
private fun AccountInitial(display: String) {
    val isDark = MaterialTheme.colorScheme.background.luminance() < 0.5f
    val bg = if (isDark) Color.White.copy(alpha = 0.14f) else Color(0x0F000000)
    val fg = if (isDark) Color.White else Color(0xFF0B0B0D)
    val letter = display.firstOrNull { it.isLetterOrDigit() }?.uppercaseChar()?.toString() ?: "·"
    Box(
        Modifier.size(48.dp).clip(RoundedCornerShape(24.dp)).background(bg),
        contentAlignment = Alignment.Center,
    ) {
        Text(letter, fontSize = 22.sp, fontWeight = FontWeight.Bold, color = fg)
    }
}

@Composable
internal fun WelcomeStep(
    t: Map<String, String>,
    onSignIn: () -> Unit,
    onCreateAccount: () -> Unit,
    onQr: () -> Unit,
) {
    Column(Modifier.fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally) {
        ScreenSubtitle(t["welcome_subtitle"].orEmpty())
        Spacer(Modifier.height(28.dp))
        TpidPrimaryButton(
            text = t["welcome_sign_in"] ?: "Sign in",
            onClick = onSignIn,
        )
        Spacer(Modifier.height(12.dp))
        TpidSecondaryButton(
            text = t["welcome_create"] ?: "Create account",
            onClick = onCreateAccount,
        )
        Spacer(Modifier.height(12.dp))
        TpidSecondaryButton(
            text = t["alt_qr"] ?: "Sign in with QR code",
            onClick = onQr,
            leadingIcon = { Icon(Icons.Filled.QrCode2, contentDescription = null, modifier = Modifier.size(18.dp)) },
        )
        TpidOrDivider(t["welcome_or"] ?: "or")
        TpidLinkButton(
            text = t["welcome_open_web"] ?: "Open tokenpay.space",
            onClick = { openBrowser("https://tokenpay.space/") },
            modifier = Modifier.fillMaxWidth().wrapContentWidth(Alignment.CenterHorizontally),
        )
    }
}

@Composable
internal fun EmailStep(
    t: Map<String, String>,
    email: String, onEmail: (String) -> Unit,
    error: String?,
    onContinue: () -> Unit,
    onCreate: () -> Unit,
    onQr: () -> Unit,
) {
    Column(Modifier.fillMaxWidth()) {
        ScreenSubtitle(t["signin_title"] ?: "Sign in")
        Spacer(Modifier.height(24.dp))
        TpidField(
            label = t["field_email"] ?: "EMAIL",
            value = email, onValueChange = onEmail,
            placeholder = t["placeholder_email"] ?: "you@example.com",
            error = error,
            keyboardType = KeyboardType.Email,
            onSubmit = onContinue,
        )
        Spacer(Modifier.height(16.dp))
        TpidPrimaryButton(
            text = t["btn_next"] ?: "Next",
            onClick = onContinue,
            enabled = email.length >= 3,
        )
        TpidOrDivider(t["alt_divider"] ?: "or")
        TpidSecondaryButton(
            text = t["alt_qr"] ?: "Sign in with QR code",
            onClick = onQr,
            leadingIcon = { Icon(Icons.Filled.QrCode2, contentDescription = null, modifier = Modifier.size(18.dp)) },
        )
        Spacer(Modifier.height(20.dp))
        FooterInline(
            muted = t["footer_no_account"] ?: "No account?",
            link = t["footer_create"] ?: "Create one",
            onClick = onCreate,
        )
    }
}

@Composable
internal fun PasswordStep(
    t: Map<String, String>,
    email: String,
    password: String, onPassword: (String) -> Unit,
    error: String?,
    onSubmit: () -> Unit,
) {
    Column(Modifier.fillMaxWidth()) {
        EmailChip(email)
        Spacer(Modifier.height(24.dp))
        TpidField(
            label = t["field_password"] ?: "PASSWORD",
            value = password, onValueChange = onPassword,
            placeholder = t["placeholder_password"] ?: "Password",
            error = error,
            keyboardType = KeyboardType.Password,
            password = true,
            onSubmit = onSubmit,
        )
        Spacer(Modifier.height(16.dp))
        TpidPrimaryButton(
            text = t["btn_sign_in"] ?: "Sign in",
            onClick = onSubmit,
            enabled = password.length >= 8,
        )
        // "Use email code" link was removed in pre.9 — the e-mail OTP is
        // now the mandatory second factor of the password login itself, not
        // an alternative entry point, so showing it as a separate option
        // was confusing and led users to a dead end.
    }
}

/**
 * Sign-up screen. Appears when the user's e-mail address has no account yet.
 *
 * Two UI phases driven by [codeSent]:
 *
 *  - `false` — user types username + password; primary button sends the
 *              verification e-mail and flips the flag.
 *  - `true`  — a 6-digit code field is revealed; the primary button now
 *              submits to `/auth/register` and finishes sign-in.
 */
@Composable
internal fun RegisterStep(
    t: Map<String, String>,
    email: String,
    username: String, onUsername: (String) -> Unit,
    password: String, onPassword: (String) -> Unit,
    code: String, onCode: (String) -> Unit,
    codeSent: Boolean,
    error: String?,
    onSendCode: () -> Unit,
    onSubmit: () -> Unit,
) {
    Column(Modifier.fillMaxWidth()) {
        ScreenSubtitle(t["register_title"] ?: "Create your account")
        Spacer(Modifier.height(10.dp))
        // Hint explaining why we landed on the sign-up screen when the user
        // merely tried to sign in with an unknown email.
        if (!codeSent) {
            Text(
                t["register_hint"]
                    ?: "This email isn't registered yet — fill in the form below to create a new account.",
                fontSize = 12.sp,
                fontWeight = FontWeight.Normal,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f),
                textAlign = TextAlign.Center,
                modifier = Modifier.fillMaxWidth(),
            )
            Spacer(Modifier.height(14.dp))
        }
        EmailChip(email)
        Spacer(Modifier.height(16.dp))
        TpidField(
            label = t["field_username"] ?: "USERNAME",
            value = username, onValueChange = onUsername,
            placeholder = t["placeholder_username"] ?: "your_login",
            error = if (!codeSent) error else null,
            enabled = !codeSent,
            keyboardType = KeyboardType.Text,
        )
        Text(
            t["hint_username"]
                ?: "Lowercase letters, digits, dots, underscores (3-30)",
            fontSize = 11.sp,
            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.45f),
            modifier = Modifier
                .fillMaxWidth()
                .padding(start = 4.dp, top = 4.dp),
        )
        Spacer(Modifier.height(12.dp))
        TpidField(
            label = t["field_password"] ?: "PASSWORD",
            value = password, onValueChange = onPassword,
            placeholder = t["placeholder_password_new"] ?: "At least 8 characters",
            error = if (!codeSent) error else null,
            enabled = !codeSent,
            keyboardType = KeyboardType.Password,
            password = true,
            onSubmit = if (!codeSent) onSendCode else ({}),
        )
        if (codeSent) {
            Spacer(Modifier.height(12.dp))
            ScreenSubtitle("${t["register_code_sent"] ?: "Verification code sent to"} $email")
            Spacer(Modifier.height(8.dp))
            TpidField(
                label = t["field_code"] ?: "CODE",
                value = code, onValueChange = onCode,
                placeholder = t["placeholder_code"] ?: "000000",
                error = error,
                keyboardType = KeyboardType.Number,
                onSubmit = onSubmit,
            )
        }
        Spacer(Modifier.height(16.dp))
        if (!codeSent) {
            TpidPrimaryButton(
                text = t["btn_send_code"] ?: "Send verification code",
                onClick = onSendCode,
                enabled = username.length >= 3 && password.length >= 8,
            )
        } else {
            TpidPrimaryButton(
                text = t["btn_create_account"] ?: "Create account",
                onClick = onSubmit,
                enabled = code.length == 6,
            )
            Spacer(Modifier.height(8.dp))
            TpidLinkButton(
                text = t["btn_resend_code"] ?: "Resend code",
                onClick = onSendCode,
                modifier = Modifier.fillMaxWidth().wrapContentWidth(Alignment.CenterHorizontally),
            )
        }
    }
}

@Composable
internal fun EmailCodeStep(
    t: Map<String, String>,
    email: String,
    code: String, onCode: (String) -> Unit,
    error: String?,
    onSubmit: () -> Unit,
) {
    Column(Modifier.fillMaxWidth()) {
        ScreenSubtitle("${t["email_code_sent"].orEmpty()} $email")
        Spacer(Modifier.height(24.dp))
        TpidField(
            label = t["field_code"] ?: "CODE",
            value = code, onValueChange = onCode,
            placeholder = t["placeholder_code"] ?: "000000",
            error = error,
            keyboardType = KeyboardType.Number,
            onSubmit = onSubmit,
        )
        Spacer(Modifier.height(16.dp))
        TpidPrimaryButton(
            text = t["btn_confirm"] ?: "Confirm",
            onClick = onSubmit,
            enabled = code.length == 6,
        )
    }
}

@Composable
internal fun TotpStep(
    t: Map<String, String>,
    totp: String, onTotp: (String) -> Unit,
    error: String?,
    onSubmit: () -> Unit,
) {
    Column(Modifier.fillMaxWidth()) {
        ScreenSubtitle(t["two_factor_hint"].orEmpty())
        Spacer(Modifier.height(24.dp))
        TpidField(
            label = t["field_totp"] ?: "CODE",
            value = totp, onValueChange = onTotp,
            placeholder = t["placeholder_code"] ?: "000000",
            error = error,
            keyboardType = KeyboardType.Number,
            onSubmit = onSubmit,
        )
        Spacer(Modifier.height(16.dp))
        TpidPrimaryButton(
            text = t["btn_confirm"] ?: "Confirm",
            onClick = onSubmit,
            enabled = totp.length == 6,
        )
    }
}

@Composable
internal fun PasskeyStep(t: Map<String, String>, onFallback: () -> Unit) {
    Column(Modifier.fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally) {
        ScreenSubtitle(t["passkey_hint"].orEmpty())
        Spacer(Modifier.height(32.dp))
        // 2.6.0 strict-monochrome: no green tint. Stroked `onBackground`
        // glyph reads the same on dark and light themes.
        SuccessGlyph(size = 64.dp)
        Spacer(Modifier.height(32.dp))
        TpidPrimaryButton(
            text = t["passkey_title"] ?: "Sign in with passkey",
            onClick = onFallback,
        )
        Spacer(Modifier.height(10.dp))
        TpidLinkButton(
            text = t["btn_use_password"] ?: "Use password",
            onClick = onFallback,
            modifier = Modifier.fillMaxWidth().wrapContentWidth(Alignment.CenterHorizontally),
        )
    }
}

@Composable
internal fun LoadingStep(message: String) {
    Column(
        Modifier.fillMaxWidth().padding(vertical = 48.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        CircularProgressIndicator(color = MaterialTheme.colorScheme.primary)
        Spacer(Modifier.height(16.dp))
        Text(
            message, fontSize = 14.sp,
            color = MaterialTheme.colorScheme.onBackground.copy(alpha = 0.7f),
        )
    }
}

@Composable
internal fun SuccessStep(t: Map<String, String>, email: String) {
    Column(
        Modifier.fillMaxWidth().padding(vertical = 32.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        // 2.6.0 strict-monochrome: no green success icon. Uses the same
        // stroked check glyph as every other step so the widget renders
        // truly black-and-white on both themes.
        SuccessGlyph(size = 64.dp)
        Spacer(Modifier.height(12.dp))
        Text(
            t["success_title"] ?: "Signed in",
            fontSize = 22.sp, fontWeight = FontWeight.Bold,
            color = MaterialTheme.colorScheme.onBackground,
        )
        if (email.isNotEmpty()) {
            Spacer(Modifier.height(4.dp))
            Text(email, fontSize = 13.sp, color = MaterialTheme.colorScheme.onBackground.copy(alpha = 0.6f))
        }
    }
}

@Composable
internal fun FatalStep(
    t: Map<String, String>,
    err: TpidError,
    onRetry: () -> Unit,
    onClose: () -> Unit,
) {
    Column(
        Modifier.fillMaxWidth().padding(vertical = 16.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Icon(
            Icons.Filled.Error, contentDescription = null,
            // 2.6.0: monochrome — bold title carries severity, icon moves
            // to `onBackground` so the red/pink accent is gone.
            tint = MaterialTheme.colorScheme.onBackground,
            modifier = Modifier.size(56.dp),
        )
        Spacer(Modifier.height(16.dp))
        Text(
            titleFor(err, t),
            fontSize = 20.sp, fontWeight = FontWeight.Bold,
            color = MaterialTheme.colorScheme.onBackground,
            textAlign = TextAlign.Center,
        )
        Spacer(Modifier.height(8.dp))
        Text(
            err.message ?: err.code,
            fontSize = 14.sp,
            color = MaterialTheme.colorScheme.onBackground.copy(alpha = 0.6f),
            textAlign = TextAlign.Center,
        )
        Spacer(Modifier.height(24.dp))
        TpidPrimaryButton(text = t["btn_try_again"] ?: "Try again", onClick = onRetry)
        Spacer(Modifier.height(8.dp))
        TpidSecondaryButton(text = t["btn_close"] ?: "Close", onClick = onClose)
    }
}

private fun titleFor(err: TpidError, t: Map<String, String>): String {
    val key = when (err) {
        is TpidError.NoNetwork -> "err_title_network"
        is TpidError.Timeout -> "err_title_timeout"
        is TpidError.AccountLocked -> "err_title_locked"
        is TpidError.EmailNotVerified -> "err_title_not_verified"
        is TpidError.RateLimited -> "err_title_rate_limited"
        is TpidError.PhishingDetected -> "err_title_phishing"
        is TpidError.ServerError -> "err_title_server"
        is TpidError.ConfigurationError -> "err_title_config"
        is TpidError.OAuthError -> "err_title_oauth"
        else -> "err_title_generic"
    }
    return t[key] ?: "Error"
}

@Composable
private fun ScreenSubtitle(text: String) {
    if (text.isBlank()) return
    Text(
        text = text,
        fontSize = 14.sp,
        color = MaterialTheme.colorScheme.onBackground.copy(alpha = 0.6f),
        textAlign = TextAlign.Center,
        modifier = Modifier.fillMaxWidth(),
    )
}

@Composable
private fun EmailChip(email: String) {
    val isDark = MaterialTheme.colorScheme.background.luminance() < 0.5f
    val bg = if (isDark) Color(0x14FFFFFF) else Color(0x0F000000)
    val fg = if (isDark) Color.White.copy(alpha = 0.7f) else Color(0xB3000000)
    Row(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .background(bg)
            .padding(horizontal = 16.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(email, color = fg, fontSize = 14.sp, fontWeight = FontWeight.Medium)
    }
}

/**
 * QR login step. The widget has asked the server for a fresh session; the
 * server returned a [qrUrl] that, when visited from an already-signed-in
 * mobile device, confirms the desktop sign-in.
 *
 * States, driven by [status]:
 *  - `"loading"`  — initial session POST in flight, spinner shown.
 *  - `"pending"`  — QR visible, desktop polling `login-poll/:sessionId`.
 *  - `"expired"`  — red badge with a Refresh button.
 *  - `"approved"` — brief "confirmed on your phone" flash before the
 *                   outer state-machine transitions to Success.
 *  - `"error"`    — human-readable [error] + Retry button.
 */
@Composable
internal fun QrStep(
    t: Map<String, String>,
    qrUrl: String?,
    qrImage: ImageBitmap?,
    status: String,
    error: String?,
    onRefresh: () -> Unit,
    onPaste: (String) -> Unit,
) {
    Column(
        Modifier.fillMaxWidth(),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        ScreenSubtitle(t["qr_title"] ?: "Sign in with QR code")
        Spacer(Modifier.height(6.dp))
        Text(
            t["qr_hint"]
                ?: "On a device where you are already signed in, open id.tokenpay.space and scan this code.",
            fontSize = 12.sp,
            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.65f),
            textAlign = TextAlign.Center,
            modifier = Modifier.fillMaxWidth().padding(horizontal = 8.dp),
        )
        val secondary = t["qr_hint_secondary"]
        if (!secondary.isNullOrBlank()) {
            Spacer(Modifier.height(4.dp))
            Text(
                secondary,
                fontSize = 11.sp,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.4f),
                textAlign = TextAlign.Center,
                modifier = Modifier.fillMaxWidth().padding(horizontal = 8.dp),
            )
        }
        Spacer(Modifier.height(16.dp))

        val isDark = MaterialTheme.colorScheme.background.luminance() < 0.5f
        val panelBg = if (isDark) Color.White else Color(0xFFF5F5F7)
        val panelBorder = if (isDark) Color.White.copy(alpha = 0.08f) else Color(0x14000000)
        Box(
            modifier = Modifier
                .size(220.dp)
                .clip(RoundedCornerShape(16.dp))
                .background(panelBg)
                .border(1.dp, panelBorder, RoundedCornerShape(16.dp)),
            contentAlignment = Alignment.Center,
        ) {
            when {
                status == "expired" -> Text(
                    t["qr_status_expired"] ?: "QR code expired",
                    fontSize = 13.sp, fontWeight = FontWeight.SemiBold,
                    // 2.6.0: panel is light in both themes — black text
                    // is the monochrome-safe choice.
                    color = Color(0xFF0B0B0D),
                    textAlign = TextAlign.Center,
                )
                status == "error" -> Text(
                    error ?: (t["qr_status_error"] ?: "Couldn't start QR session"),
                    fontSize = 12.sp,
                    fontWeight = FontWeight.SemiBold,
                    color = Color(0xFF0B0B0D),
                    textAlign = TextAlign.Center,
                    modifier = Modifier.padding(12.dp),
                )
                qrImage != null -> Image(
                    bitmap = qrImage,
                    contentDescription = null,
                    contentScale = ContentScale.Fit,
                    filterQuality = FilterQuality.None,
                    modifier = Modifier.size(200.dp).padding(4.dp),
                )
                else -> CircularProgressIndicator(
                    color = Color(0xFF0B0B0D),
                    modifier = Modifier.size(36.dp),
                )
            }
        }

        Spacer(Modifier.height(14.dp))
        val statusKey = when (status) {
            "pending"  -> "qr_status_pending"
            "approved" -> "qr_status_approved"
            "expired"  -> "qr_status_expired"
            "error"    -> "qr_status_error"
            else       -> "qr_status_pending"
        }
        Text(
            t[statusKey] ?: "Waiting for your phone…",
            fontSize = 12.sp,
            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f),
            textAlign = TextAlign.Center,
        )

        Spacer(Modifier.height(18.dp))
        if (status == "expired" || status == "error") {
            TpidPrimaryButton(
                text = t["qr_refresh"] ?: "Refresh",
                onClick = onRefresh,
                leadingIcon = { Icon(Icons.Filled.Refresh, contentDescription = null, modifier = Modifier.size(16.dp)) },
            )
            Spacer(Modifier.height(10.dp))
        }
        TpidSecondaryButton(
            text = t["qr_paste"] ?: "Paste QR link",
            onClick = {
                runCatching {
                    val clip = Toolkit.getDefaultToolkit().systemClipboard
                    val data = clip.getData(DataFlavor.stringFlavor) as? String
                    if (!data.isNullOrBlank()) onPaste(data.trim())
                }
            },
            leadingIcon = { Icon(Icons.Filled.ContentPaste, contentDescription = null, modifier = Modifier.size(16.dp)) },
        )
    }
}

@Composable
private fun FooterInline(muted: String, link: String, onClick: () -> Unit) {
    val isDark = MaterialTheme.colorScheme.background.luminance() < 0.5f
    val mutedCol = if (isDark) Color.White.copy(alpha = 0.4f) else Color(0x7F000000)
    val linkCol = if (isDark) Color.White else Color(0xFF0B0B0D)
    val annotated = buildAnnotatedString {
        withStyle(SpanStyle(color = mutedCol)) { append(muted); append(' ') }
        withStyle(SpanStyle(color = linkCol, fontWeight = FontWeight.Bold)) { append(link) }
    }
    Row(
        Modifier.fillMaxWidth().clickable(onClick = onClick),
        horizontalArrangement = Arrangement.Center,
    ) {
        Text(annotated, fontSize = 13.sp)
    }
}
