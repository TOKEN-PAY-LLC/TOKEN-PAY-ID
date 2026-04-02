'use strict';

/**
 * TOKEN PAY ID — Node.js Webhook Handler Example
 * Framework: Express.js
 *
 * Install: npm install express @tokenpay/id
 * Run:     node webhook-handler.js
 */

const express = require('express');
const { TokenPayIDClient } = require('@tokenpay/id');

const app = express();

const WEBHOOK_SECRET = process.env.TPID_WEBHOOK_SECRET; // from Dashboard → Settings

// ── Parse raw body for signature verification ────────────────────────────────
app.post('/webhook', express.raw({ type: 'application/json' }), (req, res) => {
    const signature = req.headers['x-tpid-signature'];
    const payload = req.body.toString('utf-8');

    if (!signature || !WEBHOOK_SECRET) {
        return res.status(400).json({ error: 'Missing signature or secret' });
    }

    // Verify signature (HMAC-SHA256, Stripe-style)
    const valid = TokenPayIDClient.verifyWebhookSignature(
        payload,
        signature,
        WEBHOOK_SECRET,
        300  // 5 minute tolerance
    );

    if (!valid) {
        console.warn('[WEBHOOK] Invalid signature');
        return res.status(401).json({ error: 'Invalid signature' });
    }

    // Parse and handle the event
    const event = JSON.parse(payload);
    console.log(`[WEBHOOK] ${event.event} — delivery: ${event.id}`);

    switch (event.event) {
        case 'user.oauth_connect':
            console.log('User connected:', event.data.email);
            // TODO: provision user in your system
            break;

        case 'user.unlink':
            console.log('User disconnected:', event.data.user_id);
            // TODO: revoke user access
            break;

        case 'key.created':
            console.log('API key created:', event.data.key_name);
            break;

        case 'key.revoked':
            console.log('API key revoked:', event.data.key_id);
            break;

        default:
            console.log('Unhandled event:', event.event);
    }

    res.json({ received: true });
});

app.listen(4000, () => {
    console.log('Webhook handler running at http://localhost:4000/webhook');
});
