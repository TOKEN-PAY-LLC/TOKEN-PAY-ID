# Changelog

All notable changes to TOKEN PAY ID API and SDKs.

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
