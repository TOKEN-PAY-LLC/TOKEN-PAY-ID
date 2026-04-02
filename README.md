# TOKEN PAY ID

<div align="center">

<img src="https://tokenpay.space/tokenpay-icon.png" width="80" alt="TOKEN PAY LLC"/>

**Unified Identity & Authentication Platform**

[![API](https://img.shields.io/badge/API-v1.0-black?style=flat-square)](https://tokenpay.space/api/v1/health)
[![OpenID](https://img.shields.io/badge/OpenID_Connect-✓-black?style=flat-square)](https://tokenpay.space/.well-known/openid-configuration)
[![OAuth 2.0](https://img.shields.io/badge/OAuth_2.0-✓-black?style=flat-square)](https://tokenpay.space/docs)
[![License](https://img.shields.io/badge/License-Proprietary-black?style=flat-square)](LICENSE)

**Base URL:** `https://tokenpay.space`

[Documentation](https://tokenpay.space/docs) · [Dashboard](https://tokenpay.space/dashboard) · [Contact](mailto:info@tokenpay.space)

</div>

---

## What is TOKEN PAY ID?

TOKEN PAY ID is the unified digital identity platform by TOKEN PAY LLC. It provides enterprise-grade authentication infrastructure so your application can securely verify and identify users without building auth from scratch.

- **OAuth 2.0 + PKCE** — Secure authorization code flow
- **OpenID Connect** — Standard identity layer on top of OAuth 2.0
- **REST API** — Full programmatic access with JWT and API key auth
- **2FA / TOTP** — Built-in two-factor authentication
- **Enterprise SSO** — Single sign-on for your organization
- **Webhooks** — Real-time event notifications
- **Push Notifications** — SSE-based real-time alerts
- **SDKs** — JavaScript, Python, Go — ready to use

---

## Quick Start

### 1. Register and get your API keys

1. Go to [tokenpay.space/register](https://tokenpay.space/register)
2. Open your [Dashboard](https://tokenpay.space/dashboard) → API Keys
3. Create a new key pair — you'll get a `public_key` and `secret_key`

### 2. Add the login button (5 minutes)

```html
<script src="https://tokenpay.space/sdk/tpid-widget.js"></script>
<div id="tpid-login"></div>
<script>
  TokenPayID.mount('#tpid-login', {
    clientId: 'tpid_pk_YOUR_PUBLIC_KEY',
    redirectUri: 'https://yourapp.com/callback',
    onSuccess: (user) => console.log('Logged in:', user)
  });
</script>
```

### 3. Handle the OAuth callback

```javascript
// GET https://yourapp.com/callback?code=tpid_code_...
const { access_token, user } = await tokenPayID.exchangeCode(req.query.code);
// user = { id, email, name, role, ... }
```

---

## Installation

### JavaScript / Node.js

```bash
npm install @tokenpay/id
```

```javascript
import { TokenPayIDClient } from '@tokenpay/id';

const client = new TokenPayIDClient({
  clientId: process.env.TPID_PUBLIC_KEY,
  clientSecret: process.env.TPID_SECRET_KEY,
  redirectUri: 'https://yourapp.com/callback'
});
```

### Python

```bash
pip install tokenpay-id
```

```python
from tokenpay_id import TokenPayIDClient

client = TokenPayIDClient(
    client_id=os.environ['TPID_PUBLIC_KEY'],
    client_secret=os.environ['TPID_SECRET_KEY'],
    redirect_uri='https://yourapp.com/callback'
)
```

### Go

```bash
go get github.com/TOKEN-PAY-LLC/TOKEN-PAY-ID/sdk/go
```

```go
import tpid "github.com/TOKEN-PAY-LLC/TOKEN-PAY-ID/sdk/go"

client := tpid.NewClient(tpid.Config{
    ClientID:     os.Getenv("TPID_PUBLIC_KEY"),
    ClientSecret: os.Getenv("TPID_SECRET_KEY"),
    RedirectURI:  "https://yourapp.com/callback",
})
```

---

## OAuth 2.0 Flow

```
Your App          TOKEN PAY ID         User
   │                   │                │
   │── 1. Redirect ──►│                │
   │      /authorize   │                │
   │                   │── 2. Login ──►│
   │                   │◄── 3. Auth ───│
   │◄── 4. Code ───────│               │
   │── 5. Exchange ──►│               │
   │◄── 6. Token ──────│               │
   │── 7. UserInfo ──►│               │
   │◄── 8. User Data ──│               │
```

### Step 1 — Redirect user to authorization

```
GET https://tokenpay.space/api/v1/oauth/authorize
  ?client_id=tpid_pk_...
  &redirect_uri=https://yourapp.com/callback
  &response_type=code
  &scope=profile email
  &state=RANDOM_CSRF_TOKEN
  &code_challenge=BASE64URL(SHA256(verifier))   ← PKCE (recommended)
  &code_challenge_method=S256
```

### Step 2 — Exchange code for tokens

```bash
POST https://tokenpay.space/api/v1/oauth/token
Content-Type: application/json

{
  "grant_type": "authorization_code",
  "code": "tpid_code_...",
  "client_id": "tpid_pk_...",
  "client_secret": "tpid_sk_...",
  "redirect_uri": "https://yourapp.com/callback",
  "code_verifier": "YOUR_PKCE_VERIFIER"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOi...",
  "refresh_token": "tpid_rt_...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "user": {
    "id": "tpid_usr_abc123",
    "email": "user@example.com",
    "name": "Ivan Ivanov",
    "role": "user",
    "email_verified": true
  }
}
```

### Step 3 — Get user info

```bash
GET https://tokenpay.space/api/v1/oauth/userinfo
Authorization: Bearer ACCESS_TOKEN
```

---

## API Reference

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/auth/send-code` | Send email verification code |
| `POST` | `/api/v1/auth/register` | Register new user |
| `POST` | `/api/v1/auth/login` | Login (returns JWT + refresh token) |
| `POST` | `/api/v1/auth/refresh` | Refresh access token |
| `POST` | `/api/v1/auth/logout` | Revoke current session |
| `POST` | `/api/v1/auth/forgot-password` | Send password reset code |
| `POST` | `/api/v1/auth/reset-password` | Reset password with code |

### User

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/users/me` | Get authenticated user |
| `PUT` | `/api/v1/users/me` | Update profile (name, locale, theme) |
| `GET` | `/api/v1/users/activity` | Activity log |
| `GET` | `/api/v1/users/sessions` | Active sessions / devices |
| `DELETE` | `/api/v1/users/sessions/:id` | Revoke session |
| `GET` | `/api/v1/users/connected-apps` | Connected applications |
| `DELETE` | `/api/v1/users/connected-apps/:id` | Revoke app access |

### API Keys

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/keys` | List API keys |
| `POST` | `/api/v1/keys` | Create key pair |
| `DELETE` | `/api/v1/keys/:id` | Revoke key |

### OAuth 2.0 / OpenID Connect

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/oauth/authorize` | Authorization endpoint |
| `POST` | `/api/v1/oauth/approve` | Approve authorization (after user login) |
| `POST` | `/api/v1/oauth/token` | Token endpoint |
| `GET` | `/api/v1/oauth/userinfo` | UserInfo endpoint |
| `POST` | `/api/v1/oauth/revoke` | Revoke token |
| `GET` | `/.well-known/openid-configuration` | OpenID Connect discovery |
| `GET` | `/.well-known/jwks.json` | JSON Web Key Set |

### Notifications

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/notifications` | Get notification history (last 50) |
| `PUT` | `/api/v1/notifications/:id/read` | Mark notification as read |
| `PUT` | `/api/v1/notifications/read-all` | Mark all as read |
| `GET` | `/api/v1/notifications/stream?token=JWT` | SSE real-time stream |

### Enterprise

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/enterprise/apply` | Apply for enterprise account |
| `GET` | `/api/v1/enterprise/application` | Check application status |
| `GET` | `/api/v1/enterprise/users` | List users who authorized your app |
| `GET` | `/api/v1/enterprise/stats` | Usage statistics |
| `GET` | `/api/v1/enterprise/settings` | Integration settings |
| `PUT` | `/api/v1/enterprise/settings` | Update callback URL / settings |

### System

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/health` | Health check |
| `POST` | `/api/v1/contact` | Contact form |

---

## User Object

```json
{
  "id": "tpid_usr_abc123def456",
  "email": "user@example.com",
  "name": "Ivan Ivanov",
  "role": "user",
  "email_verified": true,
  "two_factor_enabled": false,
  "locale": "ru",
  "theme": "dark",
  "created_at": "2025-01-15T10:30:00.000Z",
  "last_login": "2025-06-01T08:45:00.000Z"
}
```

**Role values:** `user` | `enterprise` | `admin`

---

## Scopes

| Scope | Description |
|-------|-------------|
| `profile` | Name, ID, role |
| `email` | Email address |
| `openid` | Standard OIDC scope |

---

## Error Format

All errors follow the same structure:

```json
{
  "error": {
    "code": "invalid_token",
    "message": "Token expired or invalid",
    "status": 401
  }
}
```

| Code | Status | Description |
|------|--------|-------------|
| `unauthorized` | 401 | Missing or invalid token |
| `invalid_token` | 401 | Expired or malformed JWT |
| `invalid_key` | 401 | Invalid API key |
| `forbidden` | 403 | Insufficient permissions |
| `not_found` | 404 | Resource not found |
| `validation_error` | 422 | Invalid request body |
| `rate_limit` | 429 | Too many requests |
| `server_error` | 500 | Internal server error |

---

## Authentication Methods

TOKEN PAY ID supports two authentication methods for API requests:

### JWT Bearer Token
```
Authorization: Bearer eyJhbGciOiJIUzI1NiJ9...
```
Obtained from login or OAuth token exchange. Expires in 1 hour.

### API Key
```
Authorization: Bearer tpid_sk_...
```
Long-lived key from your dashboard. Use for server-to-server.

---

## Rate Limits

| Endpoint | Limit |
|----------|-------|
| `/auth/send-code` | 1 per 60 seconds per email |
| `/auth/login` | 10 per minute per IP |
| `/auth/register` | 5 per hour per IP |
| All other endpoints | 200 per minute per key |

---

## Webhooks

Enterprise accounts can receive real-time event notifications.

**Events:**
- `user.oauth_connect` — User authorized via your app
- `user.oauth_cancel` — User closed the consent window
- `user.oauth_deny` — User denied authorization
- `user.unlink` — User disconnected from your app
- `key.created` — New API key created
- `key.revoked` — API key revoked

**Payload:**
```json
{
  "event": "user.oauth_connect",
  "timestamp": "2025-06-01T12:00:00.000Z",
  "data": {
    "user_id": "tpid_usr_abc123",
    "email": "user@example.com",
    "name": "Ivan Ivanov"
  }
}
```

---

## OpenID Connect

TOKEN PAY ID is fully OpenID Connect compliant.

**Discovery URL:** `https://tokenpay.space/.well-known/openid-configuration`

```json
{
  "issuer": "https://tokenpay.space",
  "authorization_endpoint": "https://tokenpay.space/api/v1/oauth/authorize",
  "token_endpoint": "https://tokenpay.space/api/v1/oauth/token",
  "userinfo_endpoint": "https://tokenpay.space/api/v1/oauth/userinfo",
  "jwks_uri": "https://tokenpay.space/.well-known/jwks.json",
  "response_types_supported": ["code"],
  "grant_types_supported": ["authorization_code", "refresh_token"],
  "code_challenge_methods_supported": ["S256", "plain"],
  "scopes_supported": ["openid", "profile", "email"]
}
```

---

## Security

- All API traffic over **HTTPS/TLS 1.3**
- JWT signed with **RS256** (asymmetric, public key verifiable)
- PKCE support for **public clients** (mobile, SPA)
- **Refresh token rotation** on every refresh
- Rate limiting and IP-based abuse prevention
- Email verification required for all accounts

---

## Contributors

- **Ivan Chernykh** — Lead Developer, Architecture & Implementation

---

## Support

- **Documentation:** [tokenpay.space/docs](https://tokenpay.space/docs)
- **Email:** [info@tokenpay.space](mailto:info@tokenpay.space)
- **Issues:** [GitHub Issues](https://github.com/TOKEN-PAY-LLC/TOKEN-PAY-ID/issues)

---

<div align="center">

© 2025 TOKEN PAY LLC — All Rights Reserved

</div>
