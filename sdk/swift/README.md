# TOKEN PAY ID — Swift SDK

**Version:** `3.0.0` · **API compatibility:** existing `/api/v1` auth contracts remain in use

## 3.0.0

- Saved-account screen now has a compact account card, clear next-step guidance, QR access, and fully rounded black-and-white actions.
- Remembered sessions are checked against the selected account and a nonnegative login age. The automatic theme follows the operating system on Apple platforms.
- Removed the dead-end native passkey prompt. Passkeys remain available on the hosted web sign-in; native flows use working password, email-code, QR, and 2FA paths.
- Public `TpidAuth`, `TpidWidget`, and `TpidResult` interfaces remain compatible.

## Previous release notes

> **2.5.0-pre.4 changes**
> - **Sign-up restored** — brand-new emails now open a `RegisterStepView` instead of `PasswordStepView` (which 401'd). Two-phase: name + password, then 6-digit verification code → `POST /auth/register`.
> - `ApiClient.register(email:password:username:emailCode:config:)` returns `TpidSession` directly; handles both camelCase and snake_case token keys from the server.
> - **Endpoint fix** — `requestEmailCode`/`verifyEmailCode` now hit `/api/v1/auth/send-code` and `/api/v1/auth/verify`. The pre.3 Swift SDK was still pointing at `/auth/magic-link/*` which never shipped (same blocker that was fixed in JVM and Android two releases ago).
> - `requestEmailCode` forwards the required `type: "login" | "register"` parameter.
> - **Bundled wordmarks regenerated** — DARK and LIGHT buttons use the same solid glyph at matching aspect 6.649.
> - New Swift widget strings: `register_title`, `register_code_sent`, `field_username`, `placeholder_username`, `placeholder_password_new`, `btn_send_code`, `btn_create_account`, `btn_resend_code`, `error_username_short`, `loading_creating` across en/ru/zh.
> - `TpidVersion.string` → `2.5.0-pre.4`.

> **2.5.0-pre.3 changes**
> - `TpidLoginButton`: border bumped to 2pt × 28% alpha (up from 1.5pt × 18%), wordmark 18/22/26 pt (up from 16/20/24) — second pass on "чтобы лого был немного крупнее".
> - `TpidVersion.string` → `2.5.0-pre.3`; User-Agent / `X-TPID-SDK` header now emits `swift:2.5.0-pre.3`.
> - Internal parity with Android + JVM bug-fix release of the same version (password-reveal toggle, soft-rounded widget card, `/auth/send-code` with `type` field — Swift shipped those earlier).

> **2.5.0-pre.2 changes**
> - Comfortaa variable TTF bundled + registered with CoreText; widget card uses it automatically.
> - Animated fade+slide between widget steps (matches Android and JVM).
> - New `TpidUpdateBanner` driven by `RemoteConfig` fetched from `/api/v1/sdk/config`.
> - `TpidLoginButton`: matched 1.5pt borders on both variants, enlarged wordmark, tinted-white saturn glyph on `iconOnly`, press-scale animation.
> - User-Agent / X-TPID-SDK header now emits `swift:2.5.0-pre.2`.
**Platforms:** iOS 15+, macOS 12+, tvOS 15+, watchOS 8+, visionOS 1+

Fully native authentication widget for Apple platforms. Authentication screens are rendered with SwiftUI inside your application and use HTTPS calls to `id.tokenpay.space`.

---

## Features

- `TpidLoginButton()` — drop-in SwiftUI button
- `TpidWidget.present(...)` — programmatic presentation via `UIKit`/`AppKit`
- Full auth flow natively:
  - Email → Password or Email code
  - TOTP 2FA
  - Passkeys through the hosted web sign-in; native passkey UI is not yet available
  - Recovery codes
- OAuth token refresh and device flow alongside native password/email-code sign-in
- Device Flow (RFC 8628) — primary path for tvOS / watchOS
- Keychain secure storage (biometric-protected on iOS / macOS)
- TLS pinning via `URLSession` delegate — pins refreshed from `/sdk/tls-pins`
- Telemetry with client-side PII scrubbing
- Anti-phishing badge (host + TLS pin confirmation)
- Screenshot protection on iOS via hidden secure field overlay
- Full i18n: `ru` / `en` / `zh`
- Light / Dark / System themes

---

## Installation

### Swift Package Manager (local package)

Add to `Package.swift`:

```swift
.package(path: "./tokenpay-id-swift-3.0.0")
```

Or via Xcode:
1. Download `tokenpay-id-swift-3.0.0.tar.gz` and its `.sha256` file from <https://tokenpay.space/sdk/>
2. Unpack, add `Package.swift` directory to Xcode as local package
3. Add `TokenPayID` library to your target

The 3.0.0 release is distributed as a source archive. Add its extracted package directory as a local Swift package.

---

## Quick start

```swift
import SwiftUI
import TokenPayID

@main
struct MyApp: App {
    init() {
        TpidAuth.shared.initialize(
            config: .init(
                clientId: "tpid_pk_YOUR_PUBLIC_KEY",
                redirectURI: URL(string: "com.cupol.vpn:/auth/callback")!,
                scopes: ["openid", "profile", "email"],
                theme: .auto,
                language: .system
            )
        )
    }
    var body: some Scene { WindowGroup { ContentView() } }
}

struct ContentView: View {
    @State private var status: String = "Not signed in"
    var body: some View {
        VStack(spacing: 20) {
            TpidLoginButton { result in
                switch result {
                case .success(let session):
                    status = "Signed in: \(session.user.email)"
                case .cancelled:
                    status = "Cancelled"
                case .failure(let err):
                    status = "Error: \(err.code) — \(err.localizedDescription)"
                }
            }
            Text(status).font(.footnote)
        }
        .padding()
    }
}
```

### Device Flow (tvOS / watchOS)

```swift
let device = try await TpidAuth.shared.startDeviceFlow()
// Display device.userCode + device.verificationURIComplete on-screen (QR/text)
let result = try await TpidAuth.shared.pollDeviceFlow(device)
```

### Sign out

```swift
TpidAuth.shared.signOut(revokeOnServer: true)
```

### Access token

```swift
let token = try await TpidAuth.shared.getAccessToken()  // refreshes automatically
```

---

## Security

- PKCE S256 is used for authorization-code flows; native password/email-code sign-in uses the documented authentication endpoints.
- Tokens → Keychain (`kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly` + biometric ACL when available)
- TLS pinning via `URLSessionDelegate` when `/sdk/tls-pins` provides valid SHA-256 SPKI pins; otherwise the system TLS trust check applies.
- On pin mismatch: aborts, clears keychain, returns `.phishingDetected`
- No third-party dependencies. Pure Foundation / URLSession / CryptoKit / AuthenticationServices.

Full threat model: <https://tokenpay.space/docs#native-widget-security>

---

## License

Commercial. © 2026 TOKEN PAY LLC. Requires active Partner Agreement.
