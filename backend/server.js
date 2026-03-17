const express = require('express');
const { Pool } = require('pg');
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const cors = require('cors');
const helmet = require('helmet');
const rateLimit = require('express-rate-limit');
const { v4: uuidv4 } = require('uuid');
const crypto = require('crypto');
const { initTransporter, sendEmail, templates } = require('./email-service');

// ===== TOTP 2FA (RFC 6238, no external deps) =====
function _b32Decode(s) {
    const a = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
    let bits = 0, val = 0, out = [];
    for (const c of s.toUpperCase().replace(/=/g,'')) {
        const i = a.indexOf(c); if (i < 0) continue;
        val = (val << 5) | i; bits += 5;
        if (bits >= 8) { out.push((val >>> (bits-8)) & 255); bits -= 8; }
    }
    return Buffer.from(out);
}
function _b32Encode(buf) {
    const a = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
    let bits = 0, val = 0, out = '';
    for (const b of buf) { val = (val << 8) | b; bits += 8; while (bits >= 5) { out += a[(val >>> (bits-5)) & 31]; bits -= 5; } }
    if (bits > 0) out += a[(val << (5-bits)) & 31];
    return out;
}
function _hotp(secret, counter) {
    const key = _b32Decode(secret);
    const buf = Buffer.alloc(8);
    let tmp = counter;
    for (let i = 7; i >= 0; i--) { buf[i] = tmp & 0xff; tmp = Math.floor(tmp / 256); }
    const hmac = crypto.createHmac('sha1', key).update(buf).digest();
    const off = hmac[19] & 0xf;
    const code = ((hmac[off] & 0x7f) << 24) | ((hmac[off+1] & 0xff) << 16) | ((hmac[off+2] & 0xff) << 8) | (hmac[off+3] & 0xff);
    return String(code % 1000000).padStart(6, '0');
}
function totpGenSecret() { return _b32Encode(crypto.randomBytes(20)); }
function totpVerify(secret, token) {
    if (!secret || !token || !/^\d{6}$/.test(token)) return false;
    const t = Math.floor(Date.now() / 30000);
    for (let i = -1; i <= 1; i++) { if (_hotp(secret, t+i) === token) return true; }
    return false;
}
function totpQrUrl(email, secret) {
    return `otpauth://totp/${encodeURIComponent('TOKEN PAY ID:'+email)}?secret=${secret}&issuer=${encodeURIComponent('TOKEN PAY ID')}&digits=6&period=30`;
}

const app = express();
const PORT = process.env.PORT || 8080;

// ===== CONFIG =====
const JWT_SECRET = process.env.JWT_SECRET || 'tpid_jwt_secret_' + uuidv4();
const JWT_REFRESH_SECRET = process.env.JWT_REFRESH_SECRET || 'tpid_refresh_' + uuidv4();
const ADMIN_EMAIL = process.env.ADMIN_EMAIL || 'info@tokenpay.space';
const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD || '';

// ===== DATABASE =====
const pool = new Pool({
    host: process.env.DB_HOST || '5.23.55.152',
    port: process.env.DB_PORT || 5432,
    database: process.env.DB_NAME || 'default_db',
    user: process.env.DB_USER || 'gen_user',
    password: process.env.DB_PASSWORD || '',
    max: 20,
    idleTimeoutMillis: 30000,
    connectionTimeoutMillis: 5000,
});

// ===== MIDDLEWARE =====
app.set('trust proxy', 1);
app.use(helmet({
    contentSecurityPolicy: false,
    crossOriginEmbedderPolicy: false,
    // Nginx already sets these — disable to avoid duplicate headers
    frameguard: false,
    xContentTypeOptions: false,
    xXssProtection: false,
    referrerPolicy: false,
    hsts: false,
    xDownloadOptions: false,
    xPermittedCrossDomainPolicies: false
}));

const allowedOrigins = (process.env.CORS_ORIGIN || 'https://tokenpay.space,https://cupol.space,https://auth.tokenpay.space,https://id.tokenpay.space').split(',').map(s => s.trim());
app.use(cors({
    origin: function(origin, cb) {
        if (!origin || allowedOrigins.includes(origin) || allowedOrigins.includes('*')) return cb(null, true);
        cb(new Error('CORS blocked'));
    },
    credentials: true,
    methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
    allowedHeaders: ['Content-Type', 'Authorization', 'X-Request-ID', 'Accept-Language'],
    exposedHeaders: ['X-Request-ID']
}));
app.use(express.json({ limit: '1mb' }));

// Request ID + request language resolution
app.use((req, res, next) => {
    const rid = req.headers['x-request-id'] || ('tpid_' + uuidv4().replace(/-/g, '').substring(0, 16));
    req.requestId = rid;
    res.set('X-Request-ID', rid);
    // Resolve request language: header > body > query > default
    req.lang = (req.headers['accept-language'] || '').startsWith('en') ? 'en' : 'ru';
    next();
});

// General rate limit — 120 req/min
const limiter = rateLimit({
    windowMs: 60 * 1000,
    max: 120,
    standardHeaders: true,
    legacyHeaders: false,
    keyGenerator: (req) => req.ip,
    message: { error: { code: 'rate_limit', message: 'Too many requests', status: 429 } }
});
app.use('/api/', limiter);

// Strict auth rate limit — 8 req/min for login/register
const authLimiter = rateLimit({
    windowMs: 60 * 1000,
    max: 8,
    standardHeaders: true,
    legacyHeaders: false,
    keyGenerator: (req) => req.ip,
    message: { error: { code: 'rate_limit', message: 'Too many auth attempts. Try again in 1 minute.', status: 429 } }
});

// ===== VALIDATION HELPERS =====
function isValidEmail(email) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email) && email.length <= 255;
}
function isStrongPassword(password) {
    return password && password.length >= 8 && password.length <= 128;
}
function sanitize(str, maxLen = 255) {
    if (!str) return '';
    return String(str)
        .replace(/[<>"'&]/g, c => ({'<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#x27;','&':'&amp;'}[c] || c))
        .replace(/javascript:/gi, '')
        .replace(/on\w+=/gi, '')
        .substring(0, maxLen).trim();
}
function escapeLike(str) {
    return String(str).replace(/[%_\\]/g, c => '\\' + c);
}
function secureCode6() {
    return String(crypto.randomInt(100000, 999999));
}

// ===== AUTH MIDDLEWARE =====
function authMiddleware(req, res, next) {
    const auth = req.headers.authorization;
    if (!auth || !auth.startsWith('Bearer ')) {
        return res.status(401).json({ error: { code: 'unauthorized', message: 'Missing or invalid token', status: 401 } });
    }
    const token = auth.split(' ')[1];

    // Check if it's an API key
    if (token.startsWith('tpid_sk_')) {
        pool.query('SELECT u.*, k.expires_at as key_expires_at FROM users u JOIN api_keys k ON u.id = k.user_id WHERE k.secret_key = $1 AND k.status = $2', [token, 'active'])
            .then(result => {
                if (result.rows.length === 0) return res.status(401).json({ error: { code: 'invalid_key', message: 'Invalid or revoked API key', status: 401 } });
                const row = result.rows[0];
                if (row.key_expires_at && new Date(row.key_expires_at) < new Date()) {
                    return res.status(401).json({ error: { code: 'key_expired', message: 'API key has expired', status: 401 } });
                }
                req.user = row;
                next();
            })
            .catch(() => res.status(500).json({ error: { code: 'server_error', message: 'Internal server error', status: 500 } }));
        return;
    }

    // JWT token
    try {
        const decoded = jwt.verify(token, JWT_SECRET);
        pool.query('SELECT * FROM users WHERE id = $1', [decoded.userId])
            .then(result => {
                if (result.rows.length === 0) return res.status(401).json({ error: { code: 'user_not_found', message: 'User not found', status: 401 } });
                req.user = result.rows[0];
                next();
            })
            .catch(() => res.status(500).json({ error: { code: 'server_error', message: 'Internal server error', status: 500 } }));
    } catch (err) {
        return res.status(401).json({ error: { code: 'invalid_token', message: 'Token expired or invalid', status: 401 } });
    }
}

function adminMiddleware(req, res, next) {
    if (!req.user || req.user.role !== 'admin') {
        return res.status(403).json({ error: { code: 'forbidden', message: 'Admin access required', status: 403 } });
    }
    next();
}

function presidentMiddleware(req, res, next) {
    if (!req.user || req.user.role !== 'admin' || req.user.email !== ADMIN_EMAIL) {
        return res.status(403).json({ error: { code: 'forbidden', message: 'President access required', status: 403 } });
    }
    next();
}

function generateTokens(userId, rememberMe = true) {
    const accessToken = jwt.sign({ userId }, JWT_SECRET, { expiresIn: '1h' });
    const refreshToken = jwt.sign({ userId }, JWT_REFRESH_SECRET, { expiresIn: rememberMe ? '30d' : '24h' });
    return { accessToken, refreshToken, expiresIn: 3600 };
}

// ===== API VERSION HEADER =====
app.use((req, res, next) => {
    res.setHeader('X-API-Version', '2.1.0');
    res.setHeader('X-TPID-SDK-Latest', '1.2.0');
    next();
});

// ===== CAPTCHA =====
const captchaStore = new Map(); // nonce → { x, createdAt }
const captchaConfig = { mode: 'auto', auto_threshold: 3, images: [] };

function cleanCaptchaStore() {
    const ttl = 5 * 60 * 1000;
    const now = Date.now();
    for (const [k, v] of captchaStore) { if (now - v.createdAt > ttl) captchaStore.delete(k); }
}

// Public: get config mode
app.get('/api/v1/captcha/config', (req, res) => {
    res.json({ mode: captchaConfig.mode, auto_threshold: captchaConfig.auto_threshold });
});

// Public: generate a puzzle challenge
app.get('/api/v1/captcha/challenge', (req, res) => {
    cleanCaptchaStore();
    const nonce = crypto.randomBytes(20).toString('hex');
    const holeX = Math.floor(Math.random() * 160) + 60; // 60–220px
    const holeY = Math.floor(Math.random() * 60) + 40;  // 40–100px
    captchaStore.set(nonce, { x: holeX, y: holeY, createdAt: Date.now() });
    res.json({ nonce, hole_x: holeX, hole_y: holeY, width: 320, height: 160, piece_size: 50 });
});

// Public: verify solution
app.post('/api/v1/captcha/verify', (req, res) => {
    const { nonce, x } = req.body;
    if (!nonce || x === undefined) return res.status(400).json({ error: { code: 'bad_request', message: 'nonce and x required' } });
    const ch = captchaStore.get(nonce);
    if (!ch) return res.status(400).json({ error: { code: 'captcha_expired', message: 'Challenge expired or invalid' } });
    captchaStore.delete(nonce);
    if (Math.abs(Number(x) - ch.x) > 18) {
        return res.json({ success: false, error: { code: 'captcha_failed', message: 'Incorrect. Please try again.' } });
    }
    const captchaToken = jwt.sign({ captcha: true, ts: Date.now() }, JWT_SECRET, { expiresIn: '15m' });
    res.json({ success: true, captcha_token: captchaToken });
});

// Admin: get captcha config (president only)
app.get('/api/v1/admin/captcha/config', authMiddleware, presidentMiddleware, (req, res) => {
    res.json(captchaConfig);
});

// Admin: update captcha config (president only)
app.put('/api/v1/admin/captcha/config', authMiddleware, presidentMiddleware, (req, res) => {
    const { mode, auto_threshold } = req.body;
    if (mode && ['auto', 'always', 'off'].includes(mode)) captchaConfig.mode = mode;
    if (auto_threshold !== undefined) captchaConfig.auto_threshold = Math.max(1, Math.min(10, Number(auto_threshold)));
    res.json({ success: true, config: captchaConfig });
});

// Admin: add custom captcha image (president only)
app.post('/api/v1/admin/captcha/images', authMiddleware, presidentMiddleware, (req, res) => {
    const { image, name } = req.body;
    if (!image) return res.status(400).json({ error: { code: 'bad_request', message: 'image required' } });
    const id = uuidv4();
    captchaConfig.images.push({ id, name: sanitize(name || 'Image', 64), image: image.substring(0, 2 * 1024 * 1024), createdAt: new Date().toISOString() });
    if (captchaConfig.images.length > 20) captchaConfig.images.shift();
    res.json({ success: true, id });
});

// Admin: delete captcha image (president only)
app.delete('/api/v1/admin/captcha/images/:id', authMiddleware, presidentMiddleware, (req, res) => {
    const before = captchaConfig.images.length;
    captchaConfig.images = captchaConfig.images.filter(i => i.id !== req.params.id);
    res.json({ success: captchaConfig.images.length < before });
});

// ===== HEALTH =====
app.get('/health', async (req, res) => {
    try {
        await pool.query('SELECT 1');
        res.json({ status: 'ok', service: 'tokenpay-id-api', version: '2.1.0', timestamp: new Date().toISOString(), db: 'connected' });
    } catch (err) {
        res.status(503).json({ status: 'degraded', service: 'tokenpay-id-api', version: '2.1.0', timestamp: new Date().toISOString(), db: 'disconnected' });
    }
});

// ===== AUTH ROUTES =====

// Send email verification code (for login & register)
app.post('/api/v1/auth/send-code', authLimiter, async (req, res) => {
    try {
        const { email, type, name } = req.body;
        if (!email || !type) {
            return res.status(400).json({ error: { code: 'missing_fields', message: 'email and type required', status: 400 } });
        }
        if (!['login', 'register'].includes(type)) {
            return res.status(400).json({ error: { code: 'invalid_type', message: 'type must be login or register', status: 400 } });
        }
        if (!isValidEmail(email)) {
            return res.status(400).json({ error: { code: 'invalid_email', message: 'Invalid email format', status: 400 } });
        }

        const emailLower = email.toLowerCase();

        // For register: check email not taken
        if (type === 'register') {
            const existing = await pool.query('SELECT id FROM users WHERE email = $1', [emailLower]);
            if (existing.rows.length > 0) {
                return res.status(409).json({ error: { code: 'email_exists', message: 'Email already registered', status: 409 } });
            }
        }

        // For login: check email exists
        if (type === 'login') {
            const existing = await pool.query('SELECT id FROM users WHERE email = $1', [emailLower]);
            if (existing.rows.length === 0) {
                await new Promise(r => setTimeout(r, 200));
                return res.status(404).json({ error: { code: 'not_found', message: 'Email not registered', status: 404 } });
            }
        }

        // Rate limit: max 1 code per email per 60 seconds
        const recent = await pool.query(
            "SELECT id FROM email_codes WHERE email = $1 AND type = $2 AND created_at > NOW() - INTERVAL '60 seconds' AND used IS NOT TRUE",
            [emailLower, type]
        );
        if (recent.rows.length > 0) {
            return res.status(429).json({ error: { code: 'code_cooldown', message: 'Code already sent. Wait 60 seconds.', status: 429 } });
        }

        // Generate 6-digit code
        const code = secureCode6();

        // Invalidate previous codes for this email+type
        await pool.query("UPDATE email_codes SET used = TRUE WHERE email = $1 AND type = $2 AND used IS NOT TRUE", [emailLower, type]);

        // Store code (expires_at uses DB clock to avoid Node↔PG clock skew)
        await pool.query(
            "INSERT INTO email_codes (id, email, code, type, used, expires_at, created_at) VALUES ($1, $2, $3, $4, FALSE, NOW() + INTERVAL '10 minutes', NOW())",
            [uuidv4(), emailLower, code, type]
        );

        // Send email (respect lang parameter for enterprise API calls)
        const lang = req.body.lang || req.query.lang || req.lang || 'ru';
        const displayName = name || emailLower.split('@')[0];
        const subject = lang === 'en'
            ? (type === 'register' ? 'Registration Code — TOKEN PAY ID' : 'Login Code — TOKEN PAY ID')
            : (type === 'register' ? 'Код регистрации — TOKEN PAY ID' : 'Код входа — TOKEN PAY ID');
        sendEmail(emailLower, subject,
            templates.verificationCode(displayName, code, 10, lang)
        ).catch(err => console.error('[EMAIL] send-code error:', err.message));

        res.json({ success: true, message: 'Code sent to email', expires_in: 600 });
    } catch (err) {
        console.error('Send code error:', err);
        res.status(500).json({ error: { code: 'server_error', message: 'Internal server error', status: 500 } });
    }
});

// Helper: verify email code (consume=false keeps the code valid for multi-step login like 2FA)
async function verifyEmailCode(email, code, type, consume = true) {
    if (!code) return false;
    const clean = String(code).replace(/\D/g, '');
    if (!/^\d{6}$/.test(clean)) return false;
    const result = await pool.query(
        'SELECT id FROM email_codes WHERE email = $1 AND code = $2 AND type = $3 AND used = FALSE AND expires_at > NOW() ORDER BY created_at DESC LIMIT 1',
        [email.toLowerCase(), clean, type]
    );
    if (result.rows.length === 0) return false;
    if (consume) {
        await pool.query('UPDATE email_codes SET used = TRUE WHERE id = $1', [result.rows[0].id]);
    }
    return true;
}

// Register (requires email_code from /auth/send-code)
app.post('/api/v1/auth/register', authLimiter, async (req, res) => {
    try {
        const { email, password, name, email_code: rawCode } = req.body;
        const email_code = rawCode ? String(rawCode).replace(/\D/g, '').trim() : undefined;
        if (!email || !password || !name) {
            return res.status(400).json({ error: { code: 'missing_fields', message: 'Email, password and name are required', status: 400 } });
        }
        if (!isValidEmail(email)) {
            return res.status(400).json({ error: { code: 'invalid_email', message: 'Invalid email format', status: 400 } });
        }
        if (!isStrongPassword(password)) {
            return res.status(400).json({ error: { code: 'weak_password', message: 'Password must be 8-128 characters', status: 400 } });
        }
        if (!email_code) {
            return res.status(400).json({ error: { code: 'missing_code', message: 'Email verification code is required. Call /auth/send-code first.', status: 400 } });
        }
        const cleanName = sanitize(name, 100);
        if (cleanName.length < 1) {
            return res.status(400).json({ error: { code: 'invalid_name', message: 'Name is required', status: 400 } });
        }

        // Verify email code
        const codeValid = await verifyEmailCode(email, email_code, 'register');
        if (!codeValid) {
            return res.status(400).json({ error: { code: 'invalid_code', message: 'Invalid or expired verification code', status: 400 } });
        }

        const existing = await pool.query('SELECT id FROM users WHERE email = $1', [email.toLowerCase()]);
        if (existing.rows.length > 0) {
            return res.status(409).json({ error: { code: 'email_exists', message: 'Email already registered', status: 409 } });
        }

        const id = 'tpid_usr_' + uuidv4().replace(/-/g, '').substring(0, 16);
        const hashedPassword = await bcrypt.hash(password, 12);

        await pool.query(
            `INSERT INTO users (id, email, password_hash, name, role, email_verified, two_factor_enabled, created_at, last_login)
             VALUES ($1, $2, $3, $4, $5, $6, $7, NOW(), NOW())`,
            [id, email.toLowerCase(), hashedPassword, cleanName, 'user', true, false]
        );

        // Create default API key
        const pkPrefix = 'tpid_pk_' + uuidv4().replace(/-/g, '').substring(0, 16);
        const skKey = 'tpid_sk_' + uuidv4().replace(/-/g, '') + uuidv4().replace(/-/g, '').substring(0, 8);
        await pool.query(
            `INSERT INTO api_keys (id, user_id, name, public_key, secret_key, status, created_at)
             VALUES ($1, $2, $3, $4, $5, $6, NOW())`,
            [uuidv4(), id, 'Default Key', pkPrefix, skKey, 'active']
        );

        // Log activity
        await pool.query(
            `INSERT INTO activity_log (id, user_id, type, title, status, ip, created_at)
             VALUES ($1, $2, $3, $4, $5, $6, NOW())`,
            [uuidv4(), id, 'account_created', 'Аккаунт создан', 'success', req.ip]
        );

        const tokens = generateTokens(id);

        // Create session on registration
        const regSessionId = 'ses_' + uuidv4().replace(/-/g, '').substring(0, 16);
        const regUa = req.headers['user-agent'] || 'Unknown';
        const regDeviceType = /mobile|android|iphone|ipad/i.test(regUa) ? 'mobile' : /mac|windows|linux/i.test(regUa) ? 'desktop' : 'unknown';
        const regBrowser = regUa.match(/(Chrome|Firefox|Safari|Edge|Opera)[/\s]([\d.]+)/)?.[1] || 'Browser';
        const regDeviceLabel = `${regBrowser} (${regDeviceType})`;
        await pool.query(
            `INSERT INTO sessions (id, user_id, device, ip, last_active, created_at) VALUES ($1, $2, $3, $4, NOW(), NOW())`,
            [regSessionId, id, regDeviceLabel.substring(0, 200), req.ip]
        );

        // Send welcome email
        const lang = req.body.lang || req.lang || 'ru';
        const welcomeSubject = lang === 'en' ? 'Welcome to TOKEN PAY ID' : 'Добро пожаловать в TOKEN PAY ID';
        sendEmail(email.toLowerCase(), welcomeSubject,
            templates.welcome(cleanName, lang)
        ).catch(() => {});

        res.status(201).json({
            user: { id, email: email.toLowerCase(), name: cleanName, role: 'user', email_verified: true, two_factor_enabled: false, locale: 'ru' },
            ...tokens,
            token_type: 'Bearer'
        });
    } catch (err) {
        console.error('Register error:', err);
        res.status(500).json({ error: { code: 'server_error', message: 'Internal server error', status: 500 } });
    }
});

// Login (requires email_code — auto-sent on first call with valid password)
app.post('/api/v1/auth/login', authLimiter, async (req, res) => {
    try {
        const { email, password, email_code: rawEmailCode, two_factor_code, remember_me = true, lang } = req.body;
        const email_code = rawEmailCode ? String(rawEmailCode).replace(/\D/g, '').trim() : undefined;
        if (!email || !password) {
            return res.status(400).json({ error: { code: 'missing_fields', message: 'Email and password are required', status: 400 } });
        }

        const result = await pool.query('SELECT * FROM users WHERE email = $1', [email.toLowerCase()]);
        if (result.rows.length === 0) {
            await new Promise(r => setTimeout(r, 200));
            return res.status(401).json({ error: { code: 'invalid_credentials', message: 'Invalid email or password', status: 401 } });
        }

        const user = result.rows[0];
        const valid = await bcrypt.compare(password, user.password_hash);
        if (!valid) {
            await pool.query(
                `INSERT INTO activity_log (id, user_id, type, title, status, ip, created_at)
                 VALUES ($1, $2, $3, $4, $5, $6, NOW())`,
                [uuidv4(), user.id, 'login_failed', 'Неудачная попытка входа', 'error', req.ip]
            );
            return res.status(401).json({ error: { code: 'invalid_credentials', message: 'Invalid email or password', status: 401 } });
        }

        // Password is valid. Now check if email_code is provided.
        if (!email_code) {
            // Auto-send email code
            const emailLower = email.toLowerCase();
            const recent = await pool.query(
                "SELECT id FROM email_codes WHERE email = $1 AND type = 'login' AND created_at > NOW() - INTERVAL '60 seconds' AND used IS NOT TRUE",
                [emailLower]
            );
            if (recent.rows.length === 0) {
                const code = secureCode6();
                await pool.query("UPDATE email_codes SET used = TRUE WHERE email = $1 AND type = 'login' AND used IS NOT TRUE", [emailLower]);
                await pool.query(
                    "INSERT INTO email_codes (id, email, code, type, used, expires_at, created_at) VALUES ($1, $2, $3, $4, FALSE, NOW() + INTERVAL '10 minutes', NOW())",
                    [uuidv4(), emailLower, code, 'login']
                );
                const loginLang = req.body.lang || req.lang || (user.locale || 'ru');
                const loginCodeSubject = loginLang === 'en' ? 'Login Code — TOKEN PAY ID' : 'Код входа — TOKEN PAY ID';
                sendEmail(emailLower, loginCodeSubject,
                    templates.verificationCode(user.name, code, 10, loginLang)
                ).catch(err => console.error('[EMAIL] login code error:', err.message));
            }
            return res.status(200).json({
                requires_email_code: true,
                requires_2fa: !!(user.two_factor_enabled && user.totp_secret),
                message: 'Verification code sent to your email'
            });
        }

        // Verify email code — don't consume yet if 2FA step is still pending
        const needs2FA = !!(user.two_factor_enabled && user.totp_secret);
        const shouldConsume = !needs2FA || !!two_factor_code;
        const codeValid = await verifyEmailCode(email, email_code, 'login', shouldConsume);
        if (!codeValid) {
            return res.status(400).json({ error: { code: 'invalid_code', message: 'Invalid or expired email code', status: 400 } });
        }

        // 2FA check
        if (needs2FA) {
            if (!two_factor_code) {
                return res.status(200).json({ requires_2fa: true, email_code_verified: true });
            }
            if (!totpVerify(user.totp_secret, two_factor_code.replace(/\s/g, ''))) {
                await pool.query(
                    `INSERT INTO activity_log (id, user_id, type, title, status, ip, created_at)
                     VALUES ($1, $2, $3, $4, $5, $6, NOW())`,
                    [uuidv4(), user.id, '2fa_failed', 'Неверный код 2FA', 'error', req.ip]
                );
                return res.status(401).json({ error: { code: 'invalid_2fa', message: 'Invalid 2FA code', status: 401 } });
            }
        }

        // Update last login
        await pool.query('UPDATE users SET last_login = NOW() WHERE id = $1', [user.id]);

        // Log activity
        await pool.query(
            `INSERT INTO activity_log (id, user_id, type, title, status, ip, created_at)
             VALUES ($1, $2, $3, $4, $5, $6, NOW())`,
            [uuidv4(), user.id, 'login', 'Вход в аккаунт', 'success', req.ip]
        );

        // Create session
        const newSessionId = 'ses_' + uuidv4().replace(/-/g, '').substring(0, 16);
        const ua = req.headers['user-agent'] || 'Unknown';
        const deviceType = /mobile|android|iphone|ipad/i.test(ua) ? 'mobile' : /mac|windows|linux/i.test(ua) ? 'desktop' : 'unknown';
        const browser = ua.match(/(Chrome|Firefox|Safari|Edge|Opera)[/\s]([\d.]+)/)?.[1] || 'Browser';
        const deviceLabel = `${browser} (${deviceType})`;
        await pool.query(
            `INSERT INTO sessions (id, user_id, device, ip, last_active, created_at)
             VALUES ($1, $2, $3, $4, NOW(), NOW())`,
            [newSessionId, user.id, deviceLabel.substring(0, 200), req.ip]
        );

        const tokens = generateTokens(user.id, remember_me !== false);

        // Send login notification email (async)
        const userLang = req.body.lang || user.locale || req.lang || 'ru';
        const loginTime = new Date().toLocaleString(userLang === 'en' ? 'en-US' : 'ru-RU', { timeZone: 'Europe/Moscow' });
        const loginSubject = userLang === 'en' ? 'New Sign-In — TOKEN PAY ID' : 'Новый вход в TOKEN PAY ID';
        sendEmail(user.email, loginSubject, templates.loginNotification(user.name, req.ip, deviceLabel, loginTime, userLang)).catch(() => {});

        res.json({
            user: {
                id: user.id,
                email: user.email,
                name: user.name,
                role: user.role,
                email_verified: user.email_verified,
                two_factor_enabled: user.two_factor_enabled,
                locale: user.locale || 'ru',
                created_at: user.created_at,
                last_login: user.last_login
            },
            ...tokens,
            token_type: 'Bearer',
            session_id: newSessionId
        });
    } catch (err) {
        console.error('Login error:', err);
        res.status(500).json({ error: { code: 'server_error', message: 'Internal server error', status: 500 } });
    }
});

// Refresh token
app.post('/api/v1/auth/refresh', async (req, res) => {
    try {
        const { refresh_token } = req.body;
        if (!refresh_token) return res.status(400).json({ error: { code: 'missing_token', message: 'Refresh token required', status: 400 } });

        const decoded = jwt.verify(refresh_token, JWT_REFRESH_SECRET);
        const result = await pool.query('SELECT * FROM users WHERE id = $1', [decoded.userId]);
        if (result.rows.length === 0) return res.status(401).json({ error: { code: 'user_not_found', message: 'User not found', status: 401 } });

        const tokens = generateTokens(decoded.userId);
        res.json({ ...tokens, token_type: 'Bearer' });
    } catch (err) {
        res.status(401).json({ error: { code: 'invalid_token', message: 'Invalid refresh token', status: 401 } });
    }
});

// Quick re-login (no password) — only if user logged in within last 24h
app.post('/api/v1/auth/quick-login', authLimiter, async (req, res) => {
    try {
        const { email, email_code: rawCode, remember_me = true } = req.body;
        const email_code = rawCode ? String(rawCode).replace(/\D/g, '').trim() : undefined;
        if (!email || !email_code) {
            return res.status(400).json({ error: { code: 'missing_fields', message: 'Email and code required', status: 400 } });
        }
        const result = await pool.query('SELECT * FROM users WHERE email = $1', [email.toLowerCase()]);
        if (result.rows.length === 0) {
            await new Promise(r => setTimeout(r, 200));
            return res.status(401).json({ error: { code: 'user_not_found', message: 'User not found', status: 401 } });
        }
        const user = result.rows[0];
        // Only allow if last_login was within 24h
        const lastLogin = user.last_login ? new Date(user.last_login).getTime() : 0;
        if (Date.now() - lastLogin > 24 * 60 * 60 * 1000) {
            return res.status(401).json({ error: { code: 'quick_login_expired', message: 'Session expired. Please use full login with password.', status: 401 } });
        }
        // Verify email code
        const codeValid = await verifyEmailCode(email, email_code, 'login');
        if (!codeValid) {
            return res.status(400).json({ error: { code: 'invalid_code', message: 'Invalid or expired verification code', status: 400 } });
        }
        // Handle 2FA
        const { two_factor_code } = req.body;
        if (user.two_factor_enabled) {
            if (!two_factor_code) {
                return res.json({ requires_2fa: true });
            }
            if (!totpVerify(user.totp_secret, two_factor_code)) {
                return res.status(401).json({ error: { code: 'invalid_2fa', message: 'Invalid 2FA code', status: 401 } });
            }
        }
        const tokens = generateTokens(user.id, remember_me);
        await pool.query('UPDATE users SET last_login = NOW() WHERE id = $1', [user.id]);
        const sessionId = 'ses_' + uuidv4().replace(/-/g, '').substring(0, 16);
        const ua = req.headers['user-agent'] || 'Unknown';
        const deviceType = /mobile|android|iphone|ipad/i.test(ua) ? 'mobile' : /mac|windows|linux/i.test(ua) ? 'desktop' : 'unknown';
        const browser = ua.match(/(Chrome|Firefox|Safari|Edge|Opera)[/\s]([\d.]+)/)?.[1] || 'Browser';
        await pool.query(
            `INSERT INTO sessions (id, user_id, device, ip, last_active, created_at) VALUES ($1, $2, $3, $4, NOW(), NOW())`,
            [sessionId, user.id, `${browser} (${deviceType})`.substring(0, 200), req.ip]
        );
        await pool.query(
            `INSERT INTO activity_log (id, user_id, type, title, status, ip, created_at) VALUES ($1, $2, $3, $4, $5, $6, NOW())`,
            [uuidv4(), user.id, 'login', 'Быстрый вход (без пароля)', 'success', req.ip]
        );
        const userObj = { id: user.id, email: user.email, name: user.name, role: user.role, email_verified: user.email_verified, two_factor_enabled: user.two_factor_enabled, locale: user.locale || 'ru', theme: user.theme || 'dark', company_name: user.company_name };
        res.json({ user: userObj, ...tokens, token_type: 'Bearer', session_id: sessionId });
    } catch (err) {
        console.error('Quick login error:', err);
        res.status(500).json({ error: { code: 'server_error', message: 'Internal server error', status: 500 } });
    }
});

// Verify token
app.post('/api/v1/auth/verify', async (req, res) => {
    try {
        const { token } = req.body;
        if (!token) return res.status(400).json({ error: { code: 'missing_token', message: 'Token required', status: 400 } });

        const decoded = jwt.verify(token, JWT_SECRET);
        const result = await pool.query('SELECT id, email, name, email_verified FROM users WHERE id = $1', [decoded.userId]);
        if (result.rows.length === 0) return res.json({ valid: false });

        const user = result.rows[0];
        res.json({ valid: true, user_id: user.id, email: user.email, name: user.name, expires_at: decoded.exp });
    } catch (err) {
        res.json({ valid: false });
    }
});

// Logout
app.post('/api/v1/auth/logout', authMiddleware, async (req, res) => {
    try {
        const { session_id } = req.body;
        if (session_id) {
            await pool.query('DELETE FROM sessions WHERE id = $1 AND user_id = $2', [session_id, req.user.id]);
        } else {
            await pool.query('DELETE FROM sessions WHERE user_id = $1', [req.user.id]);
        }
        await pool.query(
            `INSERT INTO activity_log (id, user_id, type, title, status, ip, created_at)
             VALUES ($1, $2, $3, $4, $5, $6, NOW())`,
            [uuidv4(), req.user.id, 'logout', 'Выход из аккаунта', 'success', req.ip]
        );
        res.json({ success: true });
    } catch (err) {
        res.status(500).json({ error: { code: 'server_error', message: 'Server error', status: 500 } });
    }
});

// Forgot password — send reset code to email
app.post('/api/v1/auth/forgot-password', authLimiter, async (req, res) => {
    try {
        const { email } = req.body;
        if (!email || !isValidEmail(email)) {
            return res.status(400).json({ error: { code: 'invalid_email', message: 'Valid email is required', status: 400 } });
        }
        const emailLower = email.toLowerCase();
        const userResult = await pool.query('SELECT id, name, locale FROM users WHERE email = $1', [emailLower]);
        if (userResult.rows.length === 0) {
            // Don't reveal whether user exists — return success anyway
            await new Promise(r => setTimeout(r, 300));
            return res.json({ success: true, message: 'If the email is registered, a reset code has been sent.' });
        }
        const user = userResult.rows[0];

        // Rate limit: max 1 code per email per 60 seconds
        const recent = await pool.query(
            "SELECT id FROM email_codes WHERE email = $1 AND type = 'reset' AND created_at > NOW() - INTERVAL '60 seconds' AND used IS NOT TRUE",
            [emailLower]
        );
        if (recent.rows.length > 0) {
            return res.status(429).json({ error: { code: 'code_cooldown', message: 'Code already sent. Wait 60 seconds.', status: 429 } });
        }

        // Generate 6-digit code
        const code = secureCode6();

        // Invalidate previous reset codes
        await pool.query("UPDATE email_codes SET used = TRUE WHERE email = $1 AND type = 'reset' AND used IS NOT TRUE", [emailLower]);

        // Store code (15 min expiry)
        await pool.query(
            "INSERT INTO email_codes (id, email, code, type, used, expires_at, created_at) VALUES ($1, $2, $3, $4, FALSE, NOW() + INTERVAL '15 minutes', NOW())",
            [uuidv4(), emailLower, code, 'reset']
        );

        // Send reset email
        const lang = req.body.lang || req.lang || (user.locale || 'ru');
        const subject = lang === 'en' ? 'Password Reset — TOKEN PAY ID' : 'Сброс пароля — TOKEN PAY ID';
        sendEmail(emailLower, subject,
            templates.passwordReset(user.name, code, 15, lang)
        ).catch(err => console.error('[EMAIL] forgot-password error:', err.message));

        await pool.query(
            `INSERT INTO activity_log (id, user_id, type, title, status, ip, created_at) VALUES ($1, $2, $3, $4, $5, $6, NOW())`,
            [uuidv4(), user.id, 'password_reset_requested', 'Запрос сброса пароля', 'info', req.ip]
        );

        res.json({ success: true, message: 'If the email is registered, a reset code has been sent.' });
    } catch (err) {
        console.error('Forgot password error:', err);
        res.status(500).json({ error: { code: 'server_error', message: 'Internal server error', status: 500 } });
    }
});

// Reset password — verify code and set new password
app.post('/api/v1/auth/reset-password', authLimiter, async (req, res) => {
    try {
        const { email, code, new_password } = req.body;
        if (!email || !code || !new_password) {
            return res.status(400).json({ error: { code: 'missing_fields', message: 'email, code, and new_password required', status: 400 } });
        }
        if (!isValidEmail(email)) {
            return res.status(400).json({ error: { code: 'invalid_email', message: 'Invalid email', status: 400 } });
        }
        if (!isStrongPassword(new_password)) {
            return res.status(400).json({ error: { code: 'weak_password', message: 'Password must be 8-128 characters', status: 400 } });
        }

        const emailLower = email.toLowerCase();

        // Verify reset code
        const codeValid = await verifyEmailCode(emailLower, code, 'reset', true);
        if (!codeValid) {
            return res.status(400).json({ error: { code: 'invalid_code', message: 'Invalid or expired reset code', status: 400 } });
        }

        // Find user
        const userResult = await pool.query('SELECT id, name, locale FROM users WHERE email = $1', [emailLower]);
        if (userResult.rows.length === 0) {
            return res.status(404).json({ error: { code: 'not_found', message: 'User not found', status: 404 } });
        }
        const user = userResult.rows[0];

        // Update password
        const hash = await bcrypt.hash(new_password, 12);
        await pool.query('UPDATE users SET password_hash = $1 WHERE id = $2', [hash, user.id]);

        // Revoke all sessions
        await pool.query('DELETE FROM sessions WHERE user_id = $1', [user.id]);

        // Log activity
        await pool.query(
            `INSERT INTO activity_log (id, user_id, type, title, status, ip, created_at) VALUES ($1, $2, $3, $4, $5, $6, NOW())`,
            [uuidv4(), user.id, 'password_reset', 'Пароль сброшен', 'success', req.ip]
        );

        // Send security alert email
        const lang = req.body.lang || req.lang || (user.locale || 'ru');
        const subject = lang === 'en' ? 'Password Changed — TOKEN PAY ID' : 'Пароль изменён — TOKEN PAY ID';
        sendEmail(emailLower, subject,
            templates.securityAlert(user.name, lang === 'en' ? 'password reset' : 'сброс пароля', req.ip, lang)
        ).catch(() => {});

        res.json({ success: true, message: 'Password has been reset. All sessions revoked. Please log in.' });
    } catch (err) {
        console.error('Reset password error:', err);
        res.status(500).json({ error: { code: 'server_error', message: 'Internal server error', status: 500 } });
    }
});

// Change password
app.post('/api/v1/auth/change-password', authMiddleware, async (req, res) => {
    try {
        const { current_password, new_password } = req.body;
        if (!current_password || !new_password) {
            return res.status(400).json({ error: { code: 'missing_fields', message: 'current_password and new_password required', status: 400 } });
        }
        if (!isStrongPassword(new_password)) {
            return res.status(400).json({ error: { code: 'weak_password', message: 'Password must be 8-128 characters', status: 400 } });
        }
        const result = await pool.query('SELECT password_hash FROM users WHERE id = $1', [req.user.id]);
        const valid = await bcrypt.compare(current_password, result.rows[0].password_hash);
        if (!valid) return res.status(401).json({ error: { code: 'invalid_password', message: 'Current password is wrong', status: 401 } });
        const hash = await bcrypt.hash(new_password, 12);
        await pool.query('UPDATE users SET password_hash = $1 WHERE id = $2', [hash, req.user.id]);
        await pool.query('DELETE FROM sessions WHERE user_id = $1', [req.user.id]);
        await pool.query(
            `INSERT INTO activity_log (id, user_id, type, title, status, ip, created_at)
             VALUES ($1, $2, $3, $4, $5, $6, NOW())`,
            [uuidv4(), req.user.id, 'password_changed', 'Пароль изменён', 'success', req.ip]
        );
        const pwLang = req.user.locale || req.lang || 'ru';
        const pwSubject = pwLang === 'en' ? 'Password Changed — TOKEN PAY ID' : 'Пароль изменён — TOKEN PAY ID';
        sendEmail(req.user.email, pwSubject,
            templates.securityAlert(req.user.name, pwLang === 'en' ? 'password change' : 'смена пароля', req.ip, pwLang)
        ).catch(() => {});
        res.json({ success: true, message: 'Password changed. All sessions revoked.' });
    } catch (err) {
        res.status(500).json({ error: { code: 'server_error', message: 'Server error', status: 500 } });
    }
});

// 2FA: Setup — generate TOTP secret
app.post('/api/v1/auth/2fa/setup', authMiddleware, async (req, res) => {
    try {
        const secret = totpGenSecret();
        const qrUrl = totpQrUrl(req.user.email, secret);
        // Store temp secret (not enabled yet)
        await pool.query('UPDATE users SET totp_secret = $1 WHERE id = $2', [secret, req.user.id]);
        res.json({
            secret,
            qr_url: qrUrl,
            qr_image_url: `https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(qrUrl)}`,
            message: 'Scan QR code with your authenticator app, then call /2fa/enable with the code'
        });
    } catch (err) {
        res.status(500).json({ error: { code: 'server_error', message: 'Server error', status: 500 } });
    }
});

// 2FA: Enable — verify code and enable
app.post('/api/v1/auth/2fa/enable', authMiddleware, async (req, res) => {
    try {
        const { code } = req.body;
        if (!code) return res.status(400).json({ error: { code: 'missing_code', message: 'TOTP code required', status: 400 } });
        const result = await pool.query('SELECT totp_secret FROM users WHERE id = $1', [req.user.id]);
        const secret = result.rows[0]?.totp_secret;
        if (!secret) return res.status(400).json({ error: { code: 'no_secret', message: 'Call /2fa/setup first', status: 400 } });
        if (!totpVerify(secret, code.replace(/\s/g, ''))) {
            return res.status(400).json({ error: { code: 'invalid_code', message: 'Invalid TOTP code', status: 400 } });
        }
        await pool.query('UPDATE users SET two_factor_enabled = TRUE WHERE id = $1', [req.user.id]);
        await pool.query(
            `INSERT INTO activity_log (id, user_id, type, title, status, ip, created_at)
             VALUES ($1, $2, $3, $4, $5, $6, NOW())`,
            [uuidv4(), req.user.id, '2fa_enabled', 'Двухфакторная аутентификация включена', 'success', req.ip]
        );
        res.json({ success: true, message: '2FA enabled successfully' });
    } catch (err) {
        res.status(500).json({ error: { code: 'server_error', message: 'Server error', status: 500 } });
    }
});

// 2FA: Disable
app.post('/api/v1/auth/2fa/disable', authMiddleware, async (req, res) => {
    try {
        const { password, code } = req.body;
        if (!password) return res.status(400).json({ error: { code: 'missing_password', message: 'Password required to disable 2FA', status: 400 } });
        const result = await pool.query('SELECT password_hash, totp_secret FROM users WHERE id = $1', [req.user.id]);
        const valid = await bcrypt.compare(password, result.rows[0].password_hash);
        if (!valid) return res.status(401).json({ error: { code: 'invalid_password', message: 'Wrong password', status: 401 } });
        if (result.rows[0].totp_secret && code && !totpVerify(result.rows[0].totp_secret, code.replace(/\s/g, ''))) {
            return res.status(400).json({ error: { code: 'invalid_code', message: 'Invalid TOTP code', status: 400 } });
        }
        await pool.query('UPDATE users SET two_factor_enabled = FALSE, totp_secret = NULL WHERE id = $1', [req.user.id]);
        await pool.query(
            `INSERT INTO activity_log (id, user_id, type, title, status, ip, created_at)
             VALUES ($1, $2, $3, $4, $5, $6, NOW())`,
            [uuidv4(), req.user.id, '2fa_disabled', 'Двухфакторная аутентификация отключена', 'warning', req.ip]
        );
        res.json({ success: true, message: '2FA disabled' });
    } catch (err) {
        res.status(500).json({ error: { code: 'server_error', message: 'Server error', status: 500 } });
    }
});

// Email verification: verify token
app.get('/api/v1/auth/verify-email/:token', async (req, res) => {
    try {
        const { token } = req.params;
        const result = await pool.query(
            'SELECT id, email, name FROM users WHERE verification_token = $1 AND verification_expires > NOW() AND email_verified = FALSE',
            [token]
        );
        if (result.rows.length === 0) {
            return res.redirect('/login?error=invalid_verification_link');
        }
        const user = result.rows[0];
        await pool.query(
            'UPDATE users SET email_verified = TRUE, verification_token = NULL, verification_expires = NULL WHERE id = $1',
            [user.id]
        );
        await pool.query(
            `INSERT INTO activity_log (id, user_id, type, title, status, ip, created_at)
             VALUES ($1, $2, $3, $4, $5, $6, NOW())`,
            [uuidv4(), user.id, 'email_verified', 'Email подтверждён', 'success', req.ip]
        );
        res.redirect('/login?verified=1');
    } catch (err) {
        res.redirect('/login?error=server_error');
    }
});

// Email verification: resend
app.post('/api/v1/auth/resend-verification', authMiddleware, async (req, res) => {
    try {
        if (req.user.email_verified) {
            return res.status(400).json({ error: { code: 'already_verified', message: 'Email already verified', status: 400 } });
        }
        const token = crypto.randomBytes(32).toString('hex');
        const expires = new Date(Date.now() + 24 * 3600 * 1000);
        await pool.query(
            'UPDATE users SET verification_token = $1, verification_expires = $2 WHERE id = $3',
            [token, expires, req.user.id]
        );
        const verifyUrl = `https://tokenpay.space/api/v1/auth/verify-email/${token}`;
        const vLang = req.user.locale || req.lang || 'ru';
        const vSubject = vLang === 'en' ? 'Verify Email — TOKEN PAY ID' : 'Подтвердите email — TOKEN PAY ID';
        const code6 = secureCode6();
        await sendEmail(req.user.email, vSubject,
            templates.verificationCode(req.user.name, code6, 1440, vLang)
        );
        res.json({ success: true, message: 'Verification email sent' });
    } catch (err) {
        res.status(500).json({ error: { code: 'server_error', message: 'Server error', status: 500 } });
    }
});

// ===== USER ROUTES =====

// Get current user
app.get('/api/v1/users/me', authMiddleware, (req, res) => {
    const u = req.user;
    const data = {
        id: u.id, email: u.email, name: u.name, role: u.role,
        email_verified: u.email_verified, two_factor_enabled: u.two_factor_enabled,
        telegram_linked: u.telegram_linked || false,
        locale: u.locale || 'ru',
        theme: u.theme || 'dark',
        created_at: u.created_at, last_login: u.last_login,
        cupol_balance: u.cupol_balance || 0,
        cupol_subscription_end: u.cupol_subscription_end || null,
        cupol_subscription_active: u.cupol_subscription_active || false,
        cupol_username: u.cupol_username || null,
        cupol_synced_at: u.cupol_synced_at || null
    };
    if (u.role === 'enterprise') {
        data.company_name = u.company_name || '';
        data.website = u.website || '';
        data.description = u.description || '';
    }
    res.json(data);
});

// Update user
app.put('/api/v1/users/me', authMiddleware, async (req, res) => {
    try {
        const { name, locale, theme, telegram_id, telegram_linked } = req.body;
        if (name) {
            const cleanName = sanitize(name, 100);
            if (cleanName.length < 1) return res.status(400).json({ error: { code: 'invalid_name', message: 'Name is required', status: 400 } });
            await pool.query('UPDATE users SET name = $1 WHERE id = $2', [cleanName, req.user.id]);
            req.user.name = cleanName;
        }
        if (locale && ['ru', 'en'].includes(locale)) {
            await pool.query('UPDATE users SET locale = $1 WHERE id = $2', [locale, req.user.id]);
            req.user.locale = locale;
        }
        if (theme && ['light', 'dark'].includes(theme)) {
            await pool.query('UPDATE users SET theme = $1 WHERE id = $2', [theme, req.user.id]);
            req.user.theme = theme;
        }
        // Telegram linking (from CUPOL VPN integration)
        if (telegram_id !== undefined) {
            const tgId = telegram_id === null ? null : parseInt(telegram_id);
            if (tgId !== null && (isNaN(tgId) || tgId < 0)) return res.status(400).json({ error: { code: 'invalid_telegram_id', message: 'Invalid telegram_id', status: 400 } });
            // Check uniqueness
            if (tgId !== null) {
                const tgExists = await pool.query('SELECT id FROM users WHERE telegram_id = $1 AND id != $2', [tgId, req.user.id]);
                if (tgExists.rows.length > 0) return res.status(409).json({ error: { code: 'telegram_taken', message: 'This Telegram account is already linked', status: 409 } });
            }
            await pool.query('UPDATE users SET telegram_id = $1 WHERE id = $2', [tgId, req.user.id]);
        }
        if (telegram_linked !== undefined) {
            await pool.query('UPDATE users SET telegram_linked = $1 WHERE id = $2', [!!telegram_linked, req.user.id]);
        }
        await pool.query(
            `INSERT INTO activity_log (id, user_id, type, title, status, ip, created_at)
             VALUES ($1, $2, $3, $4, $5, $6, NOW())`,
            [uuidv4(), req.user.id, 'profile_updated', 'Профиль обновлён', 'success', req.ip]
        );
        res.json({ id: req.user.id, email: req.user.email, name: req.user.name, locale: req.user.locale || 'ru', theme: req.user.theme || 'dark' });
    } catch (err) {
        res.status(500).json({ error: { code: 'server_error', message: 'Internal server error', status: 500 } });
    }
});

// Get activity
app.get('/api/v1/users/activity', authMiddleware, async (req, res) => {
    try {
        const limit = Math.min(parseInt(req.query.limit) || 50, 200);
        const offset = parseInt(req.query.offset) || 0;
        const type = req.query.type;

        let query = 'SELECT * FROM activity_log WHERE user_id = $1';
        const params = [req.user.id];

        if (type) {
            query += ' AND type LIKE $2';
            params.push('%' + escapeLike(type) + '%');
        }
        // Get total count
        const countQuery = query.replace('SELECT *', 'SELECT COUNT(*)');
        query += ' ORDER BY created_at DESC LIMIT $' + (params.length + 1) + ' OFFSET $' + (params.length + 2);
        params.push(limit, offset);

        const [result, countResult] = await Promise.all([
            pool.query(query, params),
            pool.query(countQuery, params.slice(0, params.length - 2))
        ]);
        res.json({ activity: result.rows, total: parseInt(countResult.rows[0].count) });
    } catch (err) {
        res.status(500).json({ error: { code: 'server_error', message: 'Internal server error', status: 500 } });
    }
});

// Get sessions
app.get('/api/v1/users/sessions', authMiddleware, async (req, res) => {
    try {
        const result = await pool.query(
            'SELECT id, device, ip, last_active, created_at FROM sessions WHERE user_id = $1 ORDER BY last_active DESC',
            [req.user.id]
        );
        res.json({ sessions: result.rows });
    } catch (err) {
        res.status(500).json({ error: { code: 'server_error', message: 'Internal server error', status: 500 } });
    }
});

// Revoke session
app.delete('/api/v1/users/sessions/:id', authMiddleware, async (req, res) => {
    try {
        await pool.query('DELETE FROM sessions WHERE id = $1 AND user_id = $2', [req.params.id, req.user.id]);
        res.json({ success: true });
    } catch (err) {
        res.status(500).json({ error: { code: 'server_error', message: 'Internal server error', status: 500 } });
    }
});

// ===== API KEY ROUTES =====

// List keys (enterprise + admin only)
app.get('/api/v1/keys', authMiddleware, async (req, res) => {
    try {
        if (req.user.role !== 'enterprise' && req.user.role !== 'admin') {
            return res.status(403).json({ error: { code: 'forbidden', message: 'Enterprise account required to manage API keys', status: 403 } });
        }
        const result = await pool.query(
            'SELECT id, name, public_key, LEFT(secret_key, 16) as secret_prefix, status, created_at, last_used, expires_at FROM api_keys WHERE user_id = $1 ORDER BY created_at DESC',
            [req.user.id]
        );
        res.json({ keys: result.rows });
    } catch (err) {
        res.status(500).json({ error: { code: 'server_error', message: 'Internal server error', status: 500 } });
    }
});

// Create key (enterprise + admin only)
app.post('/api/v1/keys', authMiddleware, async (req, res) => {
    try {
        if (req.user.role !== 'enterprise' && req.user.role !== 'admin') {
            return res.status(403).json({ error: { code: 'forbidden', message: 'Enterprise account required to create API keys', status: 403 } });
        }
        const { name, expires_in_days } = req.body;
        if (!name || !name.trim()) return res.status(400).json({ error: { code: 'missing_name', message: 'Key name is required', status: 400 } });
        if (name.trim().length > 100) return res.status(400).json({ error: { code: 'name_too_long', message: 'Key name must be under 100 characters', status: 400 } });

        let expiresAt = null;
        if (expires_in_days !== undefined && expires_in_days !== null) {
            const days = parseInt(expires_in_days);
            if (isNaN(days) || days < 1 || days > 3650) {
                return res.status(400).json({ error: { code: 'invalid_expiry', message: 'expires_in_days must be between 1 and 3650', status: 400 } });
            }
            expiresAt = new Date(Date.now() + days * 86400000);
        }

        const id = uuidv4();
        const publicKey = 'tpid_pk_' + uuidv4().replace(/-/g, '').substring(0, 16);
        const secretKey = 'tpid_sk_' + uuidv4().replace(/-/g, '') + uuidv4().replace(/-/g, '').substring(0, 8);

        await pool.query(
            `INSERT INTO api_keys (id, user_id, name, public_key, secret_key, status, expires_at, created_at)
             VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())`,
            [id, req.user.id, name.trim(), publicKey, secretKey, 'active', expiresAt]
        );

        await pool.query(
            `INSERT INTO activity_log (id, user_id, type, title, status, ip, created_at)
             VALUES ($1, $2, $3, $4, $5, $6, NOW())`,
            [uuidv4(), req.user.id, 'key_created', 'API ключ "' + name.trim() + '" создан', 'success', req.ip]
        );
        fireWebhook(req.user.id, 'key.created', { key_name: name.trim(), public_key: publicKey, expires_at: expiresAt ? expiresAt.toISOString() : null });

        res.status(201).json({ id, name: name.trim(), public_key: publicKey, secret_key: secretKey, status: 'active', expires_at: expiresAt ? expiresAt.toISOString() : null, created_at: new Date().toISOString() });
    } catch (err) {
        res.status(500).json({ error: { code: 'server_error', message: 'Internal server error', status: 500 } });
    }
});

// Revoke key (enterprise + admin only)
app.delete('/api/v1/keys/:id', authMiddleware, async (req, res) => {
    try {
        const result = await pool.query(
            'UPDATE api_keys SET status = $1 WHERE id = $2 AND user_id = $3 RETURNING name',
            ['revoked', req.params.id, req.user.id]
        );
        if (result.rows.length === 0) return res.status(404).json({ error: { code: 'not_found', message: 'Key not found', status: 404 } });

        await pool.query(
            `INSERT INTO activity_log (id, user_id, type, title, status, ip, created_at)
             VALUES ($1, $2, $3, $4, $5, $6, NOW())`,
            [uuidv4(), req.user.id, 'key_revoked', 'API ключ "' + result.rows[0].name + '" отозван', 'warning', req.ip]
        );
        fireWebhook(req.user.id, 'key.revoked', { key_id: req.params.id, key_name: result.rows[0].name });

        res.json({ success: true });
    } catch (err) {
        res.status(500).json({ error: { code: 'server_error', message: 'Internal server error', status: 500 } });
    }
});

// ===== API KEY APP BRANDING =====

// Update API key app branding (enterprise/admin only)
app.put('/api/v1/keys/:id/branding', authMiddleware, async (req, res) => {
    try {
        if (req.user.role !== 'enterprise' && req.user.role !== 'admin') {
            return res.status(403).json({ error: { code: 'forbidden', message: 'Enterprise access required', status: 403 } });
        }
        const { app_name, app_icon_url, app_description } = req.body;
        const updates = []; const params = []; let idx = 1;
        if (app_name !== undefined) { updates.push(`app_name = $${idx++}`); params.push(sanitize(app_name, 255) || null); }
        if (app_icon_url !== undefined) { updates.push(`app_icon_url = $${idx++}`); params.push(sanitize(app_icon_url, 500) || null); }
        if (app_description !== undefined) { updates.push(`app_description = $${idx++}`); params.push(sanitize(app_description, 1000) || null); }
        if (updates.length === 0) return res.status(400).json({ error: { code: 'no_updates', message: 'No fields to update', status: 400 } });
        params.push(req.params.id, req.user.id);
        const result = await pool.query(`UPDATE api_keys SET ${updates.join(', ')} WHERE id = $${idx} AND user_id = $${idx + 1} RETURNING id, name, app_name, app_icon_url, app_description`, params);
        if (result.rows.length === 0) return res.status(404).json({ error: { code: 'not_found', message: 'Key not found', status: 404 } });
        res.json({ success: true, key: result.rows[0] });
    } catch (err) {
        res.status(500).json({ error: { code: 'server_error', message: 'Server error', status: 500 } });
    }
});

// ===== ADMIN ROUTES =====

// Admin: list all users
app.get('/api/v1/admin/users', authMiddleware, adminMiddleware, async (req, res) => {
    try {
        const limit = Math.min(parseInt(req.query.limit) || 50, 200);
        const offset = parseInt(req.query.offset) || 0;
        const result = await pool.query(
            'SELECT id, email, name, role, email_verified, two_factor_enabled, created_at, last_login FROM users ORDER BY created_at DESC LIMIT $1 OFFSET $2',
            [limit, offset]
        );
        const countResult = await pool.query('SELECT COUNT(*) FROM users');
        res.json({ users: result.rows, total: parseInt(countResult.rows[0].count) });
    } catch (err) {
        res.status(500).json({ error: { code: 'server_error', message: 'Internal server error', status: 500 } });
    }
});

// Admin: get user by id
app.get('/api/v1/admin/users/:id', authMiddleware, adminMiddleware, async (req, res) => {
    try {
        const result = await pool.query(
            'SELECT id, email, name, role, email_verified, two_factor_enabled, created_at, last_login FROM users WHERE id = $1',
            [req.params.id]
        );
        if (result.rows.length === 0) return res.status(404).json({ error: { code: 'not_found', message: 'User not found', status: 404 } });

        const keys = await pool.query('SELECT id, name, public_key, status, created_at FROM api_keys WHERE user_id = $1', [req.params.id]);
        const activity = await pool.query('SELECT * FROM activity_log WHERE user_id = $1 ORDER BY created_at DESC LIMIT 20', [req.params.id]);
        const sessions = await pool.query('SELECT * FROM sessions WHERE user_id = $1 ORDER BY last_active DESC', [req.params.id]);

        res.json({ user: result.rows[0], keys: keys.rows, activity: activity.rows, sessions: sessions.rows });
    } catch (err) {
        res.status(500).json({ error: { code: 'server_error', message: 'Internal server error', status: 500 } });
    }
});

// Admin: update user (change role, name, etc.)
app.put('/api/v1/admin/users/:id', authMiddleware, adminMiddleware, async (req, res) => {
    try {
        const { role, name, email_verified } = req.body;
        const updates = [];
        const params = [];
        let paramIdx = 1;

        if (role && ['user', 'enterprise', 'admin'].includes(role)) {
            updates.push(`role = $${paramIdx++}`);
            params.push(role);
        }
        if (name) {
            updates.push(`name = $${paramIdx++}`);
            params.push(sanitize(name, 100));
        }
        if (typeof email_verified === 'boolean') {
            updates.push(`email_verified = $${paramIdx++}`);
            params.push(email_verified);
        }

        if (updates.length === 0) {
            return res.status(400).json({ error: { code: 'no_updates', message: 'No valid fields to update', status: 400 } });
        }

        params.push(req.params.id);
        const result = await pool.query(
            `UPDATE users SET ${updates.join(', ')} WHERE id = $${paramIdx} RETURNING id, email, name, role, email_verified`,
            params
        );
        if (result.rows.length === 0) return res.status(404).json({ error: { code: 'not_found', message: 'User not found', status: 404 } });

        await pool.query(
            `INSERT INTO activity_log (id, user_id, type, title, status, ip, created_at)
             VALUES ($1, $2, $3, $4, $5, $6, NOW())`,
            [uuidv4(), req.user.id, 'admin_user_update', `Обновлён пользователь ${result.rows[0].email}`, 'success', req.ip]
        );

        res.json({ user: result.rows[0] });
    } catch (err) {
        res.status(500).json({ error: { code: 'server_error', message: 'Internal server error', status: 500 } });
    }
});

// Admin: delete user
app.delete('/api/v1/admin/users/:id', authMiddleware, adminMiddleware, async (req, res) => {
    try {
        await pool.query('DELETE FROM activity_log WHERE user_id = $1', [req.params.id]);
        await pool.query('DELETE FROM sessions WHERE user_id = $1', [req.params.id]);
        await pool.query('DELETE FROM api_keys WHERE user_id = $1', [req.params.id]);
        await pool.query('DELETE FROM users WHERE id = $1', [req.params.id]);
        res.json({ success: true });
    } catch (err) {
        res.status(500).json({ error: { code: 'server_error', message: 'Internal server error', status: 500 } });
    }
});

// Admin: stats
app.get('/api/v1/admin/stats', authMiddleware, adminMiddleware, async (req, res) => {
    try {
        const users = await pool.query('SELECT COUNT(*) FROM users');
        const keys = await pool.query("SELECT COUNT(*) FROM api_keys WHERE status = 'active'");
        const sessions = await pool.query('SELECT COUNT(*) FROM sessions');
        const todayActivity = await pool.query("SELECT COUNT(*) FROM activity_log WHERE created_at > NOW() - INTERVAL '24 hours'");
        res.json({
            total_users: parseInt(users.rows[0].count),
            active_keys: parseInt(keys.rows[0].count),
            active_sessions: parseInt(sessions.rows[0].count),
            activity_24h: parseInt(todayActivity.rows[0].count)
        });
    } catch (err) {
        res.status(500).json({ error: { code: 'server_error', message: 'Internal server error', status: 500 } });
    }
});

// Admin: global activity log
app.get('/api/v1/admin/activity', authMiddleware, adminMiddleware, async (req, res) => {
    try {
        const limit = Math.min(parseInt(req.query.limit) || 100, 500);
        const offset = parseInt(req.query.offset) || 0;
        const type = req.query.type;

        let query = `SELECT a.*, u.email, u.name as user_name FROM activity_log a LEFT JOIN users u ON a.user_id = u.id`;
        const params = [];

        if (type) {
            query += ' WHERE a.type LIKE $1';
            params.push('%' + escapeLike(type) + '%');
        }
        query += ` ORDER BY a.created_at DESC LIMIT $${params.length + 1} OFFSET $${params.length + 2}`;
        params.push(limit, offset);

        const result = await pool.query(query, params);
        const countResult = await pool.query('SELECT COUNT(*) FROM activity_log');
        res.json({ activity: result.rows, total: parseInt(countResult.rows[0].count) });
    } catch (err) {
        res.status(500).json({ error: { code: 'server_error', message: 'Internal server error', status: 500 } });
    }
});

// Admin: system info
app.get('/api/v1/admin/system', authMiddleware, adminMiddleware, async (req, res) => {
    try {
        const [users, verified, twofa, enterprise, keys, revokedKeys, sessions,
               todayActivity, weekActivity, totalActivity, todayLogins,
               todayRegistrations, failedLogins, connectedApps, oauthCodes,
               roleBreakdown, recentRegs] = await Promise.all([
            pool.query('SELECT COUNT(*) FROM users'),
            pool.query('SELECT COUNT(*) FROM users WHERE email_verified = TRUE'),
            pool.query('SELECT COUNT(*) FROM users WHERE two_factor_enabled = TRUE'),
            pool.query("SELECT COUNT(*) FROM users WHERE role = 'enterprise'"),
            pool.query("SELECT COUNT(*) FROM api_keys WHERE status = 'active'"),
            pool.query("SELECT COUNT(*) FROM api_keys WHERE status = 'revoked'"),
            pool.query('SELECT COUNT(*) FROM sessions'),
            pool.query("SELECT COUNT(*) FROM activity_log WHERE created_at > NOW() - INTERVAL '24 hours'"),
            pool.query("SELECT COUNT(*) FROM activity_log WHERE created_at > NOW() - INTERVAL '7 days'"),
            pool.query('SELECT COUNT(*) FROM activity_log'),
            pool.query("SELECT COUNT(*) FROM activity_log WHERE type = 'login' AND created_at > NOW() - INTERVAL '24 hours'"),
            pool.query("SELECT COUNT(*) FROM activity_log WHERE type = 'account_created' AND created_at > NOW() - INTERVAL '24 hours'"),
            pool.query("SELECT COUNT(*) FROM activity_log WHERE type = 'login_failed' AND created_at > NOW() - INTERVAL '24 hours'"),
            pool.query('SELECT COUNT(*) FROM connected_apps'),
            pool.query("SELECT COUNT(*) FROM oauth_codes WHERE expires_at > NOW() AND used = FALSE"),
            pool.query("SELECT role, COUNT(*) as count FROM users GROUP BY role ORDER BY count DESC"),
            pool.query(`SELECT DATE(created_at) as date, COUNT(*) as count 
                FROM users WHERE created_at > NOW() - INTERVAL '7 days' 
                GROUP BY DATE(created_at) ORDER BY date DESC`)
        ]);

        res.json({
            users: {
                total: parseInt(users.rows[0].count),
                verified: parseInt(verified.rows[0].count),
                two_factor: parseInt(twofa.rows[0].count),
                enterprise: parseInt(enterprise.rows[0].count),
                roles: roleBreakdown.rows
            },
            keys: {
                active: parseInt(keys.rows[0].count),
                revoked: parseInt(revokedKeys.rows[0].count)
            },
            sessions: {
                active: parseInt(sessions.rows[0].count)
            },
            activity: {
                total: parseInt(totalActivity.rows[0].count),
                last_24h: parseInt(todayActivity.rows[0].count),
                last_7d: parseInt(weekActivity.rows[0].count),
                logins_24h: parseInt(todayLogins.rows[0].count),
                registrations_24h: parseInt(todayRegistrations.rows[0].count),
                failed_logins_24h: parseInt(failedLogins.rows[0].count)
            },
            oauth: {
                connected_apps: parseInt(connectedApps.rows[0].count),
                pending_codes: parseInt(oauthCodes.rows[0].count)
            },
            registrations_chart: recentRegs.rows,
            server: {
                uptime: process.uptime(),
                memory: process.memoryUsage(),
                node_version: process.version,
                timestamp: new Date().toISOString()
            }
        });
    } catch (err) {
        console.error('Admin system error:', err);
        res.status(500).json({ error: { code: 'server_error', message: 'Internal server error', status: 500 } });
    }
});

// ===== OPENID CONNECT DISCOVERY =====
app.get('/.well-known/openid-configuration', (req, res) => {
    const issuer = 'https://tokenpay.space';
    res.json({
        issuer,
        authorization_endpoint: `${issuer}/api/v1/oauth/authorize`,
        token_endpoint: `${issuer}/api/v1/oauth/token`,
        userinfo_endpoint: `${issuer}/api/v1/oauth/userinfo`,
        revocation_endpoint: `${issuer}/api/v1/oauth/revoke`,
        cancel_endpoint: `${issuer}/api/v1/oauth/cancel`,
        deny_endpoint: `${issuer}/api/v1/oauth/deny`,
        branding_endpoint: `${issuer}/api/v1/oauth/branding`,
        response_types_supported: ['code'],
        prompt_values_supported: ['login', 'consent', 'none'],
        grant_types_supported: ['authorization_code', 'refresh_token'],
        subject_types_supported: ['public'],
        id_token_signing_alg_values_supported: ['HS256'],
        scopes_supported: ['openid', 'profile', 'email'],
        token_endpoint_auth_methods_supported: ['client_secret_post', 'client_secret_basic', 'none'],
        code_challenge_methods_supported: ['S256', 'plain'],
        claims_supported: ['sub', 'email', 'name', 'email_verified', 'locale', 'role', 'iat', 'exp']
    });
});

// ===== FULL OAUTH 2.0 AUTHORIZATION CODE FLOW (+ PKCE) =====

// GET /api/v1/oauth/authorize — redirect user to consent screen
app.get('/api/v1/oauth/authorize', async (req, res) => {
    try {
        const { client_id, redirect_uri, response_type, scope, state, code_challenge, code_challenge_method, prompt, login_hint } = req.query;
        if (response_type !== 'code') {
            return res.status(400).json({ error: { code: 'unsupported_response_type', message: 'Only response_type=code is supported', status: 400 } });
        }
        if (!client_id || !redirect_uri) {
            return res.status(400).json({ error: { code: 'missing_params', message: 'client_id and redirect_uri are required', status: 400 } });
        }
        const keyResult = await pool.query(
            'SELECT k.*, u.name as owner_name, u.company_name as owner_company, u.callback_url, u.allowed_redirect_uris FROM api_keys k JOIN users u ON k.user_id = u.id WHERE k.public_key = $1 AND k.status = $2',
            [client_id, 'active']
        );
        if (keyResult.rows.length === 0) {
            return res.status(400).json({ error: { code: 'invalid_client', message: 'Unknown client_id', status: 400 } });
        }
        const ent = keyResult.rows[0];
        // Validate redirect_uri against allowed list (if configured)
        const allowedUris = ent.allowed_redirect_uris
            ? ent.allowed_redirect_uris.split('\n').map(s => s.trim()).filter(Boolean)
            : (ent.callback_url ? [ent.callback_url] : []);
        if (allowedUris.length > 0 && !allowedUris.includes(redirect_uri)) {
            return res.status(400).json({ error: { code: 'invalid_redirect_uri', message: 'redirect_uri not in allowed list', status: 400 } });
        }
        // Redirect to consent page with params (PKCE forwarded for popup postMessage)
        // Use app_name from api_keys (OAuth branding), fallback to key name
        const displayAppName = ent.app_name || ent.name;
        const displayOwner = ent.owner_company || ent.owner_name;
        const consentParams = {
            client_id, redirect_uri, scope: scope || 'profile', state: state || '',
            app_name: displayAppName, owner_name: displayOwner
        };
        if (ent.app_icon_url) consentParams.app_icon = ent.app_icon_url;
        if (ent.app_description) consentParams.app_desc = ent.app_description;
        if (code_challenge) { consentParams.code_challenge = code_challenge; consentParams.code_challenge_method = code_challenge_method || 'S256'; }
        if (prompt) consentParams.prompt = prompt;
        if (login_hint) consentParams.login_hint = login_hint;
        res.redirect(`/oauth-consent.html?${new URLSearchParams(consentParams).toString()}`);
    } catch (err) {
        res.status(500).json({ error: { code: 'server_error', message: 'Internal server error', status: 500 } });
    }
});

// POST /api/v1/oauth/approve — user approves, generate auth code (PKCE supported)
app.post('/api/v1/oauth/approve', authMiddleware, async (req, res) => {
    try {
        const { client_id, redirect_uri, scope, state, code_challenge, code_challenge_method } = req.body;
        if (!client_id || !redirect_uri) {
            return res.status(400).json({ error: { code: 'missing_params', message: 'client_id and redirect_uri required', status: 400 } });
        }
        const keyResult = await pool.query(
            'SELECT k.*, u.callback_url, u.allowed_redirect_uris FROM api_keys k JOIN users u ON k.user_id = u.id WHERE k.public_key = $1 AND k.status = $2', [client_id, 'active']
        );
        if (keyResult.rows.length === 0) {
            return res.status(400).json({ error: { code: 'invalid_client', message: 'Invalid client_id', status: 400 } });
        }
        // Re-validate redirect_uri (prevent tampering)
        const ent = keyResult.rows[0];
        const allowedUris = ent.allowed_redirect_uris
            ? ent.allowed_redirect_uris.split('\n').map(s => s.trim()).filter(Boolean)
            : (ent.callback_url ? [ent.callback_url] : []);
        if (allowedUris.length > 0 && !allowedUris.includes(redirect_uri)) {
            return res.status(400).json({ error: { code: 'invalid_redirect_uri', message: 'redirect_uri not in allowed list', status: 400 } });
        }
        // Generate authorization code (valid 5 min, PKCE optional)
        const code = 'tpid_code_' + uuidv4().replace(/-/g, '');
        await pool.query(
            `INSERT INTO oauth_codes (id, code, user_id, client_id, redirect_uri, scope, code_challenge, code_challenge_method, expires_at, created_at)
             VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW() + INTERVAL '5 minutes', NOW())`,
            [uuidv4(), code, req.user.id, client_id, redirect_uri, scope || 'profile', code_challenge || null, code_challenge_method || null]
        );
        await pool.query(
            `INSERT INTO activity_log (id, user_id, type, title, status, ip, created_at)
             VALUES ($1, $2, $3, $4, $5, $6, NOW())`,
            [uuidv4(), req.user.id, 'oauth_approve', 'OAuth авторизация одобрена', 'success', req.ip]
        );
        // Track connected app (insert or update last_used)
        const entKeyRow = await pool.query('SELECT user_id, name, app_name FROM api_keys WHERE public_key = $1 AND status = $2', [client_id, 'active']);
        if (entKeyRow.rows.length > 0) {
            const entId = entKeyRow.rows[0].user_id;
            const appName = entKeyRow.rows[0].app_name || entKeyRow.rows[0].name;
            const existingConn = await pool.query('SELECT id FROM connected_apps WHERE user_id = $1 AND enterprise_id = $2', [req.user.id, entId]);
            if (existingConn.rows.length > 0) {
                await pool.query('UPDATE connected_apps SET last_used = NOW(), scopes = $1, app_name = $2 WHERE id = $3',
                    [scope || 'profile', appName, existingConn.rows[0].id]).catch(() => {});
            } else {
                await pool.query(`INSERT INTO connected_apps (id, user_id, enterprise_id, app_name, scopes, authorized_at, last_used) VALUES ($1, $2, $3, $4, $5, NOW(), NOW())`,
                    [uuidv4(), req.user.id, entId, appName, scope || 'profile']).catch(() => {});
            }
            fireWebhook(entId, 'user.oauth_connect', {
                user_id: req.user.id, email: req.user.email, name: req.user.name,
                scope: scope || 'profile', client_id, timestamp: new Date().toISOString()
            });
        }
        const redirectUrl = new URL(redirect_uri);
        redirectUrl.searchParams.set('code', code);
        if (state) redirectUrl.searchParams.set('state', state);
        res.json({ redirect_url: redirectUrl.toString(), code });
    } catch (err) {
        console.error('OAuth approve error:', err);
        res.status(500).json({ error: { code: 'server_error', message: 'Internal server error', status: 500 } });
    }
});

// POST /api/v1/oauth/token — exchange auth code or refresh token (PKCE supported)
app.post('/api/v1/oauth/token', async (req, res) => {
    try {
        const { grant_type, code, client_id, client_secret, redirect_uri, code_verifier, refresh_token: rt } = req.body;

        // Handle refresh_token grant
        if (grant_type === 'refresh_token') {
            if (!rt) return res.status(400).json({ error: { code: 'missing_token', message: 'refresh_token required', status: 400 } });
            try {
                const decoded = jwt.verify(rt, JWT_REFRESH_SECRET);
                const userResult = await pool.query('SELECT id FROM users WHERE id = $1', [decoded.userId]);
                if (userResult.rows.length === 0) return res.status(401).json({ error: { code: 'user_not_found', message: 'User not found', status: 401 } });
                const tokens = generateTokens(decoded.userId);
                return res.json({ access_token: tokens.accessToken, refresh_token: tokens.refreshToken, token_type: 'Bearer', expires_in: tokens.expiresIn });
            } catch (e) {
                return res.status(401).json({ error: { code: 'invalid_token', message: 'Invalid or expired refresh token', status: 401 } });
            }
        }

        if (grant_type !== 'authorization_code') {
            return res.status(400).json({ error: { code: 'unsupported_grant', message: 'Supported: authorization_code, refresh_token', status: 400 } });
        }
        if (!code || !client_id) {
            return res.status(400).json({ error: { code: 'missing_params', message: 'code and client_id required', status: 400 } });
        }
        // Verify client — PKCE flows may omit client_secret
        if (client_secret) {
            const keyResult = await pool.query(
                'SELECT * FROM api_keys WHERE public_key = $1 AND secret_key = $2 AND status = $3',
                [client_id, client_secret, 'active']
            );
            if (keyResult.rows.length === 0) {
                return res.status(401).json({ error: { code: 'invalid_client', message: 'Invalid client credentials', status: 401 } });
            }
        } else {
            const keyResult = await pool.query(
                'SELECT * FROM api_keys WHERE public_key = $1 AND status = $2',
                [client_id, 'active']
            );
            if (keyResult.rows.length === 0) {
                return res.status(401).json({ error: { code: 'invalid_client', message: 'Unknown client_id', status: 401 } });
            }
        }
        // Verify code
        const codeResult = await pool.query(
            'SELECT * FROM oauth_codes WHERE code = $1 AND client_id = $2 AND used = FALSE AND expires_at > NOW()',
            [code, client_id]
        );
        if (codeResult.rows.length === 0) {
            return res.status(400).json({ error: { code: 'invalid_code', message: 'Invalid or expired authorization code', status: 400 } });
        }
        const oauthCode = codeResult.rows[0];
        if (redirect_uri && oauthCode.redirect_uri !== redirect_uri) {
            return res.status(400).json({ error: { code: 'redirect_mismatch', message: 'redirect_uri mismatch', status: 400 } });
        }
        // PKCE verification
        if (oauthCode.code_challenge) {
            if (!code_verifier) {
                return res.status(400).json({ error: { code: 'missing_code_verifier', message: 'code_verifier required for PKCE flow', status: 400 } });
            }
            let computed;
            if (oauthCode.code_challenge_method === 'S256') {
                computed = crypto.createHash('sha256').update(code_verifier).digest('base64url');
            } else {
                computed = code_verifier;
            }
            if (computed !== oauthCode.code_challenge) {
                return res.status(400).json({ error: { code: 'invalid_code_verifier', message: 'PKCE verification failed', status: 400 } });
            }
        }
        // Mark code as used
        await pool.query('UPDATE oauth_codes SET used = TRUE WHERE id = $1', [oauthCode.id]);
        // Update api_keys last_used
        await pool.query('UPDATE api_keys SET last_used = NOW() WHERE public_key = $1', [client_id]);
        // Generate tokens for the user
        const tokens = generateTokens(oauthCode.user_id);
        res.json({
            access_token: tokens.accessToken,
            refresh_token: tokens.refreshToken,
            token_type: 'Bearer',
            expires_in: tokens.expiresIn,
            scope: oauthCode.scope,
            user_id: oauthCode.user_id
        });
    } catch (err) {
        console.error('OAuth token error:', err);
        res.status(500).json({ error: { code: 'server_error', message: 'Internal server error', status: 500 } });
    }
});

// GET /api/v1/oauth/userinfo — get user info with OAuth token
app.get('/api/v1/oauth/userinfo', authMiddleware, (req, res) => {
    const u = req.user;
    res.json({
        id: u.id, email: u.email, name: u.name,
        role: u.role,
        email_verified: u.email_verified,
        locale: u.locale || 'ru',
        theme: u.theme || 'dark',
        telegram_id: u.telegram_id || null,
        telegram_linked: !!u.telegram_linked,
        cupol_balance: u.cupol_balance || 0,
        cupol_subscription_end: u.cupol_subscription_end || null,
        cupol_subscription_active: u.cupol_subscription_active || false,
        cupol_username: u.cupol_username || null,
        created_at: u.created_at
    });
});

// POST /api/v1/internal/cupol-sync — CUPOL pushes balance/subscription data (API key auth)
app.post('/api/v1/internal/cupol-sync', authMiddleware, async (req, res) => {
    try {
        // Only admin/enterprise API keys can call this
        if (req.user.role !== 'admin' && req.user.role !== 'enterprise') {
            return res.status(403).json({ error: { code: 'forbidden', message: 'Admin or enterprise access required', status: 403 } });
        }
        const { telegram_id, balance, subscription_end, subscription_active, username } = req.body;
        if (!telegram_id) {
            return res.status(400).json({ error: { code: 'missing_fields', message: 'telegram_id is required', status: 400 } });
        }
        // Find user by telegram_id
        const userResult = await pool.query('SELECT id FROM users WHERE telegram_id = $1', [telegram_id]);
        if (userResult.rows.length === 0) {
            return res.status(404).json({ error: { code: 'not_found', message: 'No TPID user linked to this telegram_id', status: 404 } });
        }
        const userId = userResult.rows[0].id;
        const updates = [];
        const params = [];
        let idx = 1;
        if (balance !== undefined) { updates.push(`cupol_balance = $${idx++}`); params.push(balance); }
        if (subscription_end !== undefined) { updates.push(`cupol_subscription_end = $${idx++}`); params.push(subscription_end); }
        if (subscription_active !== undefined) { updates.push(`cupol_subscription_active = $${idx++}`); params.push(!!subscription_active); }
        if (username !== undefined) { updates.push(`cupol_username = $${idx++}`); params.push(username); }
        updates.push(`cupol_synced_at = NOW()`);
        if (updates.length > 1) {
            params.push(userId);
            await pool.query(`UPDATE users SET ${updates.join(', ')} WHERE id = $${idx}`, params);
        }
        res.json({ success: true, user_id: userId });
    } catch (err) {
        console.error('CUPOL sync error:', err);
        res.status(500).json({ error: { code: 'server_error', message: 'Internal server error', status: 500 } });
    }
});

// GET /api/v1/internal/cupol-data — CUPOL pulls TPID profile for a telegram_id (API key auth)
app.get('/api/v1/internal/cupol-data', authMiddleware, async (req, res) => {
    try {
        if (req.user.role !== 'admin' && req.user.role !== 'enterprise') {
            return res.status(403).json({ error: { code: 'forbidden', message: 'Admin or enterprise access required', status: 403 } });
        }
        const telegram_id = req.query.telegram_id;
        if (!telegram_id) {
            return res.status(400).json({ error: { code: 'missing_fields', message: 'telegram_id query param required', status: 400 } });
        }
        const result = await pool.query('SELECT id, email, name, email_verified, created_at FROM users WHERE telegram_id = $1', [telegram_id]);
        if (result.rows.length === 0) {
            return res.json({ linked: false });
        }
        const u = result.rows[0];
        res.json({ linked: true, tpid_user_id: u.id, email: u.email, name: u.name, email_verified: u.email_verified, created_at: u.created_at });
    } catch (err) {
        console.error('CUPOL data error:', err);
        res.status(500).json({ error: { code: 'server_error', message: 'Internal server error', status: 500 } });
    }
});

// Token blacklist (in-memory, cleared on restart — acceptable for OAuth revocation)
const tokenBlacklist = new Set();
setInterval(() => {
    // Clean blacklist entries older than 2h (tokens expire in 1h anyway)
    // We store expiry timestamps, so just clear periodically
    if (tokenBlacklist.size > 10000) tokenBlacklist.clear();
}, 3600000);

// POST /api/v1/oauth/revoke — revoke an OAuth token
app.post('/api/v1/oauth/revoke', async (req, res) => {
    try {
        const { token } = req.body;
        if (!token) return res.status(400).json({ error: { code: 'missing_token', message: 'Token required', status: 400 } });
        try {
            const decoded = jwt.verify(token, JWT_SECRET);
            tokenBlacklist.add(token);
        } catch (e) {
            // Token already expired or invalid — that's fine
        }
        res.json({ success: true });
    } catch (err) {
        res.status(500).json({ error: { code: 'server_error', message: 'Internal server error', status: 500 } });
    }
});

// GET /api/v1/oauth/branding — returns button configs, CSS snippet, and integration code for enterprises
app.get('/api/v1/oauth/branding', async (req, res) => {
    try {
        const { client_id } = req.query;
        const issuer = `https://${req.get('host') || 'tokenpay.space'}`;

        // If client_id provided, return app-specific branding
        let appBranding = null;
        if (client_id) {
            const keyResult = await pool.query(
                `SELECT k.app_name, k.name, k.app_icon_url, k.app_description,
                        u.name as owner_name, u.company_name as owner_company
                 FROM api_keys k JOIN users u ON k.user_id = u.id
                 WHERE k.public_key = $1 AND k.status = $2`,
                [client_id, 'active']
            );
            if (keyResult.rows.length > 0) {
                const ent = keyResult.rows[0];
                appBranding = {
                    app_name: ent.app_name || ent.name,
                    owner: ent.owner_company || ent.owner_name,
                    icon_url: ent.app_icon_url || null,
                    description: ent.app_description || null
                };
            }
        }

        res.json({
            provider: 'TOKEN PAY ID',
            version: '2.1.0',
            widget_url: `${issuer}/sdk/tpid-widget.js`,
            widget_version: '1.2.0',
            authorize_url: `${issuer}/api/v1/oauth/authorize`,
            token_url: `${issuer}/api/v1/oauth/token`,
            icon: {
                shield_svg: '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M12 2L3 7v5c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V7l-9-5z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/><path d="M9.5 12.5l2 2 3.5-4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>',
                logo_dark_url: `${issuer}/tokenpay-id-light.png`,
                logo_light_url: `${issuer}/tokenpay-id-dark.png`,
                icon_url: `${issuer}/tokenpay-icon.png`
            },
            buttons: {
                standard: {
                    description: 'Full "Sign in with TOKEN PAY ID" button',
                    html: `<div data-tpid-button="standard"></div>`,
                    api: 'TPID.renderButton("#container")'
                },
                icon: {
                    description: 'Round icon-only button (for navbars)',
                    html: `<div data-tpid-button="icon"></div>`,
                    html_sizes: {
                        sm: '<div data-tpid-button="icon" data-tpid-size="sm"></div>',
                        md: '<div data-tpid-button="icon" data-tpid-size="md"></div>',
                        lg: '<div data-tpid-button="icon" data-tpid-size="lg"></div>'
                    },
                    api: 'TPID.renderIconButton("#container", { size: "md" })'
                },
                logo: {
                    description: 'Transparent logo button (TOKEN PAY ID text)',
                    html: `<div data-tpid-button="logo"></div>`,
                    api: 'TPID.renderLogoButton("#container")'
                }
            },
            integration: {
                quick_start: `<!-- Add to your HTML -->\n<script src="${issuer}/sdk/tpid-widget.js" data-client-id="YOUR_CLIENT_ID"><\/script>\n\n<!-- Buttons appear automatically in these containers -->\n<div data-tpid-button="standard"></div>\n<div data-tpid-button="icon"></div>\n<div data-tpid-button="logo"></div>`,
                oauth_popup: `// OAuth popup flow (returns Promise)\nconst result = await TPID.loginWithOAuth({\n  clientId: 'YOUR_CLIENT_ID',\n  redirectUri: 'https://yoursite.com/callback',\n  scope: 'profile email'\n});\nconsole.log(result.code); // authorization code`,
                manual_init: `<script src="${issuer}/sdk/tpid-widget.js"><\/script>\n<script>\nTPID.init({\n  clientId: 'YOUR_CLIENT_ID',\n  theme: 'auto',\n  lang: 'ru',\n  onSuccess: function(data) {\n    console.log('User:', data.user);\n    console.log('Token:', data.accessToken);\n  }\n});\n<\/script>`
            },
            themes: ['dark', 'light', 'auto'],
            languages: ['ru', 'en'],
            app: appBranding
        });
    } catch (err) {
        console.error('Branding error:', err);
        res.status(500).json({ error: { code: 'server_error', message: 'Internal server error', status: 500 } });
    }
});

// POST /api/v1/oauth/cancel — enterprise notifies that user closed/cancelled OAuth flow
app.post('/api/v1/oauth/cancel', async (req, res) => {
    try {
        const { client_id, state, reason } = req.body;
        if (!client_id) {
            return res.status(400).json({ error: { code: 'missing_params', message: 'client_id is required', status: 400 } });
        }
        // Find enterprise by client_id (public_key)
        const keyResult = await pool.query(
            'SELECT k.user_id, k.name, k.app_name FROM api_keys k WHERE k.public_key = $1 AND k.status = $2',
            [client_id, 'active']
        );
        if (keyResult.rows.length === 0) {
            return res.status(400).json({ error: { code: 'invalid_client', message: 'Unknown client_id', status: 400 } });
        }
        const ent = keyResult.rows[0];
        // Invalidate any pending oauth codes for this client_id + state
        if (state) {
            await pool.query(
                "UPDATE oauth_codes SET used = TRUE WHERE client_id = $1 AND used = FALSE AND expires_at > NOW()",
                [client_id]
            ).catch(() => {});
        }
        // Fire webhook to enterprise
        fireWebhook(ent.user_id, 'oauth.cancelled', {
            client_id,
            state: state || null,
            reason: reason || 'user_closed',
            timestamp: new Date().toISOString()
        });
        // Log
        await pool.query(
            `INSERT INTO activity_log (id, user_id, type, title, status, ip, created_at) VALUES ($1, $2, $3, $4, $5, $6, NOW())`,
            [uuidv4(), ent.user_id, 'oauth_cancelled', `OAuth отменён пользователем (${ent.app_name || ent.name})`, 'info', req.ip]
        ).catch(() => {});
        res.json({ success: true });
    } catch (err) {
        console.error('OAuth cancel error:', err);
        res.status(500).json({ error: { code: 'server_error', message: 'Internal server error', status: 500 } });
    }
});

// POST /api/v1/oauth/deny — consent page calls this when user explicitly denies
app.post('/api/v1/oauth/deny', async (req, res) => {
    try {
        const { client_id, state } = req.body;
        if (!client_id) {
            return res.status(400).json({ error: { code: 'missing_params', message: 'client_id is required', status: 400 } });
        }
        const keyResult = await pool.query(
            'SELECT k.user_id, k.name, k.app_name FROM api_keys k WHERE k.public_key = $1 AND k.status = $2',
            [client_id, 'active']
        );
        if (keyResult.rows.length === 0) {
            return res.status(400).json({ error: { code: 'invalid_client', message: 'Unknown client_id', status: 400 } });
        }
        const ent = keyResult.rows[0];
        // Get user info if authenticated
        let userId = null;
        let userEmail = null;
        const auth = req.headers.authorization;
        if (auth && auth.startsWith('Bearer ')) {
            try {
                const decoded = jwt.verify(auth.split(' ')[1], JWT_SECRET);
                const userRow = await pool.query('SELECT id, email FROM users WHERE id = $1', [decoded.userId]);
                if (userRow.rows.length > 0) { userId = userRow.rows[0].id; userEmail = userRow.rows[0].email; }
            } catch (e) { /* token invalid — that's ok, user denied without being logged in */ }
        }
        // Fire webhook to enterprise
        fireWebhook(ent.user_id, 'oauth.denied', {
            client_id,
            state: state || null,
            user_id: userId,
            user_email: userEmail,
            timestamp: new Date().toISOString()
        });
        // Log activity
        if (userId) {
            await pool.query(
                `INSERT INTO activity_log (id, user_id, type, title, status, ip, created_at) VALUES ($1, $2, $3, $4, $5, $6, NOW())`,
                [uuidv4(), userId, 'oauth_denied', `OAuth отклонён для ${ent.app_name || ent.name}`, 'info', req.ip]
            ).catch(() => {});
        }
        res.json({ success: true });
    } catch (err) {
        console.error('OAuth deny error:', err);
        res.status(500).json({ error: { code: 'server_error', message: 'Internal server error', status: 500 } });
    }
});

// ===== GENERIC ENTERPRISE DATA SYNC (replaces CUPOL-specific endpoints) =====

// POST /api/v1/enterprise/sync-user — any enterprise pushes user metadata (API key auth)
app.post('/api/v1/enterprise/sync-user', authMiddleware, async (req, res) => {
    try {
        if (req.user.role !== 'admin' && req.user.role !== 'enterprise') {
            return res.status(403).json({ error: { code: 'forbidden', message: 'Enterprise access required', status: 403 } });
        }
        const { telegram_id, user_id, metadata } = req.body;
        if (!telegram_id && !user_id) {
            return res.status(400).json({ error: { code: 'missing_fields', message: 'telegram_id or user_id is required', status: 400 } });
        }
        // Find TPID user
        let userResult;
        if (user_id) {
            userResult = await pool.query('SELECT id FROM users WHERE id = $1', [user_id]);
        } else {
            userResult = await pool.query('SELECT id FROM users WHERE telegram_id = $1', [telegram_id]);
        }
        if (userResult.rows.length === 0) {
            return res.status(404).json({ error: { code: 'not_found', message: 'No TPID user found', status: 404 } });
        }
        const tpidUserId = userResult.rows[0].id;
        // Update connected_apps metadata
        if (metadata && typeof metadata === 'object') {
            const existingConn = await pool.query(
                'SELECT id FROM connected_apps WHERE user_id = $1 AND enterprise_id = $2',
                [tpidUserId, req.user.id]
            );
            if (existingConn.rows.length > 0) {
                await pool.query(
                    'UPDATE connected_apps SET last_used = NOW() WHERE id = $1',
                    [existingConn.rows[0].id]
                );
            }
        }
        // Also support legacy CUPOL-specific fields for backward compatibility
        const { balance, subscription_end, subscription_active, username } = req.body;
        const updates = []; const params = []; let idx = 1;
        if (balance !== undefined) { updates.push(`cupol_balance = $${idx++}`); params.push(balance); }
        if (subscription_end !== undefined) { updates.push(`cupol_subscription_end = $${idx++}`); params.push(subscription_end); }
        if (subscription_active !== undefined) { updates.push(`cupol_subscription_active = $${idx++}`); params.push(!!subscription_active); }
        if (username !== undefined) { updates.push(`cupol_username = $${idx++}`); params.push(username); }
        if (updates.length > 0) {
            updates.push(`cupol_synced_at = NOW()`);
            params.push(tpidUserId);
            await pool.query(`UPDATE users SET ${updates.join(', ')} WHERE id = $${idx}`, params);
        }
        res.json({ success: true, user_id: tpidUserId });
    } catch (err) {
        console.error('Enterprise sync-user error:', err);
        res.status(500).json({ error: { code: 'server_error', message: 'Internal server error', status: 500 } });
    }
});

// GET /api/v1/enterprise/user-data — any enterprise pulls TPID user profile (API key auth)
app.get('/api/v1/enterprise/user-data', authMiddleware, async (req, res) => {
    try {
        if (req.user.role !== 'admin' && req.user.role !== 'enterprise') {
            return res.status(403).json({ error: { code: 'forbidden', message: 'Enterprise access required', status: 403 } });
        }
        const { telegram_id, user_id } = req.query;
        if (!telegram_id && !user_id) {
            return res.status(400).json({ error: { code: 'missing_fields', message: 'telegram_id or user_id query param required', status: 400 } });
        }
        let result;
        if (user_id) {
            result = await pool.query('SELECT id, email, name, email_verified, locale, theme, created_at FROM users WHERE id = $1', [user_id]);
        } else {
            result = await pool.query('SELECT id, email, name, email_verified, locale, theme, created_at FROM users WHERE telegram_id = $1', [telegram_id]);
        }
        if (result.rows.length === 0) {
            return res.json({ linked: false });
        }
        const u = result.rows[0];
        res.json({ linked: true, tpid_user_id: u.id, email: u.email, name: u.name, email_verified: u.email_verified, locale: u.locale, theme: u.theme, created_at: u.created_at });
    } catch (err) {
        console.error('Enterprise user-data error:', err);
        res.status(500).json({ error: { code: 'server_error', message: 'Internal server error', status: 500 } });
    }
});

// ===== SDK VERSION ENDPOINT =====
app.get('/api/v1/sdk/version', (req, res) => {
    res.json({
        widget: '1.2.0',
        api: '2.1.0',
        widget_url: 'https://tokenpay.space/sdk/tpid-widget.js',
        changelog_url: 'https://tokenpay.space/docs#changelog',
        breaking_changes: false
    });
});

// ===== DB INIT + ADMIN SEED =====
async function initDB() {
    const client = await pool.connect();
    try {
        await client.query(`
            CREATE TABLE IF NOT EXISTS users (
                id VARCHAR(64) PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                name VARCHAR(255) NOT NULL,
                role VARCHAR(20) DEFAULT 'user',
                email_verified BOOLEAN DEFAULT FALSE,
                two_factor_enabled BOOLEAN DEFAULT FALSE,
                telegram_linked BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW(),
                last_login TIMESTAMP DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS api_keys (
                id VARCHAR(64) PRIMARY KEY,
                user_id VARCHAR(64) REFERENCES users(id),
                name VARCHAR(255) NOT NULL,
                public_key VARCHAR(255) UNIQUE NOT NULL,
                secret_key VARCHAR(255) UNIQUE NOT NULL,
                status VARCHAR(20) DEFAULT 'active',
                created_at TIMESTAMP DEFAULT NOW(),
                last_used TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS sessions (
                id VARCHAR(64) PRIMARY KEY,
                user_id VARCHAR(64) REFERENCES users(id),
                device VARCHAR(255),
                ip VARCHAR(100),
                last_active TIMESTAMP DEFAULT NOW(),
                created_at TIMESTAMP DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS activity_log (
                id VARCHAR(64) PRIMARY KEY,
                user_id VARCHAR(64) REFERENCES users(id),
                type VARCHAR(100),
                title VARCHAR(500),
                status VARCHAR(20),
                ip VARCHAR(100),
                created_at TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_api_keys_user ON api_keys(user_id);
            CREATE INDEX IF NOT EXISTS idx_api_keys_secret ON api_keys(secret_key);
            CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
            CREATE INDEX IF NOT EXISTS idx_activity_user ON activity_log(user_id);
            CREATE INDEX IF NOT EXISTS idx_activity_created ON activity_log(created_at);

            CREATE TABLE IF NOT EXISTS oauth_codes (
                id VARCHAR(64) PRIMARY KEY,
                code VARCHAR(255) UNIQUE NOT NULL,
                user_id VARCHAR(64) REFERENCES users(id),
                client_id VARCHAR(255) NOT NULL,
                redirect_uri TEXT NOT NULL,
                scope VARCHAR(255) DEFAULT 'profile',
                used BOOLEAN DEFAULT FALSE,
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_oauth_codes_code ON oauth_codes(code);
        `);

        // DB migrations: add new columns if missing
        await client.query(`ALTER TABLE users ADD COLUMN IF NOT EXISTS totp_secret VARCHAR(64) DEFAULT NULL`);
        await client.query(`ALTER TABLE users ADD COLUMN IF NOT EXISTS verification_token VARCHAR(128) DEFAULT NULL`);
        await client.query(`ALTER TABLE users ADD COLUMN IF NOT EXISTS verification_expires TIMESTAMP DEFAULT NULL`);
        await client.query(`CREATE INDEX IF NOT EXISTS idx_users_verification ON users(verification_token)`);

        // Enterprise columns
        await client.query(`ALTER TABLE users ADD COLUMN IF NOT EXISTS company_name VARCHAR(255) DEFAULT NULL`);
        await client.query(`ALTER TABLE users ADD COLUMN IF NOT EXISTS website VARCHAR(255) DEFAULT NULL`);
        await client.query(`ALTER TABLE users ADD COLUMN IF NOT EXISTS description TEXT DEFAULT NULL`);
        await client.query(`ALTER TABLE users ADD COLUMN IF NOT EXISTS locale VARCHAR(5) DEFAULT 'ru'`);

        // Email verification codes
        await client.query(`
            CREATE TABLE IF NOT EXISTS email_codes (
                id VARCHAR(64) PRIMARY KEY,
                email VARCHAR(255) NOT NULL,
                code VARCHAR(6) NOT NULL,
                type VARCHAR(20) NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                used BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_email_codes_email ON email_codes(email);
            CREATE INDEX IF NOT EXISTS idx_email_codes_expires ON email_codes(expires_at);
        `);
        // Fix any NULL used values from older inserts
        await client.query(`UPDATE email_codes SET used = FALSE WHERE used IS NULL`);
        await client.query(`ALTER TABLE email_codes ALTER COLUMN used SET NOT NULL`).catch(() => {});
        await client.query(`ALTER TABLE email_codes ALTER COLUMN used SET DEFAULT FALSE`).catch(() => {});

        // Enterprise applications (users apply, admin approves/rejects)
        await client.query(`
            CREATE TABLE IF NOT EXISTS enterprise_applications (
                id VARCHAR(64) PRIMARY KEY,
                user_id VARCHAR(64) REFERENCES users(id),
                company_name VARCHAR(255) NOT NULL,
                website VARCHAR(255),
                inn VARCHAR(20),
                description TEXT,
                status VARCHAR(20) DEFAULT 'pending',
                reviewed_by VARCHAR(64),
                review_note TEXT,
                reviewed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_ent_app_user ON enterprise_applications(user_id);
            CREATE INDEX IF NOT EXISTS idx_ent_app_status ON enterprise_applications(status);
        `);

        // PKCE support for OAuth
        await client.query(`ALTER TABLE oauth_codes ADD COLUMN IF NOT EXISTS code_challenge VARCHAR(128) DEFAULT NULL`);
        await client.query(`ALTER TABLE oauth_codes ADD COLUMN IF NOT EXISTS code_challenge_method VARCHAR(10) DEFAULT NULL`);

        // Theme preference
        await client.query(`ALTER TABLE users ADD COLUMN IF NOT EXISTS theme VARCHAR(10) DEFAULT 'dark'`);
        // Enterprise callback URL
        await client.query(`ALTER TABLE users ADD COLUMN IF NOT EXISTS callback_url VARCHAR(500) DEFAULT NULL`);

        // API key expiry support
        await client.query(`ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP DEFAULT NULL`);

        // OAuth app branding on API keys (so consent page shows proper app name/icon)
        await client.query(`ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS app_name VARCHAR(255) DEFAULT NULL`);
        await client.query(`ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS app_icon_url VARCHAR(500) DEFAULT NULL`);
        await client.query(`ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS app_description TEXT DEFAULT NULL`);

        // Connected apps tracking (when user authorizes via OAuth on enterprise sites)
        await client.query(`
            CREATE TABLE IF NOT EXISTS connected_apps (
                id VARCHAR(64) PRIMARY KEY,
                user_id VARCHAR(64) REFERENCES users(id),
                enterprise_id VARCHAR(64) REFERENCES users(id),
                app_name VARCHAR(255),
                scopes VARCHAR(255) DEFAULT 'profile',
                authorized_at TIMESTAMP DEFAULT NOW(),
                last_used TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_connected_apps_user ON connected_apps(user_id);
            CREATE INDEX IF NOT EXISTS idx_connected_apps_enterprise ON connected_apps(enterprise_id);
        `);

        // Telegram integration: telegram_id column for CUPOL VPN linking
        await client.query(`ALTER TABLE users ADD COLUMN IF NOT EXISTS telegram_id BIGINT DEFAULT NULL`);
        await client.query(`CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id)`);

        // CUPOL VPN sync columns
        await client.query(`ALTER TABLE users ADD COLUMN IF NOT EXISTS cupol_balance INTEGER DEFAULT 0`);
        await client.query(`ALTER TABLE users ADD COLUMN IF NOT EXISTS cupol_subscription_end TIMESTAMP DEFAULT NULL`);
        await client.query(`ALTER TABLE users ADD COLUMN IF NOT EXISTS cupol_subscription_active BOOLEAN DEFAULT FALSE`);
        await client.query(`ALTER TABLE users ADD COLUMN IF NOT EXISTS cupol_username VARCHAR(255) DEFAULT NULL`);
        await client.query(`ALTER TABLE users ADD COLUMN IF NOT EXISTS cupol_synced_at TIMESTAMP DEFAULT NULL`);

        // Webhook system for enterprise
        await client.query(`ALTER TABLE users ADD COLUMN IF NOT EXISTS webhook_url VARCHAR(500) DEFAULT NULL`);
        await client.query(`ALTER TABLE users ADD COLUMN IF NOT EXISTS webhook_secret VARCHAR(64) DEFAULT NULL`);
        await client.query(`ALTER TABLE users ADD COLUMN IF NOT EXISTS allowed_redirect_uris TEXT DEFAULT NULL`);
        await client.query(`
            CREATE TABLE IF NOT EXISTS webhook_deliveries (
                id VARCHAR(64) PRIMARY KEY,
                enterprise_id VARCHAR(64) REFERENCES users(id) ON DELETE CASCADE,
                event VARCHAR(100) NOT NULL,
                status_code INTEGER DEFAULT 0,
                duration_ms INTEGER DEFAULT 0,
                error TEXT,
                delivered_at TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_webhook_del_enterprise ON webhook_deliveries(enterprise_id);
            CREATE INDEX IF NOT EXISTS idx_webhook_del_delivered ON webhook_deliveries(delivered_at);
        `);

        // Seed admin
        const adminExists = await client.query('SELECT id FROM users WHERE email = $1', [ADMIN_EMAIL]);
        if (adminExists.rows.length === 0) {
            const adminId = 'tpid_usr_admin_' + uuidv4().replace(/-/g, '').substring(0, 8);
            const adminHash = await bcrypt.hash(ADMIN_PASSWORD, 12);
            await client.query(
                `INSERT INTO users (id, email, password_hash, name, role, email_verified, two_factor_enabled, created_at, last_login)
                 VALUES ($1, $2, $3, $4, $5, $6, $7, NOW(), NOW())`,
                [adminId, ADMIN_EMAIL, adminHash, 'Admin', 'admin', true, false]
            );
            // Admin API key
            const adminPk = 'tpid_pk_admin_' + uuidv4().replace(/-/g, '').substring(0, 12);
            const adminSk = 'tpid_sk_admin_' + uuidv4().replace(/-/g, '') + uuidv4().replace(/-/g, '').substring(0, 8);
            await client.query(
                `INSERT INTO api_keys (id, user_id, name, public_key, secret_key, status, created_at)
                 VALUES ($1, $2, $3, $4, $5, $6, NOW())`,
                [uuidv4(), adminId, 'Admin Master Key', adminPk, adminSk, 'active']
            );
            console.log('[INIT] Admin account created:', ADMIN_EMAIL);
        } else {
            // Always sync admin password from env
            const adminHash = await bcrypt.hash(ADMIN_PASSWORD, 12);
            await client.query('UPDATE users SET password_hash = $1 WHERE email = $2', [adminHash, ADMIN_EMAIL]);
            console.log('[INIT] Admin account exists:', ADMIN_EMAIL, '(password synced)');
            // Auto-fix: rename admin key from 'Admin Master Key' to proper app name
            await client.query(`UPDATE api_keys SET app_name = 'CUPOL VPN', app_description = 'Безопасный VPN-сервис' WHERE name = 'Admin Master Key' AND app_name IS NULL`).catch(() => {});
        }

        console.log('[INIT] Database tables ready');
    } catch (err) {
        console.error('[INIT] Database init error:', err.message);
        // Tables may already exist, that's fine
    } finally {
        client.release();
    }
}

// ===== ENTERPRISE APPLICATION FLOW =====

// User: submit enterprise application
app.post('/api/v1/enterprise/apply', authMiddleware, async (req, res) => {
    try {
        const { company_name, website, inn, description } = req.body;
        if (!company_name) {
            return res.status(400).json({ error: { code: 'missing_fields', message: 'company_name is required', status: 400 } });
        }
        if (req.user.role === 'enterprise') {
            return res.status(400).json({ error: { code: 'already_enterprise', message: 'Account is already enterprise', status: 400 } });
        }
        // Check for existing pending application
        const existing = await pool.query(
            "SELECT id FROM enterprise_applications WHERE user_id = $1 AND status = 'pending'", [req.user.id]
        );
        if (existing.rows.length > 0) {
            return res.status(409).json({ error: { code: 'application_exists', message: 'You already have a pending application', status: 409 } });
        }
        const appId = 'tpid_eapp_' + uuidv4().replace(/-/g, '').substring(0, 12);
        await pool.query(
            `INSERT INTO enterprise_applications (id, user_id, company_name, website, inn, description, status, created_at)
             VALUES ($1, $2, $3, $4, $5, $6, 'pending', NOW())`,
            [appId, req.user.id, sanitize(company_name, 255), sanitize(website || '', 255), sanitize(inn || '', 20), sanitize(description || '', 2000)]
        );
        await pool.query(
            `INSERT INTO activity_log (id, user_id, type, title, status, ip, created_at) VALUES ($1, $2, $3, $4, $5, $6, NOW())`,
            [uuidv4(), req.user.id, 'enterprise_apply', `Заявка на корпоративный аккаунт: ${sanitize(company_name, 100)}`, 'info', req.ip]
        );
        res.status(201).json({ id: appId, status: 'pending', message: 'Application submitted for review' });
    } catch (err) {
        console.error('Enterprise apply error:', err);
        res.status(500).json({ error: { code: 'server_error', message: 'Server error', status: 500 } });
    }
});

// User: check own application status
app.get('/api/v1/enterprise/application', authMiddleware, async (req, res) => {
    try {
        const result = await pool.query(
            'SELECT id, company_name, website, inn, description, status, review_note, created_at, reviewed_at FROM enterprise_applications WHERE user_id = $1 ORDER BY created_at DESC LIMIT 1',
            [req.user.id]
        );
        if (result.rows.length === 0) return res.json({ application: null });
        res.json({ application: result.rows[0] });
    } catch (err) {
        res.status(500).json({ error: { code: 'server_error', message: 'Server error', status: 500 } });
    }
});

// Admin: list enterprise applications
app.get('/api/v1/admin/enterprise/applications', authMiddleware, adminMiddleware, async (req, res) => {
    try {
        const status = req.query.status || 'pending';
        const limit = Math.min(parseInt(req.query.limit) || 50, 200);
        const offset = parseInt(req.query.offset) || 0;
        const result = await pool.query(
            `SELECT ea.*, u.email, u.name as user_name, u.created_at as user_created
             FROM enterprise_applications ea
             JOIN users u ON ea.user_id = u.id
             WHERE ea.status = $1
             ORDER BY ea.created_at DESC LIMIT $2 OFFSET $3`,
            [status, limit, offset]
        );
        const countResult = await pool.query('SELECT COUNT(*) FROM enterprise_applications WHERE status = $1', [status]);
        res.json({ applications: result.rows, total: parseInt(countResult.rows[0].count) });
    } catch (err) {
        res.status(500).json({ error: { code: 'server_error', message: 'Server error', status: 500 } });
    }
});

// Admin: approve or reject enterprise application
app.put('/api/v1/admin/enterprise/applications/:id', authMiddleware, adminMiddleware, async (req, res) => {
    try {
        const { action, review_note } = req.body;
        if (!action || !['approve', 'reject'].includes(action)) {
            return res.status(400).json({ error: { code: 'invalid_action', message: 'action must be approve or reject', status: 400 } });
        }
        const appResult = await pool.query(
            "SELECT ea.*, u.email, u.name, u.locale FROM enterprise_applications ea JOIN users u ON ea.user_id = u.id WHERE ea.id = $1 AND ea.status = 'pending'",
            [req.params.id]
        );
        if (appResult.rows.length === 0) {
            return res.status(404).json({ error: { code: 'not_found', message: 'Application not found or already reviewed', status: 404 } });
        }
        const app = appResult.rows[0];
        const newStatus = action === 'approve' ? 'approved' : 'rejected';
        await pool.query(
            'UPDATE enterprise_applications SET status = $1, reviewed_by = $2, review_note = $3, reviewed_at = NOW() WHERE id = $4',
            [newStatus, req.user.id, sanitize(review_note || '', 500), req.params.id]
        );
        const userLang = app.locale || 'ru';
        if (action === 'approve') {
            // Upgrade user to enterprise role
            await pool.query(
                'UPDATE users SET role = $1, company_name = $2, website = $3, description = $4 WHERE id = $5',
                ['enterprise', app.company_name, app.website, app.description, app.user_id]
            );
            // Create production API key
            const pk = 'tpid_pk_' + uuidv4().replace(/-/g, '').substring(0, 16);
            const sk = 'tpid_sk_' + uuidv4().replace(/-/g, '') + uuidv4().replace(/-/g, '').substring(0, 8);
            await pool.query(
                `INSERT INTO api_keys (id, user_id, name, public_key, secret_key, status, created_at) VALUES ($1, $2, $3, $4, $5, 'active', NOW())`,
                [uuidv4(), app.user_id, 'Production Key', pk, sk]
            );
            await pool.query(
                `INSERT INTO activity_log (id, user_id, type, title, status, ip, created_at) VALUES ($1, $2, $3, $4, $5, $6, NOW())`,
                [uuidv4(), app.user_id, 'enterprise_approved', `Корпоративный аккаунт одобрен: ${app.company_name}`, 'success', req.ip]
            );
            const approveSubject = userLang === 'en' ? 'Enterprise Application Approved — TOKEN PAY ID' : 'Заявка одобрена — TOKEN PAY ID';
            sendEmail(app.email, approveSubject, templates.enterpriseApproved(app.name, app.company_name, userLang)).catch(() => {});
            res.json({ success: true, status: 'approved', public_key: pk, secret_key: sk });
        } else {
            await pool.query(
                `INSERT INTO activity_log (id, user_id, type, title, status, ip, created_at) VALUES ($1, $2, $3, $4, $5, $6, NOW())`,
                [uuidv4(), app.user_id, 'enterprise_rejected', `Корпоративная заявка отклонена: ${app.company_name}`, 'warning', req.ip]
            );
            const rejectSubject = userLang === 'en' ? 'Enterprise Application Rejected — TOKEN PAY ID' : 'Заявка отклонена — TOKEN PAY ID';
            sendEmail(app.email, rejectSubject, templates.enterpriseRejected(app.name, app.company_name, review_note, userLang)).catch(() => {});
            res.json({ success: true, status: 'rejected' });
        }
    } catch (err) {
        console.error('Enterprise review error:', err);
        res.status(500).json({ error: { code: 'server_error', message: 'Server error', status: 500 } });
    }
});

// User: get connected apps (where this user has authorized via OAuth)
app.get('/api/v1/users/connected-apps', authMiddleware, async (req, res) => {
    try {
        const result = await pool.query(
            `SELECT ca.id, ca.app_name, ca.scopes, ca.authorized_at, ca.last_used, u.company_name, u.website
             FROM connected_apps ca
             JOIN users u ON ca.enterprise_id = u.id
             WHERE ca.user_id = $1
             ORDER BY ca.last_used DESC`,
            [req.user.id]
        );
        res.json({ apps: result.rows });
    } catch (err) {
        res.status(500).json({ error: { code: 'server_error', message: 'Server error', status: 500 } });
    }
});

// User: revoke connected app
app.delete('/api/v1/users/connected-apps/:id', authMiddleware, async (req, res) => {
    try {
        const appRow = await pool.query('SELECT enterprise_id FROM connected_apps WHERE id = $1 AND user_id = $2', [req.params.id, req.user.id]);
        await pool.query('DELETE FROM connected_apps WHERE id = $1 AND user_id = $2', [req.params.id, req.user.id]);
        if (appRow.rows.length > 0) {
            fireWebhook(appRow.rows[0].enterprise_id, 'user.unlink', {
                user_id: req.user.id, email: req.user.email, timestamp: new Date().toISOString()
            });
        }
        await pool.query(`INSERT INTO activity_log (id, user_id, type, title, status, ip, created_at) VALUES ($1, $2, $3, $4, $5, $6, NOW())`,
            [uuidv4(), req.user.id, 'app_revoked', 'Приложение отвязано', 'success', req.ip]).catch(() => {});
        res.json({ success: true });
    } catch (err) {
        res.status(500).json({ error: { code: 'server_error', message: 'Server error', status: 500 } });
    }
});

// Enterprise: get settings
app.get('/api/v1/enterprise/settings', authMiddleware, async (req, res) => {
    try {
        if (req.user.role !== 'enterprise' && req.user.role !== 'admin') {
            return res.status(403).json({ error: { code: 'forbidden', message: 'Enterprise access required', status: 403 } });
        }
        const r = await pool.query('SELECT callback_url, company_name, website, description, webhook_url, webhook_secret, allowed_redirect_uris FROM users WHERE id = $1', [req.user.id]);
        const u = r.rows[0];
        res.json({
            callback_url: u.callback_url || '',
            company_name: u.company_name || '',
            website: u.website || '',
            description: u.description || '',
            webhook_url: u.webhook_url || '',
            has_webhook_secret: !!(u.webhook_secret),
            allowed_redirect_uris: u.allowed_redirect_uris ? u.allowed_redirect_uris.split('\n').filter(Boolean) : []
        });
    } catch (err) {
        res.status(500).json({ error: { code: 'server_error', message: 'Server error', status: 500 } });
    }
});

// Enterprise: update settings
app.put('/api/v1/enterprise/settings', authMiddleware, async (req, res) => {
    try {
        if (req.user.role !== 'enterprise' && req.user.role !== 'admin') {
            return res.status(403).json({ error: { code: 'forbidden', message: 'Enterprise access required', status: 403 } });
        }
        const { callback_url, company_name, website, description, allowed_redirect_uris } = req.body;
        const updates = []; const params = []; let idx = 1;
        if (callback_url !== undefined) { updates.push(`callback_url = $${idx++}`); params.push(sanitize(callback_url, 500) || null); }
        if (company_name !== undefined) { updates.push(`company_name = $${idx++}`); params.push(sanitize(company_name, 255)); }
        if (website !== undefined) { updates.push(`website = $${idx++}`); params.push(sanitize(website, 255)); }
        if (description !== undefined) { updates.push(`description = $${idx++}`); params.push(sanitize(description, 2000)); }
        if (allowed_redirect_uris !== undefined) {
            const uriList = Array.isArray(allowed_redirect_uris)
                ? allowed_redirect_uris.join('\n')
                : String(allowed_redirect_uris);
            updates.push(`allowed_redirect_uris = $${idx++}`);
            params.push(uriList.substring(0, 5000) || null);
        }
        if (updates.length > 0) {
            params.push(req.user.id);
            await pool.query(`UPDATE users SET ${updates.join(', ')} WHERE id = $${idx}`, params);
        }
        await pool.query(`INSERT INTO activity_log (id, user_id, type, title, status, ip, created_at) VALUES ($1, $2, $3, $4, $5, $6, NOW())`,
            [uuidv4(), req.user.id, 'settings_updated', 'Настройки обновлены', 'success', req.ip]);
        res.json({ success: true });
    } catch (err) {
        res.status(500).json({ error: { code: 'server_error', message: 'Server error', status: 500 } });
    }
});

// Enterprise: get stats (their connected users, API usage)
app.get('/api/v1/enterprise/stats', authMiddleware, async (req, res) => {
    try {
        if (req.user.role !== 'enterprise' && req.user.role !== 'admin') {
            return res.status(403).json({ error: { code: 'forbidden', message: 'Enterprise access required', status: 403 } });
        }
        const connectedUsers = await pool.query('SELECT COUNT(DISTINCT user_id) FROM connected_apps WHERE enterprise_id = $1', [req.user.id]);
        const keys = await pool.query("SELECT COUNT(*) FROM api_keys WHERE user_id = $1 AND status = 'active'", [req.user.id]);
        const recentAuth = await pool.query(
            "SELECT COUNT(*) FROM activity_log WHERE user_id = $1 AND type IN ('oauth_approve','login') AND created_at > NOW() - INTERVAL '24 hours'",
            [req.user.id]
        );
        res.json({
            connected_users: parseInt(connectedUsers.rows[0].count),
            active_keys: parseInt(keys.rows[0].count),
            auth_requests_24h: parseInt(recentAuth.rows[0].count)
        });
    } catch (err) {
        res.status(500).json({ error: { code: 'server_error', message: 'Server error', status: 500 } });
    }
});

// Enterprise: list connected users
app.get('/api/v1/enterprise/users', authMiddleware, async (req, res) => {
    try {
        if (req.user.role !== 'enterprise' && req.user.role !== 'admin') {
            return res.status(403).json({ error: { code: 'forbidden', message: 'Enterprise access required', status: 403 } });
        }
        const result = await pool.query(
            `SELECT ca.id, ca.scopes, ca.authorized_at, ca.last_used, u.id as user_id, u.email, u.name
             FROM connected_apps ca
             JOIN users u ON ca.user_id = u.id
             WHERE ca.enterprise_id = $1
             ORDER BY ca.last_used DESC`,
            [req.user.id]
        );
        res.json({ users: result.rows });
    } catch (err) {
        res.status(500).json({ error: { code: 'server_error', message: 'Server error', status: 500 } });
    }
});

// ===== WEBHOOK SYSTEM =====

async function fireWebhook(enterpriseId, event, payload) {
    if (!enterpriseId) return;
    try {
        const result = await pool.query(
            `SELECT webhook_url, webhook_secret FROM users WHERE id = $1 AND webhook_url IS NOT NULL AND webhook_url != ''`,
            [enterpriseId]
        );
        if (result.rows.length === 0) return;
        const { webhook_url, webhook_secret } = result.rows[0];
        if (!webhook_url || !/^https?:\/\//.test(webhook_url)) return;

        const deliveryId = uuidv4();
        const body = JSON.stringify({ id: deliveryId, event, timestamp: new Date().toISOString(), data: payload });
        const headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'TPID-Webhook/1.0',
            'X-TPID-Event': event,
            'X-TPID-Delivery': deliveryId,
        };
        if (webhook_secret) {
            headers['X-TPID-Signature'] = 'sha256=' + crypto.createHmac('sha256', webhook_secret).update(body).digest('hex');
        }
        const startMs = Date.now();
        try {
            const r = await fetch(webhook_url, { method: 'POST', headers, body, signal: AbortSignal.timeout(10000) });
            await pool.query(
                `INSERT INTO webhook_deliveries (id, enterprise_id, event, status_code, duration_ms, delivered_at) VALUES ($1, $2, $3, $4, $5, NOW())`,
                [deliveryId, enterpriseId, event, r.status, Date.now() - startMs]
            ).catch(() => {});
        } catch (err) {
            await pool.query(
                `INSERT INTO webhook_deliveries (id, enterprise_id, event, status_code, duration_ms, error, delivered_at) VALUES ($1, $2, $3, $4, $5, $6, NOW())`,
                [deliveryId, enterpriseId, event, 0, Date.now() - startMs, err.message.substring(0, 255)]
            ).catch(() => {});
        }
    } catch (err) {
        console.error('[WEBHOOK] fireWebhook error:', err.message);
    }
}

// Enterprise: get webhook settings
app.get('/api/v1/enterprise/webhook', authMiddleware, async (req, res) => {
    try {
        if (req.user.role !== 'enterprise' && req.user.role !== 'admin') {
            return res.status(403).json({ error: { code: 'forbidden', message: 'Enterprise access required', status: 403 } });
        }
        const r = await pool.query('SELECT webhook_url, webhook_secret, allowed_redirect_uris FROM users WHERE id = $1', [req.user.id]);
        const u = r.rows[0];
        res.json({
            webhook_url: u.webhook_url || '',
            has_secret: !!(u.webhook_secret),
            allowed_redirect_uris: u.allowed_redirect_uris ? u.allowed_redirect_uris.split('\n').filter(Boolean) : []
        });
    } catch (err) {
        res.status(500).json({ error: { code: 'server_error', message: 'Server error', status: 500 } });
    }
});

// Enterprise: update webhook URL + allowed redirect URIs
app.put('/api/v1/enterprise/webhook', authMiddleware, async (req, res) => {
    try {
        if (req.user.role !== 'enterprise' && req.user.role !== 'admin') {
            return res.status(403).json({ error: { code: 'forbidden', message: 'Enterprise access required', status: 403 } });
        }
        const { webhook_url, allowed_redirect_uris } = req.body;
        const updates = []; const params = []; let idx = 1;
        if (webhook_url !== undefined) {
            const clean = webhook_url ? sanitize(webhook_url, 500) : null;
            if (clean && !/^https?:\/\//.test(clean)) {
                return res.status(400).json({ error: { code: 'invalid_url', message: 'webhook_url must start with https://', status: 400 } });
            }
            updates.push(`webhook_url = $${idx++}`); params.push(clean || null);
        }
        if (allowed_redirect_uris !== undefined) {
            const raw = Array.isArray(allowed_redirect_uris) ? allowed_redirect_uris.join('\n') : String(allowed_redirect_uris || '');
            updates.push(`allowed_redirect_uris = $${idx++}`); params.push(sanitize(raw, 3000) || null);
        }
        if (updates.length === 0) return res.status(400).json({ error: { code: 'no_updates', message: 'No fields to update', status: 400 } });
        params.push(req.user.id);
        await pool.query(`UPDATE users SET ${updates.join(', ')} WHERE id = $${idx}`, params);
        await pool.query(`INSERT INTO activity_log (id, user_id, type, title, status, ip, created_at) VALUES ($1, $2, $3, $4, $5, $6, NOW())`,
            [uuidv4(), req.user.id, 'webhook_updated', 'Настройки вебхука обновлены', 'success', req.ip]);
        res.json({ success: true });
    } catch (err) {
        res.status(500).json({ error: { code: 'server_error', message: 'Server error', status: 500 } });
    }
});

// Enterprise: rotate webhook signing secret
app.post('/api/v1/enterprise/webhook/rotate-secret', authMiddleware, async (req, res) => {
    try {
        if (req.user.role !== 'enterprise' && req.user.role !== 'admin') {
            return res.status(403).json({ error: { code: 'forbidden', message: 'Enterprise access required', status: 403 } });
        }
        const secret = crypto.randomBytes(32).toString('hex');
        await pool.query('UPDATE users SET webhook_secret = $1 WHERE id = $2', [secret, req.user.id]);
        await pool.query(`INSERT INTO activity_log (id, user_id, type, title, status, ip, created_at) VALUES ($1, $2, $3, $4, $5, $6, NOW())`,
            [uuidv4(), req.user.id, 'webhook_secret_rotated', 'Секрет вебхука обновлён', 'success', req.ip]);
        res.json({ success: true, secret });
    } catch (err) {
        res.status(500).json({ error: { code: 'server_error', message: 'Server error', status: 500 } });
    }
});

// Enterprise: send test webhook
app.post('/api/v1/enterprise/webhook/test', authMiddleware, async (req, res) => {
    try {
        if (req.user.role !== 'enterprise' && req.user.role !== 'admin') {
            return res.status(403).json({ error: { code: 'forbidden', message: 'Enterprise access required', status: 403 } });
        }
        const r = await pool.query('SELECT webhook_url FROM users WHERE id = $1', [req.user.id]);
        if (!r.rows[0]?.webhook_url) {
            return res.status(400).json({ error: { code: 'no_webhook', message: 'Configure a webhook URL first', status: 400 } });
        }
        await fireWebhook(req.user.id, 'test', { message: 'Test webhook from TOKEN PAY ID', app: req.user.company_name || req.user.email, timestamp: new Date().toISOString() });
        res.json({ success: true, message: 'Test event fired. Check the delivery log.' });
    } catch (err) {
        res.status(500).json({ error: { code: 'server_error', message: 'Server error', status: 500 } });
    }
});

// Enterprise: webhook delivery log
app.get('/api/v1/enterprise/webhook/deliveries', authMiddleware, async (req, res) => {
    try {
        if (req.user.role !== 'enterprise' && req.user.role !== 'admin') {
            return res.status(403).json({ error: { code: 'forbidden', message: 'Enterprise access required', status: 403 } });
        }
        const limit = Math.min(parseInt(req.query.limit) || 50, 200);
        const offset = parseInt(req.query.offset) || 0;
        const result = await pool.query(
            'SELECT id, event, status_code, duration_ms, error, delivered_at FROM webhook_deliveries WHERE enterprise_id = $1 ORDER BY delivered_at DESC LIMIT $2 OFFSET $3',
            [req.user.id, limit, offset]
        );
        const count = await pool.query('SELECT COUNT(*) FROM webhook_deliveries WHERE enterprise_id = $1', [req.user.id]);
        res.json({ deliveries: result.rows, total: parseInt(count.rows[0].count) });
    } catch (err) {
        res.status(500).json({ error: { code: 'server_error', message: 'Server error', status: 500 } });
    }
});

// Admin: view all webhook deliveries
app.get('/api/v1/admin/webhooks', authMiddleware, adminMiddleware, async (req, res) => {
    try {
        const limit = Math.min(parseInt(req.query.limit) || 100, 500);
        const offset = parseInt(req.query.offset) || 0;
        const result = await pool.query(
            `SELECT wd.*, u.email, u.company_name FROM webhook_deliveries wd JOIN users u ON wd.enterprise_id = u.id ORDER BY wd.delivered_at DESC LIMIT $1 OFFSET $2`,
            [limit, offset]
        );
        const count = await pool.query('SELECT COUNT(*) FROM webhook_deliveries');
        res.json({ deliveries: result.rows, total: parseInt(count.rows[0].count) });
    } catch (err) {
        res.status(500).json({ error: { code: 'server_error', message: 'Server error', status: 500 } });
    }
});

// ===== CONTACT FORM =====
app.post('/api/v1/contact', async (req, res) => {
    try {
        const { name, email, message } = req.body;
        if (!name || !email || !message) {
            return res.status(400).json({ error: { message: 'All fields required' } });
        }
        // Send to company email via sendEmail helper (non-blocking)
        sendEmail('info@tokenpay.space', `[Обратная связь] от ${sanitize(name, 100)}`,
                `<div style="font-family:sans-serif;padding:20px;background:#0a0a0a;color:#e8e8e8;border-radius:12px">
                    <h2 style="color:#fff;margin:0 0 16px">Новое обращение</h2>
                    <p><strong>Имя:</strong> ${sanitize(name, 200)}</p>
                    <p><strong>Email:</strong> <a href="mailto:${email}" style="color:#4488ff">${email}</a></p>
                    <p><strong>Сообщение:</strong></p>
                    <div style="background:#111;padding:16px;border-radius:8px;border:1px solid #222;margin-top:8px">${sanitize(message, 5000).replace(/\n/g, '<br>')}</div>
                </div>`
            ).catch(smtpErr => console.error('[CONTACT] Email error:', smtpErr.message));
        // Log to DB for admin review (use admin user_id to avoid FK null issue)
        try {
            const adminRow = await pool.query('SELECT id FROM users WHERE role = $1 LIMIT 1', ['admin']);
            const logUserId = adminRow.rows.length > 0 ? adminRow.rows[0].id : null;
            await pool.query(
                `INSERT INTO activity_log (id, user_id, type, title, status, ip, created_at) VALUES ($1, $2, $3, $4, $5, $6, NOW())`,
                [uuidv4(), logUserId, 'contact_form', `Обращение от ${sanitize(name, 50)}: ${sanitize(message, 100)}`, 'info', req.ip]
            );
        } catch(e) {}
        res.json({ success: true });
    } catch (err) {
        console.error('[CONTACT] Error:', err.message);
        res.status(500).json({ error: { message: 'Failed to send' } });
    }
});

// ===== PERIODIC CLEANUP =====
setInterval(async () => {
    try {
        // Clean expired email codes (older than 1 day)
        await pool.query("DELETE FROM email_codes WHERE expires_at < NOW() - INTERVAL '1 day'");
        // Clean expired oauth codes (older than 1 hour)
        await pool.query("DELETE FROM oauth_codes WHERE expires_at < NOW() - INTERVAL '1 hour'");
        // Clean stale sessions (inactive > 30 days)
        await pool.query("DELETE FROM sessions WHERE last_active < NOW() - INTERVAL '30 days'");
        // Clean old webhook deliveries (older than 30 days)
        await pool.query("DELETE FROM webhook_deliveries WHERE delivered_at < NOW() - INTERVAL '30 days'");
        // Clean old activity log entries (older than 90 days)
        await pool.query("DELETE FROM activity_log WHERE created_at < NOW() - INTERVAL '90 days'");
    } catch (err) {
        // Cleanup is best-effort
    }
}, 6 * 3600000); // Every 6 hours

// ===== START =====
app.listen(PORT, async () => {
    console.log(`[TOKEN PAY ID API] Running on port ${PORT}`);
    initTransporter();
    try {
        await initDB();
        console.log('[TOKEN PAY ID API] Database connected & initialized');
    } catch (err) {
        console.error('[TOKEN PAY ID API] Database connection failed:', err.message);
        console.log('[TOKEN PAY ID API] API running without database — will retry on requests');
    }
});
