# TOKEN PAY ID — JVM Desktop SDK

**Version**: `3.0.1` · **Status**: Source release · **API compatibility**: existing `/api/v1` auth contracts remain in use

## 3.0.1

- Removed the deterministic file-encryption fallback for refresh tokens. Without DPAPI, Keychain, or libsecret, sessions now remain in process memory only.
- Wider, top-aligned Windows dialog removes the empty band around saved-account sign-in. Rounded actions, a compact account row, QR access, and clear next-step guidance match the web sign-in.
- Automatic theme now reads the Windows app-theme setting. Active enterprise names from `/sdk/config` appear below the TOKEN PAY ID wordmark.
- The widget refuses a cached session belonging to a different account. It no longer routes users to a nonfunctional native passkey screen.
- `TpidAuth`, `TpidConfig`, `TpidResult`, and `TpidLoginButton` remain source compatible.

## Previous release notes

> **What changed in 2.5.0-pre.4**
> - **Sign-up restored** — pre.3 routed `!info.exists` straight to the password step, which always 401'd. The widget now shows a dedicated `RegisterStep` that collects username + password, sends a verification code via `/auth/send-code` with `type = "register"`, and completes sign-up via `POST /auth/register` (tokens returned directly — no OAuth code exchange). Creating an account from the widget now just works.
> - `ApiClient.register(email, password, username, emailCode, config)` added — parses both `accessToken` (what `/auth/register` returns) and `access_token` (the OAuth RFC spelling) so future backend changes stay backwards compatible.
> - `TpidField(enabled:)` — the sign-up fields freeze at 55 % alpha after the verification code has been dispatched, so users can't silently edit name or password mid-flow.
> - **Bundled wordmarks regenerated** — DARK and LIGHT buttons now use the same glyph shape (solid fill, aspect 6.649) so the two variants look visually symmetric at the same height. Old pre.3 shipped an outlined/hollow white variant that made the DARK button ~27 % wider than LIGHT.
> - Strings: new `register_title`, `register_code_sent`, `field_username`, `placeholder_username`, `placeholder_password_new`, `btn_send_code`, `btn_create_account`, `btn_resend_code`, `error_username_short`, `loading_creating` across en/ru/zh.
> - User-Agent / `X-TPID-SDK` header now emits `jvm-desktop/2.5.0-pre.4`.

> **What changed in 2.5.0-pre.3 (bug-fix release — CUPOL VPN report)**
> - **blocker** — `POST /api/v1/auth/authorize` → `POST /api/v1/auth/login`. The old path returned `404 Endpoint not found` for every password sign-in (verified against `id.tokenpay.space`).
> - **blocker** — `/auth/send-code` now sends the required `type: "login" | "register"` field. Widget dialog forwards the correct value based on `accountCheck.exists`.
> - **blocker** — `RemoteConfig.compareSemver` no longer crashes on clean semver (`"2.5.0"`). Was previously throwing `IndexOutOfBoundsException` on every recompose.
> - **UX** — Widget window shrinks to `440×600 dp` and the outer gradient / inner double-card are collapsed into a single soft-rounded surface with a 1dp border and 24dp shadow. No more dead frame around short steps.
> - **build-break** — `TpidTypography` moved from the Android `Font(resource = …)` signature to the Skiko `Font(identity, data, …)` path with `useResource`.
> - **build-break** — `build.gradle.kts` adds `kotlin("plugin.serialization")` + `org.jetbrains.kotlin.plugin.compose` and bumps the toolchain to JDK 21.
> - **UX** — password-reveal (eye) toggle built into `TpidField`; state survives via `rememberSaveable`.
> - **UX** — `TpidLoginButton`: border bumped to 2dp × 28% alpha (up from 1.5dp × 18%), wordmark 18/22/26 dp (up from 16/20/24), pill heights 40/48/56 dp.
> - User-Agent / X-TPID-SDK header now emits `jvm-desktop/2.5.0-pre.3`.

> **What changed in 2.5.0-pre.2**
> - Crypt32 DPAPI wrapper rewritten — fixes the JNA "Exception reading field 'cbData'" crash on Windows 11 + JDK 17.
> - Widget window is now **undecorated** with a painted brand top-bar (matches the web widget).
> - **Comfortaa** is bundled as a variable TTF resource and wired into MaterialTheme.
> - Buttons gained animated hover/press states, matching borders and shadows across DARK / LIGHT / ICON_ONLY.
> - New `RemoteConfig` class: theme tokens, string overrides and feature flags now flow from `/api/v1/sdk/config` at widget launch, so most future UI tweaks no longer need you to rebuild.
> - Older SDKs show an "update available" hint when the server's `recommended_sdk_version` is newer.


Single Kotlin package for desktop JVM apps on **Windows 10/11, Linux, and macOS 12+**.
Built on [JetBrains Compose for Desktop](https://www.jetbrains.com/lp/compose-desktop/) — the
same programming model as Jetpack Compose on Android, so 90 %+ of the widget UI code is
shared between the Android and JVM Desktop SDKs.

## What's inside

- **Public API** (`space.tokenpay.id.jvm`): `TpidAuth`, `TpidConfig`, `TpidResult`, `TpidError`, `TpidLoginButton`, `TpidSession`, `TpidUser`, `TpidDeviceFlowSession`.
- **HTTP client** — OkHttp 4.12 with `CertificatePinner` for TLS pinning.
- **Secure storage** — best-available per-OS:
  - **Windows** → DPAPI (via JNA `Crypt32.dll`)
  - **macOS** → Keychain (via `security` CLI)
  - **Linux** → libsecret (via `secret-tool` CLI)
  - **Fallback** — process memory only. Without a system credential store, the user signs in again after restarting the app.
- **Native Compose screens** — saved account, email, password, email code, 2FA, QR, recovery, loading, success, and fatal error. Native passkey sign-in is not offered until implemented.
- Native password/email-code sign-in, OAuth token refresh, and device flow. No embedded browser or WebView.
- **Device Flow (RFC 8628)** — for Swing-less / JavaFX-less headless apps, or when native window isn't possible.

## Embedding

### Standalone Compose Desktop app

```kotlin
import androidx.compose.ui.window.application
import androidx.compose.ui.window.Window
import space.tokenpay.id.jvm.*

fun main() = application {
    TpidAuth.initialize(TpidConfig(
        clientId = "tpid_pk_your_key",
        redirectUri = "cupol-vpn://auth/callback"
    ))
    Window(onCloseRequest = ::exitApplication, title = "My App") {
        TpidLoginButton { result ->
            when (result) {
                is TpidResult.Success -> println("Signed in: ${result.user.email}")
                is TpidResult.Failure -> println("Error: ${result.error.code}")
                TpidResult.Cancelled -> {}
            }
        }
    }
}
```

### Embed in Swing

```kotlin
import androidx.compose.ui.awt.ComposePanel
import javax.swing.JFrame

val panel = ComposePanel()
panel.setContent { TpidLoginButton { /* ... */ } }

val frame = JFrame("My Swing App")
frame.add(panel)
frame.setSize(480, 640)
frame.isVisible = true
```

### Embed in JavaFX

```kotlin
import javafx.embed.swing.SwingNode
import javax.swing.SwingUtilities
import androidx.compose.ui.awt.ComposePanel

val node = SwingNode()
SwingUtilities.invokeLater {
    val panel = ComposePanel()
    panel.setContent { TpidLoginButton { /* ... */ } }
    node.content = panel
}
// add `node` to any JavaFX container
```

## Building & running

```bash
gradle :example-app:run                 # run the example Compose Desktop app
gradle :example-app:packageDistributionForCurrentOS   # MSI / DMG / DEB installer
gradle :tokenpay-id-jvm:test           # run SDK tests
```

## Security notes

- On **Windows** without DPAPI or **Linux** without `secret-tool`, sessions remain in process memory; refresh tokens are not written to disk.
- The SDK **does not** store the user's password — only `access_token` / `refresh_token` returned by the OAuth 2.0 token endpoint.
- TLS pin mismatch aborts the request and returns `TpidError.PhishingDetected`.

## Distribution & support

Source archives for version 3.0.1 are listed at <https://tokenpay.space/sdk/>. No Maven Central artifact is advertised for this release.

- Partner support: `info@tokenpay.space`
- Security: `security@tokenpay.space`
- Status: https://status.tokenpay.space
