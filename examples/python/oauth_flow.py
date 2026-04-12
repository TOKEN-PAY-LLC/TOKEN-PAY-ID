"""
TOKEN PAY ID — Python OAuth 2.0 + PKCE Example
Framework: Flask

Install: pip install flask tokenpay-id
Run:     python oauth_flow.py
"""

import os
import secrets
from flask import Flask, redirect, request, jsonify, session

from tokenpay_id import TokenPayIDClient, TokenPayIDError

app = Flask(__name__)
app.secret_key = os.urandom(24)

client = TokenPayIDClient(
    client_id=os.environ["TPID_PUBLIC_KEY"],       # tpid_pk_...
    client_secret=os.environ["TPID_SECRET_KEY"],   # tpid_sk_...
    redirect_uri="http://localhost:5000/callback",
)


# ── 1. Start login ─────────────────────────────────────────────────────────────
@app.route("/login")
def login():
    url, state, verifier = client.get_authorization_url(
        scope="openid profile email",
        use_pkce=True,
    )
    session["oauth_state"] = state
    session["pkce_verifier"] = verifier
    return redirect(url)


# ── 2. Handle callback ─────────────────────────────────────────────────────────
@app.route("/callback")
def callback():
    error = request.args.get("error")
    if error:
        return f"Auth error: {error}", 400

    code = request.args.get("code")
    state = request.args.get("state")

    if not code or not state:
        return "Missing code or state", 400

    if state != session.pop("oauth_state", None):
        return "Invalid state — possible CSRF attack", 400

    verifier = session.pop("pkce_verifier", None)

    try:
        tokens = client.exchange_code(code, code_verifier=verifier)
    except TokenPayIDError as e:
        return f"Token exchange failed: {e}", 401

    user = tokens.get("user", {})

    # Store in session (use a proper session store in production)
    session["access_token"] = tokens["access_token"]
    session["refresh_token"] = tokens.get("refresh_token")
    session["user"] = user

    return jsonify({
        "message": "Login successful",
        "user": {
            "id":    user.get("id"),
            "name":  user.get("name"),
            "email": user.get("email"),
            "role":  user.get("role"),
        },
        "access_token":  tokens["access_token"],
        "expires_in":    tokens.get("expires_in", 3600),
    })


# ── 3. Protected route example ─────────────────────────────────────────────────
@app.route("/me")
def me():
    token = session.get("access_token")
    if not token:
        return jsonify({"error": "Not authenticated"}), 401

    try:
        user = client.get_user(token)
        return jsonify({"user": user})
    except TokenPayIDError as e:
        return jsonify({"error": str(e)}), 401


# ── 4. Refresh token ───────────────────────────────────────────────────────────
@app.route("/refresh")
def refresh():
    refresh_tok = session.get("refresh_token")
    if not refresh_tok:
        return jsonify({"error": "No refresh token"}), 401

    try:
        tokens = client.refresh_token(refresh_tok)
        session["access_token"] = tokens["access_token"]
        session["refresh_token"] = tokens.get("refresh_token", refresh_tok)
        return jsonify({"access_token": tokens["access_token"]})
    except TokenPayIDError as e:
        return jsonify({"error": str(e)}), 401


# ── 5. Logout ──────────────────────────────────────────────────────────────────
@app.route("/logout", methods=["POST"])
def logout():
    token = session.pop("access_token", None)
    if token:
        try:
            client.revoke_token(token)
        except TokenPayIDError:
            pass
    session.clear()
    return jsonify({"success": True})


if __name__ == "__main__":
    print("TOKEN PAY ID example running at http://localhost:5000")
    print("Open http://localhost:5000/login to start")
    app.run(debug=True, port=5000)
