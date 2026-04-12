# Changelog

All notable changes to TOKEN PAY ID API and SDKs.

## [1.1.0] — 2025-04-02

### API
- Push notifications via Server-Sent Events (SSE)
- `GET /api/v1/notifications` — notification history
- `PUT /api/v1/notifications/:id/read` — mark as read
- `PUT /api/v1/notifications/read-all` — mark all as read
- `GET /api/v1/notifications/stream?token=JWT` — real-time SSE stream
- Webhook events expanded: `user.oauth_connect`, `user.oauth_cancel`, `user.oauth_deny`, `user.unlink`, `key.created`, `key.revoked`
- Webhook signature verification (HMAC-SHA256, Stripe-style `t=timestamp,v1=hash`)
- QR code login flow (`/api/v1/auth/qr/*`)
- Contact form endpoint (`POST /api/v1/contact`)

### SDKs
- `verifyWebhookSignature()` — all SDKs (JS, Python, Go)
- `getNotifications()` — all SDKs
- Widget SDK v1.2: three button variants, auto PKCE, popup OAuth

### Security
- Security headers: HSTS, CSP, Referrer-Policy, Permissions-Policy
- Nginx: X-Frame-Options DENY, server_tokens off, no-store for HTML
- JSON parse errors no longer leak stack traces
- QR login rate-limited with session cap

### Examples
- Webhook handler examples (Node.js, Python, Go)
- SSE notification listener example (Node.js)

---

## [1.0.0] — 2025-03-16

### API
- OAuth 2.0 authorization code flow with PKCE
- OpenID Connect discovery endpoint
- JWT access tokens (1h) + refresh tokens (30d)
- Email verification for all accounts
- TOTP-based 2FA
- Enterprise accounts with API key management
- Temporary API keys with `expires_in_days`
- API key expiry enforcement in auth middleware
- Activity log and session management
- Webhook support for enterprise accounts

### SDKs
- JavaScript/Node.js SDK (`@tokenpay/id`)
- Python SDK (`tokenpay-id`)
- Go SDK (`github.com/TOKEN-PAY-LLC/TOKEN-PAY-ID/sdk/go`)

### Security
- Enterprise-only API key creation (enforced on backend)
- Expired key detection returns `key_expired` error code
- All keys shown once — secret not stored in plain text in API responses
