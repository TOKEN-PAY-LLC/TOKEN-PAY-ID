# TOKEN PAY ID Web Widget

**Version:** 1.3.0 · **API:** 2.4.0

The widget source in this directory is the same file served at `https://tokenpay.space/sdk/tpid-widget.js`.

## Embed

```html
<script src="https://tokenpay.space/sdk/tpid-widget.js"
        data-client-id="tpid_pk_YOUR_PUBLIC_KEY"></script>
<div data-tpid-button="standard"></div>
```

The public API key lets the widget load the app's public name, HTTPS icon, description, and website from `/api/v1/oauth/branding`. Configure these values in your TOKEN PAY ID dashboard.

For an explicit callback:

```html
<script src="https://tokenpay.space/sdk/tpid-widget.js"></script>
<script>
  TPID.init({
    clientId: 'tpid_pk_YOUR_PUBLIC_KEY',
    theme: 'auto',
    lang: 'en',
    onSuccess: ({ user, accessToken, refreshToken }) => {
      // Send tokens to your HTTPS backend and establish an application session there.
    }
  });
</script>
```

The dialog uses a horizontal brand-and-form layout on desktop and a compact single-column card on mobile. The widget validates branding links as HTTPS and writes remote metadata as text.

Never include an OAuth client secret in browser code. Treat browser tokens as untrusted input on your backend: validate the token and establish your own application session.

See the root [README](../../README.md), [API specification](../../openapi.yaml), and [changelog](../../CHANGELOG.md).
