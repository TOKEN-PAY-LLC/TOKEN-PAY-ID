import hashlib
import base64
import os
import urllib.parse
from typing import Optional, Dict, Any

try:
    import urllib.request
    import json as _json
except ImportError:
    pass

BASE_URL = "https://tokenpay.space"


class TokenPayIDError(Exception):
    def __init__(self, code: str, message: str, status: int = 0):
        super().__init__(message)
        self.code = code
        self.status = status


class TokenPayIDClient:
    """
    Official Python SDK for TOKEN PAY ID.

    Usage::

        from tokenpay_id import TokenPayIDClient

        client = TokenPayIDClient(
            client_id="tpid_pk_...",
            client_secret="tpid_sk_...",
            redirect_uri="https://yourapp.com/callback"
        )

        # Build authorization URL
        url, state, verifier = client.get_authorization_url(use_pkce=True)

        # After redirect, exchange code
        tokens = client.exchange_code(code, code_verifier=verifier)
        user = tokens["user"]
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        base_url: str = BASE_URL,
    ):
        if not client_id:
            raise ValueError("client_id is required")
        if not client_secret:
            raise ValueError("client_secret is required")
        if not redirect_uri:
            raise ValueError("redirect_uri is required")

        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.base_url = base_url.rstrip("/")

    # ── PKCE ─────────────────────────────────────────────────────────────────

    @staticmethod
    def generate_pkce() -> Dict[str, str]:
        """Generate a PKCE verifier and S256 challenge pair."""
        verifier = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode()
        digest = hashlib.sha256(verifier.encode()).digest()
        challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
        return {"verifier": verifier, "challenge": challenge}

    # ── AUTHORIZATION URL ─────────────────────────────────────────────────────

    def get_authorization_url(
        self,
        scope: str = "profile email",
        state: Optional[str] = None,
        use_pkce: bool = True,
    ):
        """
        Build the authorization URL to redirect the user to.

        Returns:
            (url, state, pkce_verifier) — verifier is None if use_pkce=False
        """
        if state is None:
            state = base64.urlsafe_b64encode(os.urandom(16)).decode().rstrip("=")

        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": scope,
            "state": state,
        }

        verifier = None
        if use_pkce:
            pkce = self.generate_pkce()
            verifier = pkce["verifier"]
            params["code_challenge"] = pkce["challenge"]
            params["code_challenge_method"] = "S256"

        url = f"{self.base_url}/api/v1/oauth/authorize?{urllib.parse.urlencode(params)}"
        return url, state, verifier

    # ── TOKEN EXCHANGE ────────────────────────────────────────────────────────

    def exchange_code(self, code: str, code_verifier: Optional[str] = None) -> Dict[str, Any]:
        """Exchange authorization code for tokens."""
        body: Dict[str, Any] = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
        }
        if code_verifier:
            body["code_verifier"] = code_verifier
        return self._post("/api/v1/oauth/token", body)

    def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh an access token."""
        return self._post("/api/v1/oauth/token", {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        })

    # ── USER ──────────────────────────────────────────────────────────────────

    def get_user(self, access_token: str) -> Dict[str, Any]:
        """Get user info via OIDC userinfo endpoint."""
        return self._get("/api/v1/oauth/userinfo", access_token)

    def get_me(self, access_token: str) -> Dict[str, Any]:
        """Get full user profile (JWT token from direct login)."""
        return self._get("/api/v1/users/me", access_token)

    # ── TOKEN REVOCATION ──────────────────────────────────────────────────────

    def revoke_token(self, token: str) -> Dict[str, Any]:
        """Revoke an access or refresh token."""
        return self._post("/api/v1/oauth/revoke", {
            "token": token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        })

    # ── NOTIFICATIONS ─────────────────────────────────────────────────────────

    def get_notifications(self, access_token: str) -> Dict[str, Any]:
        """Get notification history (last 50)."""
        return self._get("/api/v1/notifications", access_token)

    def mark_notification_read(self, access_token: str, notification_id: str) -> Dict[str, Any]:
        """Mark a notification as read."""
        return self._put(f"/api/v1/notifications/{notification_id}/read", access_token)

    def mark_all_notifications_read(self, access_token: str) -> Dict[str, Any]:
        """Mark all notifications as read."""
        return self._put("/api/v1/notifications/read-all", access_token)

    # ── WEBHOOK VERIFICATION ──────────────────────────────────────────────────

    @staticmethod
    def verify_webhook_signature(
        payload: str,
        signature: str,
        secret: str,
        tolerance: int = 300,
    ) -> bool:
        """
        Verify a webhook signature (Stripe-style t=timestamp,v1=hmac).

        Args:
            payload: Raw request body string
            signature: X-TPID-Signature header value
            secret: Your webhook secret from dashboard
            tolerance: Max age in seconds (default 5 min)

        Returns:
            True if signature is valid
        """
        import hmac as _hmac
        import time

        parts = {}
        for part in signature.split(","):
            k, _, v = part.partition("=")
            parts[k] = v

        ts_str = parts.get("t", "")
        v1 = parts.get("v1", "")
        if not ts_str or not v1:
            return False

        try:
            ts = int(ts_str)
        except ValueError:
            return False

        if abs(time.time() - ts) > tolerance:
            return False

        expected = _hmac.new(
            secret.encode(),
            f"{ts}.{payload}".encode(),
            hashlib.sha256,
        ).hexdigest()

        return _hmac.compare_digest(expected, v1)

    # ── INTERNAL ──────────────────────────────────────────────────────────────

    @staticmethod
    def _read_response(resp) -> Dict[str, Any]:
        raw = resp.read(1_048_577)
        if len(raw) > 1_048_576:
            raise TokenPayIDError("response_too_large", "TOKEN PAY ID response exceeded 1 MiB", getattr(resp, "status", 0))
        try:
            return _json.loads(raw or b"{}")
        except (ValueError, UnicodeDecodeError):
            raise TokenPayIDError("invalid_response", "TOKEN PAY ID returned an invalid response", getattr(resp, "status", 0))

    @staticmethod
    def _http_error(exc) -> TokenPayIDError:
        try:
            body = _json.loads(exc.read(1_048_576) or b"{}")
        except (ValueError, UnicodeDecodeError):
            body = {}
        error = body.get("error", {}) if isinstance(body, dict) else {}
        if isinstance(error, str):
            code = error
            message = body.get("error_description") or body.get("message") or str(exc)
            status = exc.code
        elif isinstance(error, dict):
            code = error.get("code", "request_failed")
            message = error.get("message", str(exc))
            status = error.get("status", exc.code)
        else:
            code, message, status = "request_failed", str(exc), exc.code
        return TokenPayIDError(code, message, status)

    def _post(self, path: str, body: dict) -> dict:
        import urllib.request, json
        data = json.dumps(body).encode()
        req = urllib.request.Request(
            self.base_url + path,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return self._read_response(resp)
        except urllib.error.HTTPError as e:
            raise self._http_error(e)

    def _get(self, path: str, access_token: str) -> dict:
        import urllib.request, json
        req = urllib.request.Request(
            self.base_url + path,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return self._read_response(resp)
        except urllib.error.HTTPError as e:
            raise self._http_error(e)

    def _put(self, path: str, access_token: str) -> dict:
        import urllib.request, json
        req = urllib.request.Request(
            self.base_url + path,
            method="PUT",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return self._read_response(resp)
        except urllib.error.HTTPError as e:
            raise self._http_error(e)
