# TOKEN PAY ID — Android SDK (Kotlin, Jetpack Compose)

**Version:** `3.0.0` · **API compatibility:** existing `/api/v1` auth contracts remain in use

## 3.0.0

- Reworked the saved-account screen into a compact account card with clear next-step guidance, QR access, and rounded actions. The widget keeps its black-and-white palette in both themes.
- Saved sessions are accepted only for the matching account and a valid remembered-login window. Older sessions continue through email code or password as before.
- Removed the dead-end native passkey prompt. The service supports passkeys on the hosted web sign-in; the native widget offers working password, email-code, QR, and 2FA paths.
- This release does not change the integrator-facing `TpidAuth`, `TpidWidget`, or `TpidResult` API.

## Previous release notes

> **2.5.0-pre.4 changes**
> - **Sign-up restored** — every no-account email now opens a dedicated `RegisterScreen` instead of the password step (which always 401'd). Two-phase UI: credentials → verification code → `POST /auth/register`.
> - `ApiClient.register(email, password, username, emailCode, clientId, lang)` returns `TpidResult.Success` directly; token parser now accepts both camelCase and snake_case keys.
> - `WidgetViewModel`: new `sendRegisterCode()`, `submitRegister()`, `updateRegUsername/Password/Code()`; `back()` bounces Register → Email.
> - `TpidField(enabled:)` — freezes the field at 55 % alpha (read-only) after the code has been sent so users can't silently edit values mid-flow.
> - **Bundled wordmarks regenerated** — solid-fill black and white at 1024×154 (aspect 6.649), both derived from the single canonical web wordmark. DARK and LIGHT buttons are now visually symmetric.
> - New translation keys across en/ru/zh: `register_title`, `register_code_sent`, `field_username`, `placeholder_username`, `placeholder_password_new`, `btn_send_code`, `btn_create_account`, `btn_resend_code`, `error_username_short`, `loading_creating`.
> - User-Agent / X-TPID-SDK header now emits `android:2.5.0-pre.4`.

> **2.5.0-pre.3 changes (bug-fix release — CUPOL VPN report)**
> - **blocker** — `/api/v1/auth/magic-link/{request,verify}` replaced with `/api/v1/auth/send-code` + `/api/v1/auth/verify`. The old paths never shipped and returned `404 Endpoint not found` on every email-code flow.
> - **blocker** — `/auth/send-code` now forwards the required `type` field (`"login"` / `"register"`) through `WidgetViewModel.requestEmailCode`; the value is auto-detected from the cached `accountCheck.exists`.
> - **build-break** — `TpidError.Unknown(val cause: …)` renamed to `throwable` so Kotlin 2.1 stops rejecting the whole SDK with "`cause` hides member of supertype `Throwable`".
> - **crash-on-launch** — added `com.google.android.material:material:1.11.0` so the manifest-declared `Theme.Material3.DayNight.NoActionBar` actually resolves at runtime.
> - **UX** — password-reveal (eye) toggle now built into `TpidField`; state survives rotation via `rememberSaveable`.
> - **UX** — `TpidLoginButton`: border bumped to 2dp × 28% alpha (up from 1.5dp × 18%), wordmark 18/22/26 dp (up from 16/20/24), pill heights 40/48/56 dp.
> - User-Agent / X-TPID-SDK header now emits `android:2.5.0-pre.3`.

> **2.5.0-pre.2 changes**
> - Comfortaa variable TTF bundled (`res/font/comfortaa_variable.ttf`) and wired into `MaterialTheme` typography.
> - Animated fade+slide transitions between widget steps (matches JVM + iOS).
> - New `RemoteConfig` class (`internal.RemoteConfig`) consumes the `remote` section of `/api/v1/sdk/config` — theme tokens, per-language string overrides, feature flags and min/recommended SDK version propagate without a rebuild on the integrator's side.
> - `TpidLoginButton`: matched 1.5dp × 18%-alpha borders on DARK and LIGHT, enlarged wordmark (16/20/24 dp), white-tinted saturn glyph on `IconOnly`, spring-scale press animation.
> - User-Agent / X-TPID-SDK header now emits `android:2.5.0-pre.2`.
**Min SDK:** 24 (Android 7.0)
**Target SDK:** 34 (Android 14)
**Kotlin:** 1.9.22
**Compose:** 1.5.8

Fully native authentication widget for Android. Authentication screens are rendered with Jetpack Compose inside your application. The SDK talks to `https://id.tokenpay.space` over HTTPS.

---

## Features

- `TpidLoginButton` — drop-in Composable button
- `TpidWidget.present(...)` — programmatic presentation
- Full auth flow natively:
  - Email → Password or Email code
  - TOTP 2FA
  - Passkeys through the hosted web sign-in; native passkey UI is not yet available
  - Recovery codes
- OAuth token refresh and device flow alongside native password/email-code sign-in
- Device Flow (RFC 8628) for Android TV / Wear OS / Auto
- Secure token storage via `EncryptedSharedPreferences` (AES256-GCM, MasterKey v2)
- TLS certificate pinning via OkHttp `CertificatePinner` — pins auto-refreshed from `/sdk/tls-pins`
- Telemetry events with PII filtering (client-side scrub before send)
- Anti-phishing badge (visible domain + TLS pin confirmation)
- Screenshot protection via `FLAG_SECURE` on the widget activity
- Session version validation on cold start (auto-logout on password change)
- Full i18n: `ru` / `en` / `zh` (extendable)
- Light / Dark / System themes

---

## Installation

### Local module

```bash
# In your Android project root:
curl -L -O https://www.tokenpay.space/sdk/android/tokenpay-id-android-3.0.0.tar.gz
curl -L -O https://www.tokenpay.space/sdk/android/tokenpay-id-android-3.0.0.tar.gz.sha256
sha256sum -c tokenpay-id-android-3.0.0.tar.gz.sha256
tar -xzf tokenpay-id-android-3.0.0.tar.gz
cp -r tokenpay-id-android-3.0.0/tokenpay-id-sdk ./tokenpay-id-sdk
```

In `settings.gradle.kts`:

```kotlin
include(":tokenpay-id-sdk")
```

In your app's `build.gradle.kts`:

```kotlin
dependencies {
    implementation(project(":tokenpay-id-sdk"))
}
```

The archive contains a complete sample project and the SDK module. Maven/AAR distribution is not part of this source release.

---

## Quick start

```kotlin
// In your Application class or Activity:
import space.tokenpay.id.TpidAuth
import space.tokenpay.id.TpidConfig

TpidAuth.initialize(
    context = applicationContext,
    config = TpidConfig(
        clientId = "tpid_pk_YOUR_PUBLIC_KEY",
        redirectUri = "com.cupol.vpn:/auth/callback",
        scopes = listOf("openid", "profile", "email"),
        theme = TpidConfig.Theme.AUTO,
        language = TpidConfig.Language.SYSTEM,
    )
)
```

### Compose

```kotlin
import space.tokenpay.id.TpidLoginButton

@Composable
fun LoginScreen() {
    TpidLoginButton(
        onResult = { result ->
            when (result) {
                is TpidResult.Success -> {
                    // result.accessToken, result.refreshToken, result.idToken, result.user
                    navigateToHome(result.accessToken)
                }
                is TpidResult.Cancelled -> { /* user closed widget */ }
                is TpidResult.Failure   -> { showError(result.error) }
            }
        }
    )
}
```

### Programmatic

```kotlin
lifecycleScope.launch {
    val result = TpidWidget.present(activity = this@MainActivity)
    // handle result
}
```

### Device Flow (Android TV / Wear OS)

```kotlin
val device = TpidAuth.startDeviceFlow()
// device.userCode  → "ABCD-EFGH"
// device.verificationUriComplete → "https://id.tokenpay.space/device?user_code=ABCD-EFGH"
// Show QR + code on TV screen
val tokens = TpidAuth.pollDeviceFlow(device)   // suspends until approved / expired
```

### Sign-out

```kotlin
TpidAuth.signOut(revokeOnServer = true)
```

---

## Permissions

Add to your `AndroidManifest.xml`:

```xml
<uses-permission android:name="android.permission.INTERNET" />
```

No other permissions required. The widget does **not** request Internet access at runtime if your app already has it.

---

## Security

- PKCE S256 is used for authorization-code flows. Native password/email-code sign-in uses the documented authentication endpoints.
- Tokens stored in `EncryptedSharedPreferences` with hardware-backed `MasterKey` when available.
- `WidgetActivity` has `FLAG_SECURE` by default (disable via `TpidConfig.allowScreenshots = true` for debug builds).
- Certificate pinning activates when `/sdk/tls-pins` provides valid SHA-256 SPKI pins. With no configured pins, operating-system TLS validation remains in force and the UI does not claim a pinned connection.
- On pin mismatch — widget returns `TpidError.PhishingDetected` and clears stored tokens.

See full threat model at <https://tokenpay.space/docs#native-widget-security>.

---

## License

Commercial. © 2026 TOKEN PAY LLC. By integrating this SDK you agree to the Partner Agreement at <https://tokenpay.space/partners>.
