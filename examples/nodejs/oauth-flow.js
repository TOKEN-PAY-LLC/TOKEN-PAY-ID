'use strict';

/**
 * TOKEN PAY ID — Node.js OAuth 2.0 + PKCE Example
 * Framework: Express.js
 *
 * Install: npm install express @tokenpay/id
 * Run:     node oauth-flow.js
 */

const express = require('express');
const { TokenPayIDClient } = require('@tokenpay/id');

const app = express();

const client = new TokenPayIDClient({
    clientId:     process.env.TPID_PUBLIC_KEY,    // tpid_pk_...
    clientSecret: process.env.TPID_SECRET_KEY,    // tpid_sk_...
    redirectUri:  'http://localhost:3000/callback',
});

// ── In-memory state store (use Redis/DB in production) ────────────────────────
const stateStore = new Map();

// ── 1. Start login ─────────────────────────────────────────────────────────────
app.get('/login', async (req, res) => {
    const { verifier, challenge } = await client.generatePKCE();
    const state = Math.random().toString(36).slice(2);

    stateStore.set(state, { verifier, createdAt: Date.now() });

    const url = client.getAuthorizationUrl({
        scope: 'openid profile email',
        state,
        codeChallenge: challenge,
    });

    res.redirect(url);
});

// ── 2. Handle callback ─────────────────────────────────────────────────────────
app.get('/callback', async (req, res) => {
    const { code, state, error } = req.query;

    if (error) return res.status(400).send('Auth error: ' + error);
    if (!code || !state) return res.status(400).send('Missing code or state');

    const stored = stateStore.get(state);
    if (!stored) return res.status(400).send('Invalid state — possible CSRF');
    stateStore.delete(state);

    try {
        const tokens = await client.exchangeCode(code, stored.verifier);
        const user = tokens.user;

        // Store tokens in session (use express-session or similar in production)
        res.json({
            message: 'Login successful',
            user: {
                id:    user.id,
                name:  user.name,
                email: user.email,
                role:  user.role,
            },
            access_token:  tokens.access_token,
            refresh_token: tokens.refresh_token,
            expires_in:    tokens.expires_in,
        });
    } catch (err) {
        console.error('[TokenPayID] Error:', err.message);
        res.status(401).send('Authentication failed: ' + err.message);
    }
});

// ── 3. Protected route example ─────────────────────────────────────────────────
app.get('/me', async (req, res) => {
    const token = (req.headers.authorization || '').replace('Bearer ', '');
    if (!token) return res.status(401).json({ error: 'No token' });

    try {
        const user = await client.getUser(token);
        res.json({ user });
    } catch (err) {
        res.status(401).json({ error: err.message });
    }
});

// ── 4. Logout ──────────────────────────────────────────────────────────────────
app.post('/logout', async (req, res) => {
    const token = (req.headers.authorization || '').replace('Bearer ', '');
    if (token) {
        try { await client.revokeToken(token); } catch (_) {}
    }
    res.json({ success: true });
});

app.listen(3000, () => {
    console.log('TOKEN PAY ID example running at http://localhost:3000');
    console.log('Open http://localhost:3000/login to start');
});
