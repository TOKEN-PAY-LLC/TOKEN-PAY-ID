# Changelog

All notable changes to TOKEN PAY ID's public API, widget, and source SDKs are recorded here.

## API 3.0.0 · 2026-09-24

### Added
- Additive `/api/v3` compatibility base and discovery document; v1 routes remain available with their existing OAuth, token, and authentication response shapes.
- `X-API-Version: 3.0.0` response header on v3 calls for client-side version pinning.
- v3 OpenAPI specification at [`openapi-v3.yaml`](openapi-v3.yaml); v2.6.3 auth helpers and device-flow/telemetry endpoints are documented.
- Production health and SDK metadata now report API 2.6.3 instead of the stale 2.4.0 label.

### Compatibility
- Existing `/api/v1` consumers are unchanged. v3 currently dispatches to the same reviewed handlers, so clients can migrate the base path without changing payloads. This release does not claim a breaking contract redesign.

## API 2.6.3 · 2026-05-04

- Remembered-account authentication: quick login with email code within the remembered window, plus policy metadata from account-check.
- Correct 2FA continuation in passwordless quick-login.
- Native SDK release manifest for Android, Swift, and JVM Desktop.

## API 2.4.0 · 2026-09-24

### Added
- Public OAuth branding fields for application name, icon URL, description, and HTTPS website URL.
- API key dashboard fields for application branding; existing `app_name` and `redirect_uris` payloads remain supported.
- OpenAPI coverage for passkey registration and login, QR login, public branding, and API key branding.
- Public widget v1.3.0: responsive desktop two-column sign-in panel with enterprise icon/name/website branding; mobile remains a single-column card.

### Security and reliability
- Passkey registration challenge and verification now require an authenticated account matching the submitted email.
- WebAuthn challenge age, ceremony type, exact first-party origins, RP ID hash, user presence, and supported signature counters are checked.
- WebAuthn QR session responses are marked non-cacheable; the QR page suppresses referrer leakage.
- SDK webhook verification uses constant-time comparison; JS/Python/Go response parsing is bounded and handles non-JSON errors safely.
- Python SDK packaging no longer assumes a README exists inside its package directory; JavaScript SDK now declares its Node.js 18 runtime requirement.

### UI
- Homepage header remains fixed to the viewport and visible during initial load and scrolling.
- Sign-in buttons use the site's rounded style. Passkey is presented as a secondary method below the primary email/QR choices.
- Cookie notice keeps its policy links and legal context in a calmer, more compact layout; storage failures no longer prevent the page from loading it.

---

## Native SDKs · [2.5.0-pre.1] — 2026-04-18

### TpidLoginButton — three official variants
- Dark, light, and icon-only variants with shared size presets and full-width support.
- Canonical TOKEN PAY ID logo assets keep the button presentation consistent across apps.

### Native widget — visual refresh
- Welcome, email, password, 2FA, and passkey screens share a rounded monochrome auth-card style.
- Light and dark themes, runtime RU / EN / ZH strings, and enterprise app-name branding.

### Android, Swift, and JVM Desktop
- Bundled wordmark/icon resources, consistent language behavior, and native Compose / SwiftUI layouts.
- This native prerelease remains separate from the API 2.4.0 release and is not presented as a stable public SDK package here.

---

## [1.1.0] — 2025-04-02

### API
- Push notifications via Server-Sent Events (SSE)
- Notification history and read-state routes
- QR code login flow
- Contact form endpoint

### SDKs
- Webhook signature verification and notification helpers for JavaScript, Python, and Go
- Widget SDK v1.2

### Security
- Security headers and QR session rate limits
- JSON parse errors no longer expose stack traces

---

## [1.0.0] — 2025-03-16

### API
- OAuth 2.0 authorization code flow with PKCE
- OpenID Connect discovery endpoint
- JWT access and refresh tokens
- Email verification and TOTP-based two-factor authentication
- Enterprise API keys, webhooks, activity log, and session management

### SDKs
- JavaScript/Node.js, Python, and Go source clients
