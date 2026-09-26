package space.tokenpay.id.ui.screens

import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.ContentPaste
import androidx.compose.material.icons.filled.ErrorOutline
import androidx.compose.material.icons.filled.Fingerprint
import androidx.compose.material.icons.filled.QrCode2
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import space.tokenpay.id.TpidError
import space.tokenpay.id.ui.WidgetState
import space.tokenpay.id.ui.WidgetViewModel
import space.tokenpay.id.ui.components.*

/* =========================================================================
 * WELCOME — first screen. Войти / Создать аккаунт / Открыть сайт (image 4).
 * ========================================================================= */

/* =========================================================================
 * RETURNING USER — "Continue as X" / "Use another account" card (2.6.0).
 *
 * Shown when [WidgetViewModel.initialState] found a `LastAccount` profile in
 * [SecureStorage]. The primary CTA takes the user straight to the password
 * screen for the remembered email; secondary links clear the slot or jump
 * to the full email form. Deliberately no "Create account" CTA here —
 * returning users are signing in, not signing up.
 * ========================================================================= */

@Composable
internal fun ReturningUserScreen(state: WidgetState, vm: WidgetViewModel) {
    val t = state.strings
    val last = state.lastAccount ?: run {
        // Defensive: if we somehow landed here with no profile, fall back to
        // the regular welcome.
        vm.useAnotherAccount(); return
    }
    val displayName = last.displayName?.takeIf { it.isNotBlank() } ?: last.email
    val continueFormat = t["welcome_continue_as"] ?: "Continue as %s"
    val continueLabel = runCatching { continueFormat.format(displayName) }
        .getOrDefault("Continue as $displayName")
    val ageMs = System.currentTimeMillis() - last.lastAuthenticatedAtMs
    val hintKey = when {
        last.lastAuthenticatedAtMs > 0L && ageMs in 0L..86_400_000L -> "remembered_session_hint"
        last.lastAuthenticatedAtMs > 0L && ageMs in 0L..604_800_000L -> "remembered_code_hint"
        else -> "remembered_password_hint"
    }

    Column(Modifier.fillMaxWidth()) {
        ScreenSubtitle(t.getOrDefault("signin_title", "Welcome back"))
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
                if (last.email != displayName) {
                    Spacer(Modifier.height(4.dp))
                    Text(last.email, fontSize = 12.sp,
                        color = MaterialTheme.colorScheme.onBackground.copy(alpha = 0.6f))
                }
            }
        }
        Spacer(Modifier.height(12.dp))
        Text(t[hintKey].orEmpty(), fontSize = 11.sp,
            color = MaterialTheme.colorScheme.onBackground.copy(alpha = 0.55f))
        Spacer(Modifier.height(20.dp))
        state.error?.let { TpidErrorBanner(it); Spacer(Modifier.height(12.dp)) }
        TpidPrimaryButton(
            text = continueLabel,
            onClick = { vm.continueAsLast() },
            leadingIcon = { ArrowIcon() },
        )
        Spacer(Modifier.height(10.dp))
        TpidSecondaryButton(
            text = t.getOrDefault("welcome_other_account", "Use another account"),
            onClick = { vm.useAnotherAccount() },
        )
        Spacer(Modifier.height(14.dp))
        TpidLinkButton(
            text = t.getOrDefault("alt_qr", "Sign in with QR code"),
            onClick = { vm.goQr() },
            modifier = Modifier.fillMaxWidth().wrapContentWidth(Alignment.CenterHorizontally),
        )
        Spacer(Modifier.height(4.dp))
        TpidLinkButton(
            text = t.getOrDefault("welcome_forget", "Forget this account"),
            onClick = { vm.forgetLastAccount() },
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
        Modifier
            .size(48.dp)
            .clip(RoundedCornerShape(24.dp))
            .background(bg),
        contentAlignment = Alignment.Center,
    ) {
        Text(letter, fontSize = 22.sp, fontWeight = FontWeight.Bold, color = fg)
    }
}

@Composable
internal fun WelcomeScreen(state: WidgetState, vm: WidgetViewModel) {
    val t = state.strings
    val ctx = LocalContext.current
    Column(Modifier.fillMaxWidth()) {
        ScreenSubtitle(t.getOrDefault("welcome_subtitle", ""))
        Spacer(Modifier.height(28.dp))
        TpidPrimaryButton(
            text = t.getOrDefault("welcome_sign_in", "Sign in"),
            onClick = { vm.goEmail() },
            leadingIcon = { ArrowIcon() },
        )
        Spacer(Modifier.height(12.dp))
        TpidSecondaryButton(
            text = t.getOrDefault("welcome_create", "Create account"),
            onClick = { vm.goRegister() },
            leadingIcon = { PersonPlusIcon() },
        )
        Spacer(Modifier.height(12.dp))
        TpidSecondaryButton(
            text = t.getOrDefault("alt_qr", "Sign in with QR code"),
            onClick = { vm.goQr() },
            leadingIcon = { Icon(Icons.Default.QrCode2, contentDescription = null, modifier = Modifier.size(18.dp)) },
        )
        TpidOrDivider(t.getOrDefault("welcome_or", "or"))
        TpidLinkButton(
            text = t.getOrDefault("welcome_open_web", "Open tokenpay.space"),
            onClick = {
                runCatching {
                    ctx.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse("https://tokenpay.space/")))
                }
            },
            modifier = Modifier.fillMaxWidth().wrapContentWidth(Alignment.CenterHorizontally),
        )
    }
}

/* =========================================================================
 * EMAIL — "Войдите в аккаунт" + email field + "Далее" + QR (image 5).
 * ========================================================================= */

@Composable
internal fun EmailScreen(state: WidgetState, vm: WidgetViewModel) {
    val t = state.strings
    Column(Modifier.fillMaxWidth()) {
        ScreenSubtitle(t.getOrDefault("signin_title", "Sign in"))
        Spacer(Modifier.height(24.dp))
        TpidField(
            label = t.getOrDefault("field_email", "EMAIL"),
            value = state.email,
            onValueChange = vm::updateEmail,
            placeholder = t.getOrDefault("placeholder_email", "you@example.com"),
            error = state.error,
            keyboardType = KeyboardType.Email,
            imeAction = ImeAction.Go,
            onSubmit = vm::submitEmail,
        )
        Spacer(Modifier.height(16.dp))
        TpidPrimaryButton(
            text = t.getOrDefault("btn_next", "Next"),
            onClick = vm::submitEmail,
            enabled = state.email.length >= 3,
        )
        TpidOrDivider(t.getOrDefault("alt_divider", "or"))
        TpidSecondaryButton(
            text = t.getOrDefault("alt_qr", "Sign in with QR code"),
            onClick = { vm.goQr() },
            leadingIcon = { Icon(Icons.Default.QrCode2, contentDescription = null, modifier = Modifier.size(18.dp)) },
        )
        Spacer(Modifier.height(20.dp))
        FooterInline(
            muted = t.getOrDefault("footer_no_account", "No account?"),
            link = t.getOrDefault("footer_create", "Create one"),
            onClick = vm::goRegister,
        )
    }
}

/* =========================================================================
 * PASSWORD — "Введите пароль". Field + Далее + back + "забыли пароль".
 * ========================================================================= */

@Composable
internal fun PasswordScreen(state: WidgetState, vm: WidgetViewModel) {
    val t = state.strings
    Column(Modifier.fillMaxWidth()) {
        EmailChip(state.email)
        Spacer(Modifier.height(24.dp))
        TpidField(
            label = t.getOrDefault("field_password", "PASSWORD"),
            value = state.password,
            onValueChange = vm::updatePassword,
            placeholder = t.getOrDefault("placeholder_password", "Your password"),
            error = state.error,
            keyboardType = KeyboardType.Password,
            imeAction = ImeAction.Go,
            password = true,
            onSubmit = vm::submitPassword,
        )
        Spacer(Modifier.height(16.dp))
        TpidPrimaryButton(
            text = t.getOrDefault("btn_sign_in", "Sign in"),
            onClick = vm::submitPassword,
            enabled = state.password.length >= 8,
        )
        Spacer(Modifier.height(10.dp))
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
            // The previous "Use email code" link started a password-less
            // login flow that the real backend doesn't support (it always
            // requires the password first, then an e-mail OTP as a second
            // factor). Leaving only "Forgot?" keeps the screen honest.
            TpidLinkButton(t.getOrDefault("btn_forgot", "Forgot?"), vm::switchToRecovery)
        }
    }
}

/* =========================================================================
 * EMAIL CODE — 6-digit field + Подтвердить + Resend.
 * ========================================================================= */

@Composable
internal fun EmailCodeScreen(state: WidgetState, vm: WidgetViewModel) {
    val t = state.strings
    Column(Modifier.fillMaxWidth()) {
        ScreenSubtitle(
            buildString {
                append(t.getOrDefault("email_code_sent", "Code sent to"))
                append(' ')
                append(state.email)
            },
        )
        Spacer(Modifier.height(24.dp))
        TpidField(
            label = t.getOrDefault("field_code", "CODE FROM EMAIL"),
            value = state.code,
            onValueChange = vm::updateCode,
            placeholder = t.getOrDefault("placeholder_code", "000000"),
            error = state.error,
            keyboardType = KeyboardType.NumberPassword,
            imeAction = ImeAction.Go,
            onSubmit = vm::submitEmailCode,
        )
        Spacer(Modifier.height(16.dp))
        TpidPrimaryButton(
            text = t.getOrDefault("btn_confirm", "Confirm"),
            onClick = vm::submitEmailCode,
            enabled = state.code.length == 6,
        )
        Spacer(Modifier.height(12.dp))
        TpidLinkButton(
            t.getOrDefault("btn_resend", "Resend code"),
            vm::requestEmailCode,
            modifier = Modifier.fillMaxWidth().wrapContentWidth(Alignment.CenterHorizontally),
        )
    }
}

/* =========================================================================
 * 2FA TOTP.
 * ========================================================================= */

@Composable
internal fun TwoFactorScreen(state: WidgetState, vm: WidgetViewModel) {
    val t = state.strings
    Column(Modifier.fillMaxWidth()) {
        ScreenSubtitle(t.getOrDefault("two_factor_hint", ""))
        Spacer(Modifier.height(24.dp))
        TpidField(
            label = t.getOrDefault("field_totp", "CODE FROM APP"),
            value = state.totp,
            onValueChange = vm::updateTotp,
            placeholder = t.getOrDefault("placeholder_code", "000000"),
            error = state.error,
            keyboardType = KeyboardType.NumberPassword,
            imeAction = ImeAction.Go,
            onSubmit = vm::submitTotp,
        )
        Spacer(Modifier.height(16.dp))
        TpidPrimaryButton(
            text = t.getOrDefault("btn_confirm", "Confirm"),
            onClick = vm::submitTotp,
            enabled = state.totp.length == 6,
        )
    }
}

/* =========================================================================
 * PASSKEY.
 * ========================================================================= */

@Composable
internal fun PasskeyScreen(state: WidgetState, vm: WidgetViewModel) {
    val t = state.strings
    Column(
        Modifier.fillMaxWidth(),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        ScreenSubtitle(t.getOrDefault("passkey_hint", ""))
        Spacer(Modifier.height(24.dp))
        Icon(
            imageVector = Icons.Default.Fingerprint,
            contentDescription = null,
            // 2.6.0: use `onBackground` instead of `primary` — on the dark
            // theme `primary` was white-on-black so it looked fine, but on
            // light theme `primary` was near-black on near-white and the
            // fingerprint disappeared into the card. `onBackground` is
            // guaranteed to contrast with whatever the widget surface is.
            tint = MaterialTheme.colorScheme.onBackground,
            modifier = Modifier.size(72.dp),
        )
        Spacer(Modifier.height(24.dp))
        state.error?.let { TpidErrorBanner(it); Spacer(Modifier.height(12.dp)) }
        TpidPrimaryButton(
            text = t.getOrDefault("passkey_title", "Sign in with passkey"),
            onClick = { vm.resetToStart() },
        )
        Spacer(Modifier.height(8.dp))
        TpidLinkButton(
            t.getOrDefault("btn_use_password", "Use password"),
            onClick = { vm.resetToStart() },
            modifier = Modifier.fillMaxWidth().wrapContentWidth(Alignment.CenterHorizontally),
        )
    }
}

/* =========================================================================
 * SIGN-UP — two-phase: credentials → verification code.
 * ========================================================================= */

/**
 * Register screen. Appears automatically when [WidgetViewModel.submitEmail]
 * sees an account-check response with `exists = false`.
 *
 * Phase A (`codeSent = false`) — user sets display name and password, then
 * clicks "Send verification code". The fields freeze.
 *
 * Phase B (`codeSent = true`) — a 6-digit code input is revealed; the primary
 * button morphs to "Create account" and fires `/auth/register`.
 */
@Composable
internal fun RegisterScreen(state: WidgetState, vm: WidgetViewModel, codeSent: Boolean) {
    val t = state.strings
    val emailOnFile = state.email.isNotBlank()
    Column(Modifier.fillMaxWidth()) {
        ScreenSubtitle(t.getOrDefault("register_title", "Create your account"))
        Spacer(Modifier.height(10.dp))
        // Clarifies to the user why the widget is on the sign-up form when
        // all they did was enter an unknown email. Shown only in phase A.
        if (!codeSent) {
            Text(
                t.getOrDefault(
                    "register_hint",
                    "This email isn't registered yet — fill in the form below to create a new account.",
                ),
                fontSize = 12.sp,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f),
                textAlign = TextAlign.Center,
                modifier = Modifier.fillMaxWidth(),
            )
            Spacer(Modifier.height(14.dp))
        }
        if (emailOnFile) {
            EmailChip(state.email)
        } else {
            TpidField(
                label = t.getOrDefault("field_email", "EMAIL"),
                value = state.email,
                onValueChange = vm::updateEmail,
                placeholder = t.getOrDefault("placeholder_email", "you@example.com"),
                error = if (!codeSent) state.error else null,
                enabled = !codeSent,
                keyboardType = KeyboardType.Email,
            )
            Spacer(Modifier.height(12.dp))
        }
        Spacer(Modifier.height(16.dp))
        TpidField(
            label = t.getOrDefault("field_username", "USERNAME"),
            value = state.regUsername,
            onValueChange = vm::updateRegUsername,
            placeholder = t.getOrDefault("placeholder_username", "your_login"),
            error = if (!codeSent) state.error else null,
            enabled = !codeSent,
        )
        Text(
            t.getOrDefault(
                "hint_username",
                "Lowercase letters, digits, dots, underscores (3-30)",
            ),
            fontSize = 11.sp,
            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.45f),
            modifier = Modifier
                .fillMaxWidth()
                .padding(start = 4.dp, top = 4.dp),
        )
        Spacer(Modifier.height(12.dp))
        TpidField(
            label = t.getOrDefault("field_password", "PASSWORD"),
            value = state.regPassword,
            onValueChange = vm::updateRegPassword,
            placeholder = t.getOrDefault("placeholder_password_new", "At least 8 characters"),
            error = if (!codeSent) state.error else null,
            enabled = !codeSent,
            keyboardType = KeyboardType.Password,
            password = true,
            imeAction = if (!codeSent) ImeAction.Go else ImeAction.Next,
            onSubmit = { if (!codeSent) vm.sendRegisterCode() },
        )
        if (codeSent) {
            Spacer(Modifier.height(12.dp))
            ScreenSubtitle(
                buildString {
                    append(t.getOrDefault("register_code_sent", "Verification code sent to"))
                    append(' ')
                    append(state.email)
                },
            )
            Spacer(Modifier.height(8.dp))
            TpidField(
                label = t.getOrDefault("field_code", "CODE"),
                value = state.regCode,
                onValueChange = vm::updateRegCode,
                placeholder = t.getOrDefault("placeholder_code", "000000"),
                error = state.error,
                keyboardType = KeyboardType.NumberPassword,
                imeAction = ImeAction.Go,
                onSubmit = vm::submitRegister,
            )
        }
        Spacer(Modifier.height(16.dp))
        if (!codeSent) {
            TpidPrimaryButton(
                text = t.getOrDefault("btn_send_code", "Send verification code"),
                onClick = vm::sendRegisterCode,
                enabled = state.regUsername.length >= 3 && state.regPassword.length >= 8,
            )
        } else {
            TpidPrimaryButton(
                text = t.getOrDefault("btn_create_account", "Create account"),
                onClick = vm::submitRegister,
                enabled = state.regCode.length == 6,
            )
            Spacer(Modifier.height(8.dp))
            TpidLinkButton(
                t.getOrDefault("btn_resend_code", "Resend code"),
                onClick = vm::sendRegisterCode,
                modifier = Modifier.fillMaxWidth().wrapContentWidth(Alignment.CenterHorizontally),
            )
        }
    }
}

/* =========================================================================
 * RECOVERY.
 * ========================================================================= */

@Composable
internal fun RecoveryScreen(state: WidgetState, vm: WidgetViewModel) {
    val t = state.strings
    Column(Modifier.fillMaxWidth()) {
        ScreenSubtitle(
            buildString {
                append(t.getOrDefault("email_code_sent", ""))
                append(' '); append(state.email)
            },
        )
        Spacer(Modifier.height(24.dp))
        state.error?.let { TpidErrorBanner(it); Spacer(Modifier.height(12.dp)) }
        TpidPrimaryButton(
            text = t.getOrDefault("btn_send_recovery", "Send recovery email"),
            onClick = { vm.switchToEmailCode() },
        )
        Spacer(Modifier.height(12.dp))
        TpidLinkButton(
            t.getOrDefault("btn_back_signin", "Back to sign-in"),
            vm::resetToStart,
            modifier = Modifier.fillMaxWidth().wrapContentWidth(Alignment.CenterHorizontally),
        )
    }
}

/* =========================================================================
 * QR LOGIN. Displays the QR image the server returned by
 * `/auth/qr/login-init`; the host VM is responsible for polling.
 * ========================================================================= */

@Composable
internal fun QrScreen(state: WidgetState, vm: WidgetViewModel) {
    val t = state.strings
    val ctx = LocalContext.current
    Column(
        Modifier.fillMaxWidth(),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        ScreenSubtitle(t.getOrDefault("qr_title", "Sign in with QR code"))
        Spacer(Modifier.height(6.dp))
        Text(
            t.getOrDefault(
                "qr_hint",
                "On a device where you are already signed in, open id.tokenpay.space and scan this code.",
            ),
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
                state.qrStatus == "expired" -> Text(
                    t.getOrDefault("qr_status_expired", "QR code expired"),
                    fontSize = 13.sp, fontWeight = FontWeight.SemiBold,
                    // Inverted panel → use `onBackground`-on-`surface` so the
                    // text stays readable regardless of theme without an
                    // accent colour (2.6.0 strict-monochrome spec).
                    color = if (isDark) Color(0xFF0B0B0D) else Color(0xFF0B0B0D),
                    textAlign = TextAlign.Center,
                )
                state.qrStatus == "error" -> Text(
                    state.error ?: t.getOrDefault("qr_status_error", "Couldn't start QR session"),
                    fontSize = 12.sp,
                    color = Color(0xFF0B0B0D),
                    fontWeight = FontWeight.SemiBold,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.padding(12.dp),
                )
                state.qrImage != null -> Image(
                    bitmap = state.qrImage,
                    contentDescription = null,
                    contentScale = ContentScale.Fit,
                    modifier = Modifier.size(200.dp).padding(4.dp),
                )
                else -> CircularProgressIndicator(
                    color = Color(0xFF0B0B0D),
                    strokeWidth = 2.dp,
                    modifier = Modifier.size(36.dp),
                )
            }
        }

        Spacer(Modifier.height(14.dp))
        val statusKey = when (state.qrStatus) {
            "approved" -> "qr_status_approved"
            "expired"  -> "qr_status_expired"
            "error"    -> "qr_status_error"
            else       -> "qr_status_pending"
        }
        Text(
            t.getOrDefault(statusKey, "Waiting for your phone…"),
            fontSize = 12.sp,
            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f),
            textAlign = TextAlign.Center,
        )

        Spacer(Modifier.height(18.dp))
        if (state.qrStatus == "expired" || state.qrStatus == "error") {
            TpidPrimaryButton(
                text = t.getOrDefault("qr_refresh", "Refresh"),
                onClick = vm::refreshQr,
                leadingIcon = { Icon(Icons.Default.Refresh, contentDescription = null, modifier = Modifier.size(16.dp)) },
            )
            Spacer(Modifier.height(10.dp))
        }
        TpidSecondaryButton(
            text = t.getOrDefault("qr_paste", "Paste QR link"),
            onClick = {
                val clip = ctx.getSystemService(Context.CLIPBOARD_SERVICE) as? ClipboardManager
                val primary = clip?.primaryClip
                val raw = if (primary != null && primary.itemCount > 0)
                    primary.getItemAt(0).coerceToText(ctx).toString() else null
                if (!raw.isNullOrBlank()) vm.pasteQrLink(raw.trim())
            },
            leadingIcon = { Icon(Icons.Default.ContentPaste, contentDescription = null, modifier = Modifier.size(16.dp)) },
        )
    }
}

/* =========================================================================
 * LOADING / SUCCESS / FATAL ERROR.
 * ========================================================================= */

/**
 * 2.6.2 — Loading screen now exposes a "Cancel" link button.
 *
 * Without it, a stuck network call on a flaky mobile network left the
 * user staring at an indeterminate spinner with no way out except force-
 * killing the app (system-back used to invoke `cancel()`, which closed
 * the entire widget and lost the typed credentials). Tap "Cancel" →
 * VM aborts the in-flight job and routes back to the form the loading
 * was initiated from. Internal hard-timeout ([WidgetViewModel.LOGIN_TIMEOUT_MS])
 * still kicks in if the user waits.
 */
@Composable
internal fun LoadingScreen(message: String, state: WidgetState? = null, vm: WidgetViewModel? = null) {
    Column(
        Modifier.fillMaxWidth().padding(vertical = 48.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        CircularProgressIndicator(color = MaterialTheme.colorScheme.primary)
        Spacer(Modifier.height(16.dp))
        Text(message, fontSize = 14.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
        if (vm != null) {
            Spacer(Modifier.height(20.dp))
            val label = state?.strings?.get("btn_cancel_loading") ?: "Cancel"
            TpidLinkButton(
                text = label,
                onClick = { vm.cancelLoading() },
                modifier = Modifier.fillMaxWidth().wrapContentWidth(Alignment.CenterHorizontally),
            )
        }
    }
}

@Composable
internal fun SuccessScreen(state: WidgetState) {
    val t = state.strings
    Column(
        Modifier.fillMaxWidth().padding(vertical = 32.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        // 2.6.0: strict B&W theme — no green success tint. Monochrome
        // stroked check on an `onBackground`-tinted circle reads equally
        // well on dark and light themes and aligns with the "colorless"
        // brand guideline from CUPOL.
        SuccessGlyph(size = 72.dp)
        Spacer(Modifier.height(16.dp))
        Text(
            t.getOrDefault("success_title", "Signed in"),
            fontSize = 22.sp, fontWeight = FontWeight.Bold,
            color = MaterialTheme.colorScheme.onBackground,
        )
        if (state.email.isNotBlank()) {
            Spacer(Modifier.height(4.dp))
            Text(state.email, fontSize = 13.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
internal fun FatalErrorScreen(
    error: TpidError,
    state: WidgetState,
    onRetry: () -> Unit,
    onClose: () -> Unit,
) {
    val t = state.strings
    Column(
        Modifier.fillMaxWidth().padding(vertical = 24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Icon(
            imageVector = Icons.Default.ErrorOutline,
            contentDescription = null,
            // 2.6.0: monochrome — no red tint on fatal error. The bold title
            // text below already communicates severity, and colour-blind
            // users lose nothing when the icon moves to `onBackground`.
            tint = MaterialTheme.colorScheme.onBackground,
            modifier = Modifier.size(64.dp),
        )
        Spacer(Modifier.height(16.dp))
        Text(
            titleFor(error, t),
            fontSize = 20.sp, fontWeight = FontWeight.Bold, textAlign = TextAlign.Center,
            color = MaterialTheme.colorScheme.onBackground,
        )
        Spacer(Modifier.height(8.dp))
        Text(
            error.message ?: "",
            fontSize = 14.sp,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center,
        )
        Spacer(Modifier.height(24.dp))
        TpidPrimaryButton(text = t.getOrDefault("btn_try_again", "Try again"), onClick = onRetry)
        Spacer(Modifier.height(8.dp))
        TpidSecondaryButton(text = t.getOrDefault("btn_close", "Close"), onClick = onClose)
    }
}

/* =========================================================================
 * Helpers.
 * ========================================================================= */

@Composable
private fun ScreenSubtitle(text: String) {
    if (text.isBlank()) return
    Text(
        text = text,
        fontSize = 14.sp,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
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

@Composable
private fun FooterInline(muted: String, link: String, onClick: () -> Unit) {
    val mutedCol = if (MaterialTheme.colorScheme.background.luminance() < 0.5f)
        Color.White.copy(alpha = 0.4f) else Color(0x7F000000)
    val linkCol = if (MaterialTheme.colorScheme.background.luminance() < 0.5f)
        Color.White else Color(0xFF0B0B0D)
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

@Composable
private fun ArrowIcon() {
    val isDark = MaterialTheme.colorScheme.background.luminance() < 0.5f
    val tint = if (isDark) Color(0xFF0B0B0D) else Color.White
    androidx.compose.foundation.Canvas(Modifier.size(18.dp)) {
        val w = size.width; val h = size.height
        val p = androidx.compose.ui.graphics.Path().apply {
            // → arrow
            moveTo(w * 0.15f, h * 0.5f); lineTo(w * 0.75f, h * 0.5f)
            moveTo(w * 0.55f, h * 0.25f); lineTo(w * 0.8f,  h * 0.5f); lineTo(w * 0.55f, h * 0.75f)
        }
        drawPath(p, color = tint, style = androidx.compose.ui.graphics.drawscope.Stroke(width = 2.5f))
    }
}

@Composable
private fun PersonPlusIcon() {
    val isDark = MaterialTheme.colorScheme.background.luminance() < 0.5f
    val tint = if (isDark) Color.White else Color(0xFF0B0B0D)
    androidx.compose.foundation.Canvas(Modifier.size(18.dp)) {
        val w = size.width; val h = size.height
        drawCircle(color = tint, radius = h * 0.18f,
            center = androidx.compose.ui.geometry.Offset(w * 0.4f, h * 0.3f),
            style = androidx.compose.ui.graphics.drawscope.Stroke(width = 2f))
        val p = androidx.compose.ui.graphics.Path().apply {
            moveTo(w * 0.1f, h * 0.85f); cubicTo(w * 0.2f, h * 0.55f, w * 0.6f, h * 0.55f, w * 0.7f, h * 0.85f)
            moveTo(w * 0.78f, h * 0.28f); lineTo(w * 0.95f, h * 0.28f)
            moveTo(w * 0.865f, h * 0.19f); lineTo(w * 0.865f, h * 0.37f)
        }
        drawPath(p, color = tint, style = androidx.compose.ui.graphics.drawscope.Stroke(width = 2f))
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
    return t.getOrDefault(key, "Error")
}
