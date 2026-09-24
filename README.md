# TOKEN PAY ID

<div align="center">

**Identity and authentication for TOKEN PAY integrations**

[![API](https://img.shields.io/badge/API-3.0.0-111?style=for-the-badge)](https://tokenpay.space/api/v3)
[![OAuth](https://img.shields.io/badge/OAuth-2.0-111?style=for-the-badge)](https://tokenpay.space/.well-known/openid-configuration)
[![OpenAPI](https://img.shields.io/badge/OpenAPI-3.0-111?style=for-the-badge)](openapi.yaml)
[![License](https://img.shields.io/badge/License-Proprietary-111?style=for-the-badge)](LICENSE)

[Website](https://tokenpay.space) · [API reference](https://tokenpay.space/openapi.yaml) · [Dashboard](https://tokenpay.space/dashboard) · [Support](mailto:info@tokenpay.space)

</div>

---

TOKEN PAY ID provides OAuth 2.0 / OpenID Connect, a versioned REST API, an embeddable sign-in widget, and source SDKs for JavaScript, Python, and Go. Existing API integrations remain on the same `/api/v1` routes; API 3.0.0 adds a versioned compatibility surface and request-version headers while preserving the existing authentication and token response contract. API 2.6.3 introduced remembered-account authentication improvements.

## Integration options

| Use case | Recommended entry point | Current version |
| --- | --- | --- |
| Browser sign-in button and modal | [`sdk/web/tpid-widget.js`](sdk/web/tpid-widget.js) | 1.3.0 |
| Server-side OAuth client | JavaScript, Python, or Go source SDK | JS 1.1.1 · Python 1.0.1 · Go module |
| Direct API integration | [`openapi-v3.yaml`](openapi-v3.yaml) | API 3.0.0 |

Only these source SDKs are included in this public repository. Other ecosystem packages are not advertised here as installable releases.

## Quick start: web widget

Create an API key in the [dashboard](https://tokenpay.space/dashboard), then embed the public key in your page. Public keys are intended for browser use; never put a secret key in browser code.

```html
<script src="https://tokenpay.space/sdk/tpid-widget.js"
        data-client-id="tpid_pk_YOUR_PUBLIC_KEY"></script>
<div data-tpid-button="standard"></div>
```

For manual setup and callbacks:

```html
<script src="https://tokenpay.space/sdk/tpid-widget.js"></script>
<script>
  TPID.init({
    clientId: 'tpid_pk_YOUR_PUBLIC_KEY',
    theme: 'auto',
    lang: 'en',
    onSuccess: ({ user, accessToken }) => {
      // Send the token to your backend over HTTPS for server-side validation.
      console.log('Signed in:', user.id);
    }
  });
</script>
```

The widget fetches public application branding for the supplied `clientId`. The desktop dialog uses a two-column layout; narrow screens use a single-column layout. Branding values are treated as text, and icon and website links must use HTTPS.

## API compatibility

New integrations can use `https://tokenpay.space/api/v3` and [`openapi-v3.yaml`](openapi-v3.yaml). Existing clients can continue using `https://tokenpay.space/api/v1`; request paths, OAuth behavior, and token response fields remain supported. The v1 contract is documented in [`openapi.yaml`](openapi.yaml). The branding update endpoint accepts the existing `app_name` and `redirect_uris` fields plus optional `app_icon_url`, `app_description`, and `client_uri` fields. Passkey registration now requires the current user's bearer token; this closes an account-ownership gap in the previous implementation.

Use the [API v3 specification](openapi-v3.yaml) for new clients or the [API v1 specification](openapi.yaml) for existing integrations. For OAuth authorization-code integrations:

1. Generate a cryptographically random `state` value and retain it in the application session.
2. Use authorization code with PKCE (`S256`) and an exact registered HTTPS redirect URI.
3. Exchange the code on your backend. Keep the client secret and refresh token server-side.
4. Validate `state`, token issuer, audience, and expiry before creating an application session.

## Source SDKs

### JavaScript / Node.js

Requires Node.js 18 or later.

```js
const { TokenPayIDClient } = require('./sdk/javascript');

const client = new TokenPayIDClient({
  clientId: process.env.TPID_PUBLIC_KEY,
  clientSecret: process.env.TPID_SECRET_KEY,
  redirectUri: 'https://yourapp.example/callback'
});
```

### Python

```python
import os
from tokenpay_id import TokenPayIDClient

client = TokenPayIDClient(
    client_id=os.environ['TPID_PUBLIC_KEY'],
    client_secret=os.environ['TPID_SECRET_KEY'],
    redirect_uri='https://yourapp.example/callback',
)
```

Install from a checkout with `pip install ./sdk/python`.

### Go

```go
import tpid "github.com/TOKEN-PAY-LLC/TOKEN-PAY-ID/sdk/go"

client := tpid.NewClient(tpid.Config{
    ClientID:     os.Getenv("TPID_PUBLIC_KEY"),
    ClientSecret: os.Getenv("TPID_SECRET_KEY"),
    RedirectURI:  "https://yourapp.example/callback",
})
```

The SDKs implement OAuth and API calls. They do not replace server-side token validation or application session management.

## Security notes

- Keep `tpid_sk_...`, OAuth client secrets, and refresh tokens on your backend.
- Register only exact HTTPS redirect URIs. Avoid wildcard redirect patterns.
- Verify webhook signatures against the unmodified raw request body and enforce a short timestamp tolerance.
- Use `state` and PKCE in OAuth flows; do not treat a browser callback or client-side token as proof without server-side validation.
- Report security issues privately to [info@tokenpay.space](mailto:info@tokenpay.space). Do not include live credentials in public issues.

## Versioning

- **API:** 3.0.0
- **Web widget:** 1.3.0
- **JavaScript SDK:** 1.1.1
- **Python SDK:** 1.0.1

See [CHANGELOG.md](CHANGELOG.md) for release notes and [LICENSE](LICENSE) for repository terms.
