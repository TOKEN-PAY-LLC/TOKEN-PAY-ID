# TOKEN PAY ID

**Unified authentication and identity platform by TOKEN PAY LLC**

[![API Status](https://img.shields.io/badge/API-Live-brightgreen)](https://tokenpay.space/api/v1/health)
[![OpenID](https://img.shields.io/badge/OpenID_Connect-Supported-blue)](https://tokenpay.space/.well-known/openid-configuration)
[![OAuth 2.0](https://img.shields.io/badge/OAuth_2.0-Supported-blue)](https://tokenpay.space/docs)

---

## Overview

TOKEN PAY ID is an open, production-ready authentication platform providing:

- **OAuth 2.0** authorization code flow with PKCE
- **OpenID Connect** discovery endpoint
- **REST API** with JWT and API key authentication
- **2FA** (TOTP) + email verification
- **Enterprise** accounts with user management
- **Webhooks** and activity monitoring

**Base URL:** `https://tokenpay.space`

---

## Quick Start

### 1. Get an API key

Register at [tokenpay.space/register](https://tokenpay.space/register), then generate an API key in your dashboard.

### 2. Authenticate users via OAuth 2.0

```
GET https://tokenpay.space/api/v1/oauth/authorize
  ?client_id=YOUR_PUBLIC_KEY
  &redirect_uri=https://yourapp.com/callback
  &response_type=code
  &scope=profile email
  &state=RANDOM_STATE
```

### 3. Exchange code for token

```bash
curl -X POST https://tokenpay.space/api/v1/oauth/token \
  -H "Content-Type: application/json" \
  -d '{
    "grant_type": "authorization_code",
    "code": "tpid_code_...",
    "client_id": "tpid_pk_...",
    "client_secret": "tpid_sk_...",
    "redirect_uri": "https://yourapp.com/callback"
  }'
```

### 4. Get user info

```bash
curl https://tokenpay.space/api/v1/oauth/userinfo \
  -H "Authorization: Bearer ACCESS_TOKEN"
```

---

## API Reference

### Authentication Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/send-code` | Send email verification code |
| POST | `/api/v1/auth/register` | Register a new user |
| POST | `/api/v1/auth/login` | Log in (returns JWT) |
| POST | `/api/v1/auth/refresh` | Refresh access token |
| POST | `/api/v1/auth/logout` | Revoke session |
| POST | `/api/v1/auth/forgot-password` | Send password reset code |
| POST | `/api/v1/auth/reset-password` | Reset password with code |

### User Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/users/me` | Get current user |
| PUT | `/api/v1/users/me` | Update user profile |
| GET | `/api/v1/users/activity` | Activity log |
| GET | `/api/v1/users/sessions` | Active sessions |
| DELETE | `/api/v1/users/sessions/:id` | Revoke session |
| GET | `/api/v1/users/connected-apps` | Connected applications |

### API Keys

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/keys` | List API keys |
| POST | `/api/v1/keys` | Create API key |
| DELETE | `/api/v1/keys/:id` | Revoke API key |

### OAuth 2.0

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/oauth/authorize` | Authorization endpoint |
| POST | `/api/v1/oauth/approve` | Approve authorization |
| POST | `/api/v1/oauth/token` | Token endpoint |
| GET | `/api/v1/oauth/userinfo` | UserInfo endpoint |
| POST | `/api/v1/oauth/revoke` | Revoke token |
| GET | `/.well-known/openid-configuration` | OpenID Connect discovery |
| GET | `/.well-known/jwks.json` | JWKS endpoint |

### Enterprise

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/enterprise/apply` | Apply for enterprise |
| GET | `/api/v1/enterprise/application` | Check application status |
| GET | `/api/v1/enterprise/users` | List connected users |
| GET | `/api/v1/enterprise/stats` | Usage statistics |
| GET | `/api/v1/enterprise/settings` | Integration settings |
| PUT | `/api/v1/enterprise/settings` | Update settings |

---

## SDK Examples

### JavaScript / Node.js

```javascript
// OAuth 2.0 callback handler
const response = await fetch('https://tokenpay.space/api/v1/oauth/token', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    grant_type: 'authorization_code',
    code: req.query.code,
    client_id: process.env.TPID_PUBLIC_KEY,
    client_secret: process.env.TPID_SECRET_KEY,
    redirect_uri: 'https://yourapp.com/callback'
  })
});
const { access_token, user } = await response.json();
```

### Python

```python
import requests

token_resp = requests.post('https://tokenpay.space/api/v1/oauth/token', json={
    'grant_type': 'authorization_code',
    'code': code,
    'client_id': PUBLIC_KEY,
    'client_secret': SECRET_KEY,
    'redirect_uri': 'https://yourapp.com/callback'
})
access_token = token_resp.json()['access_token']

user_resp = requests.get('https://tokenpay.space/api/v1/oauth/userinfo',
    headers={'Authorization': f'Bearer {access_token}'})
user = user_resp.json()
```

### Go

```go
type TokenResponse struct {
    AccessToken  string `json:"access_token"`
    RefreshToken string `json:"refresh_token"`
}

payload := map[string]string{
    "grant_type":    "authorization_code",
    "code":          code,
    "client_id":     publicKey,
    "client_secret": secretKey,
    "redirect_uri":  redirectURI,
}
body, _ := json.Marshal(payload)
resp, _ := http.Post("https://tokenpay.space/api/v1/oauth/token",
    "application/json", bytes.NewBuffer(body))
```

---

## User Object

```json
{
  "id": "tpid_usr_...",
  "email": "user@example.com",
  "name": "Ivan Ivanov",
  "role": "user",
  "email_verified": true,
  "two_factor_enabled": false,
  "locale": "ru",
  "created_at": "2025-01-01T00:00:00.000Z",
  "last_login": "2025-06-01T12:00:00.000Z"
}
```

---

## Health Check

```bash
curl https://tokenpay.space/api/v1/health
# {"status":"ok","version":"1.0.0"}
```

---

## Links

- **Website:** [tokenpay.space](https://tokenpay.space)
- **Dashboard:** [tokenpay.space/dashboard](https://tokenpay.space/dashboard)
- **API Docs:** [tokenpay.space/docs](https://tokenpay.space/docs)
- **OpenID Discovery:** [tokenpay.space/.well-known/openid-configuration](https://tokenpay.space/.well-known/openid-configuration)

---

## License

Copyright © 2025 TOKEN PAY LLC. All rights reserved.
