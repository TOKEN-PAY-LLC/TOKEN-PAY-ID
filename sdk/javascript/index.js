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
     */
    constructor(config = {}) {
        if (!config.clientId) throw new Error('[TokenPayID] clientId is required');
        if (!config.clientSecret) throw new Error('[TokenPayID] clientSecret is required');
        if (!config.redirectUri) throw new Error('[TokenPayID] redirectUri is required');

        this.clientId = config.clientId;
        this.clientSecret = config.clientSecret;
        this.redirectUri = config.redirectUri;
        this.baseUrl = (config.baseUrl || BASE_URL).replace(/\/$/, '');
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
        return `${this.baseUrl}/api/v1/oauth/authorize?${params}`;
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

    // ─── TOKEN REVOCATION ────────────────────────────────────────────────────

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

    // ─── INTERNAL ────────────────────────────────────────────────────────────

    async _post(path, body) {
        const res = await fetch(this.baseUrl + path, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        const data = await res.json();
        if (!res.ok) throw new TokenPayIDError(data.error || { code: 'request_failed', message: res.statusText, status: res.status });
        return data;
    }

    async _get(path, accessToken) {
        const res = await fetch(this.baseUrl + path, {
            headers: { Authorization: 'Bearer ' + accessToken },
        });
        const data = await res.json();
        if (!res.ok) throw new TokenPayIDError(data.error || { code: 'request_failed', message: res.statusText, status: res.status });
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
