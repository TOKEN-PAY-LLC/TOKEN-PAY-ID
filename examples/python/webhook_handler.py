"""
TOKEN PAY ID — Python Webhook Handler Example
Framework: Flask

Install: pip install flask tokenpay-id
Run:     TPID_WEBHOOK_SECRET=whsec_... python webhook_handler.py
"""

import os
import json
from flask import Flask, request, jsonify

from tokenpay_id import TokenPayIDClient

app = Flask(__name__)

WEBHOOK_SECRET = os.environ.get("TPID_WEBHOOK_SECRET", "")


@app.route("/webhook", methods=["POST"])
def webhook():
    signature = request.headers.get("X-TPID-Signature", "")
    payload = request.get_data(as_text=True)

    if not signature or not WEBHOOK_SECRET:
        return jsonify({"error": "Missing signature or secret"}), 400

    # Verify signature (HMAC-SHA256, Stripe-style)
    valid = TokenPayIDClient.verify_webhook_signature(
        payload=payload,
        signature=signature,
        secret=WEBHOOK_SECRET,
        tolerance=300,  # 5 minute tolerance
    )

    if not valid:
        print("[WEBHOOK] Invalid signature")
        return jsonify({"error": "Invalid signature"}), 401

    # Parse and handle the event
    event = json.loads(payload)
    event_type = event.get("event", "")
    print(f"[WEBHOOK] {event_type} — delivery: {event.get('id')}")

    if event_type == "user.oauth_connect":
        user = event.get("data", {})
        print(f"  User connected: {user.get('email')}")
        # TODO: provision user in your system

    elif event_type == "user.unlink":
        print(f"  User disconnected: {event['data'].get('user_id')}")
        # TODO: revoke user access

    elif event_type == "key.created":
        print(f"  API key created: {event['data'].get('key_name')}")

    elif event_type == "key.revoked":
        print(f"  API key revoked: {event['data'].get('key_id')}")

    else:
        print(f"  Unhandled event: {event_type}")

    return jsonify({"received": True})


if __name__ == "__main__":
    print("Webhook handler running at http://localhost:4000/webhook")
    app.run(port=4000)
