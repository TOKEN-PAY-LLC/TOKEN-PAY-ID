'use strict';

const BASE_URL = 'https://tokenpay.space';

/**
 * TOKEN PAY ID — JavaScript SDK
 * Official client for TOKEN PAY ID API (OAuth 2.0 + OpenID Connect)
 * https://tokenpay.space/docs
 */
class TokenPayIDClient {
    /**
     * @param {object} config
     * @param {string} config.clientId      - Your public key (tpid_pk_...)
     * @param {string} config.clientSecret  - Your secret key (tpid_sk_...)
     * @param {string} config.redirectUri   - OAuth callback URL
     * @param {string} [config.baseUrl]     - Override API base URL
     * @param {'v1'|'v3'} [config.apiVersion='v1'] - API version; v1 remains the default
     */
    constructor(config = {}) {
        if (!config.clientId) throw new Error('[TokenPayID] clientId is required');
        if (!config.clientSecret) throw new Error('[TokenPayID] clientSecret is required');
        if (!config.redirectUri) throw new Error('[TokenPayID] redirectUri is required');

        this.clientId = config.clientId;
        this.clientSecret = config.clientSecret;
        this.redirectUri = config.redirectUri;
        this.baseUrl = (config.baseUrl || BASE_URL).replace(/\/$/, '');
        this.apiVersion = config.apiVersion || 'v1';
        if (!['v1', 'v3'].includes(this.apiVersion)) {
            throw new Error('[TokenPayID] apiVersion must be "v1" or "v3"');
        }
    }

    // ─── PKCE HELPERS ────────────────────────────────────────────────────────

    /**
     * Generate a PKCE code verifier and challenge.
     * Use in browser/Node.js environments.
     * @returns {{ verifier: string, challenge: string }}
     */
    async generatePKCE() {
        const array = new Uint8Array(32);
        if (typeof crypto !== 'undefined' && crypto.getRandomValues) {
            crypto.getRandomValues(array);
        } else {
            const { randomBytes } = await import('crypto');
            randomBytes(32).copy(Buffer.from(array.buffer));
        }
        const verifier = _base64url(array);
        let challenge;
        if (typeof crypto !== 'undefined' && crypto.subtle) {
            const hash = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier));
            challenge = _base64url(new Uint8Array(hash));
        } else {
            const { createHash } = await import('crypto');
            challenge = createHash('sha256').update(verifier).digest('base64url');
        }
        return { verifier, challenge };
    }

    // ─── AUTHORIZATION URL ───────────────────────────────────────────────────

    /**
     * Build the authorization URL to redirect the user to.
     * @param {object} [opts]
     * @param {string} [opts.scope='profile email']
     * @param {string} [opts.state]           - CSRF token (recommended)
     * @param {string} [opts.codeChallenge]   - PKCE challenge
     * @returns {string} URL
     */
    getAuthorizationUrl(opts = {}) {
        const params = new URLSearchParams({
            client_id: this.clientId,
            redirect_uri: this.redirectUri,
            response_type: 'code',
            scope: opts.scope || 'profile email',
        });
        if (opts.state) params.set('state', opts.state);
        if (opts.codeChallenge) {
            params.set('code_challenge', opts.codeChallenge);
            params.set('code_challenge_method', 'S256');
        }
        return `${this.baseUrl}/api/${this.apiVersion}/oauth/authorize?${params}`;
    }

    // ─── TOKEN EXCHANGE ──────────────────────────────────────────────────────

    /**
     * Exchange authorization code for tokens.
     * @param {string} code           - Code from redirect query param
     * @param {string} [codeVerifier] - PKCE verifier (if used)
     * @returns {Promise<{access_token, refresh_token, user}>}
     */
    async exchangeCode(code, codeVerifier) {
        const body = {
            grant_type: 'authorization_code',
            code,
            client_id: this.clientId,
            client_secret: this.clientSecret,
            redirect_uri: this.redirectUri,
        };
        if (codeVerifier) body.code_verifier = codeVerifier;
        return this._post('/api/v1/oauth/token', body);
    }

    /**
     * Refresh an access token.
     * @param {string} refreshToken
     * @returns {Promise<{access_token, refresh_token}>}
     */
    async refreshToken(refreshToken) {
        return this._post('/api/v1/oauth/token', {
            grant_type: 'refresh_token',
            refresh_token: refreshToken,
            client_id: this.clientId,
            client_secret: this.clientSecret,
        });
    }

    // ─── USER ────────────────────────────────────────────────────────────────

    /**
     * Get the authenticated user's info.
     * @param {string} accessToken
     * @returns {Promise<User>}
     */
    async getUser(accessToken) {
        return this._get('/api/v1/oauth/userinfo', accessToken);
    }

    /**
     * Get full user profile (requires JWT from login, not OAuth token).
     * @param {string} accessToken
     * @returns {Promise<User>}
     */
    async getMe(accessToken) {
        return this._get('/api/v1/users/me', accessToken);
    }

    // ─── TOKEN REVOCATION ────────────────────────────────────────────────────────

    /**
     * Revoke an OAuth access or refresh token.
     * @param {string} token
     */
    async revokeToken(token) {
        return this._post('/api/v1/oauth/revoke', {
            token,
            client_id: this.clientId,
            client_secret: this.clientSecret,
        });
    }

    // ─── NOTIFICATIONS ───────────────────────────────────────────────────────────

    /**
     * Get notification history (last 50).
     * @param {string} accessToken
     * @returns {Promise<{notifications: Array, unread: number}>}
     */
    async getNotifications(accessToken) {
        return this._get('/api/v1/notifications', accessToken);
    }

    /**
     * Mark a notification as read.
     * @param {string} accessToken
     * @param {string} notificationId
     */
    async markNotificationRead(accessToken, notificationId) {
        return this._put('/api/v1/notifications/' + encodeURIComponent(notificationId) + '/read', accessToken);
    }

    /**
     * Mark all notifications as read.
     * @param {string} accessToken
     */
    async markAllNotificationsRead(accessToken) {
        return this._put('/api/v1/notifications/read-all', accessToken);
    }

    // ─── WEBHOOK VERIFICATION ───────────────────────────────────────────────────

    /**
     * Verify a webhook signature (Stripe-style t=timestamp,v1=hmac).
     * @param {string} payload     - Raw request body
     * @param {string} signature   - X-TPID-Signature header value
     * @param {string} secret      - Your webhook secret
     * @param {number} [tolerance=300] - Max age in seconds (default 5 min)
     * @returns {boolean}
     */
    static verifyWebhookSignature(payload, signature, secret, tolerance = 300) {
        if (typeof payload !== 'string' || typeof signature !== 'string' || typeof secret !== 'string' || !Number.isFinite(tolerance) || tolerance < 0) return false;
        const parts = {};
        signature.split(',').forEach(p => {
            const [k, ...v] = p.split('=');
            parts[k] = v.join('=');
        });
        if (!/^\d+$/.test(parts.t || '') || !parts.v1) return false;
        const ts = Number(parts.t);
        if (!Number.isSafeInteger(ts) || ts <= 0) return false;
        if (Math.abs(Date.now() / 1000 - ts) > tolerance) return false;
        try {
            const { createHmac } = require('crypto');
            const expected = createHmac('sha256', secret)
                .update(ts + '.' + payload)
                .digest('hex');
            if (!/^[a-f0-9]{64}$/i.test(parts.v1)) return false;
            const expectedBytes = Buffer.from(expected, 'hex');
            const suppliedBytes = Buffer.from(parts.v1, 'hex');
            return expectedBytes.length === suppliedBytes.length && require('crypto').timingSafeEqual(expectedBytes, suppliedBytes);
        } catch (_) {
            return false;
        }
    }

    // ─── INTERNAL ────────────────────────────────────────────────────────────

    async _post(path, body) {
        const res = await fetch(this._apiUrl(path), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        return this._readResponse(res);
    }

    async _get(path, accessToken) {
        const res = await fetch(this._apiUrl(path), {
            headers: { Authorization: 'Bearer ' + accessToken },
        });
        return this._readResponse(res);
    }

    async _put(path, accessToken) {
        const res = await fetch(this._apiUrl(path), {
            method: 'PUT',
            headers: { Authorization: 'Bearer ' + accessToken },
        });
        return this._readResponse(res);
    }

    _apiUrl(path) {
        return this.baseUrl + path.replace(/^\/api\/v1(?=\/)/, `/api/${this.apiVersion}`);
    }

    async _readResponse(res) {
        const maxBytes = 1_048_576;
        if (!res.body || typeof res.body.getReader !== 'function') {
            throw new TokenPayIDError({ code: 'invalid_response', message: 'Response streaming is unavailable', status: res.status });
        }
        const reader = res.body.getReader();
        const chunks = [];
        let totalBytes = 0;
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            totalBytes += value.byteLength;
            if (totalBytes > maxBytes) {
                await reader.cancel();
                throw new TokenPayIDError({ code: 'response_too_large', message: 'TOKEN PAY ID response exceeded 1 MiB', status: res.status });
            }
            chunks.push(value);
        }
        const bytes = new Uint8Array(totalBytes);
        let offset = 0;
        for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
        const body = new TextDecoder().decode(bytes);
        let data;
        try { data = body ? JSON.parse(body) : {}; }
        catch (_) {
            if (res.ok) throw new TokenPayIDError({ code: 'invalid_response', message: 'TOKEN PAY ID returned a non-JSON response', status: res.status });
            data = { error: { code: 'invalid_response', message: 'TOKEN PAY ID returned a non-JSON error response' } };
        }
        if (!res.ok) {
            const error = data.error;
            throw new TokenPayIDError(typeof error === 'object' && error ? { ...error, status: error.status || res.status } : {
                code: typeof error === 'string' ? error : 'request_failed',
                message: data.error_description || data.message || res.statusText,
                status: res.status,
            });
        }
        return data;
    }
}

class TokenPayIDError extends Error {
    constructor(err) {
        super(err.message || 'TOKEN PAY ID error');
        this.code = err.code;
        this.status = err.status;
    }
}

function _base64url(buf) {
    return btoa(String.fromCharCode(...buf))
        .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

module.exports = { TokenPayIDClient, TokenPayIDError };
