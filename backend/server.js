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
const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD || 'Zdcgbjm777812.';

// ===== DATABASE =====
const pool = new Pool({
    host: process.env.DB_HOST || '5.23.55.152',
    port: process.env.DB_PORT || 5432,
    database: process.env.DB_NAME || 'default_db',
    user: process.env.DB_USER || 'gen_user',
    password: process.env.DB_PASSWORD || '93JJFQLAYC=Uo)',
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

const allowedOrigins = (process.env.CORS_ORIGIN || 'https://tokenpay.space').split(',').map(s => s.trim());
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

// ===== AUTH MIDDLEWARE =====
function authMiddleware(req, res, next) {
    const auth = req.headers.authorization;
    if (!auth || !auth.startsWith('Bearer ')) {
        return res.status(401).json({ error: { code: 'unauthorized', message: 'Missing or invalid token', status: 401 } });
    }
    const token = auth.split(' ')[1];

    // Check if it's an API key
    if (token.startsWith('tpid_sk_')) {
        pool.query('SELECT u.* FROM users u JOIN api_keys k ON u.id = k.user_id WHERE k.secret_key = $1 AND k.status = $2', [token, 'active'])
            .then(result => {
                if (result.rows.length === 0) return res.status(401).json({ error: { code: 'invalid_key', message: 'Invalid API key', status: 401 } });
                req.user = result.rows[0];
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

function generateTokens(userId, rememberMe = true) {
    const accessToken = jwt.sign({ userId }, JWT_SECRET, { expiresIn: '1h' });
    const refreshToken = jwt.sign({ userId }, JWT_REFRESH_SECRET, { expiresIn: rememberMe ? '30d' : '24h' });
    return { accessToken, refreshToken, expiresIn: 3600 };
}

// ===== HEALTH =====
app.get('/health', (req, res) => {
    res.json({ status: 'ok', service: 'tokenpay-id-api', version: '1.0.0', timestamp: new Date().toISOString() });
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
        const code = String(Math.floor(100000 + Math.random() * 900000));

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
                const code = String(Math.floor(100000 + Math.random() * 900000));
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
        const code = String(Math.floor(100000 + Math.random() * 900000));

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
        const code6 = String(Math.floor(100000 + Math.random() * 900000));
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
        created_at: u.created_at, last_login: u.last_login
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
        const { name, locale, theme } = req.body;
        if (name) {
            await pool.query('UPDATE users SET name = $1 WHERE id = $2', [name, req.user.id]);
            req.user.name = name;
        }
        if (locale && ['ru', 'en'].includes(locale)) {
            await pool.query('UPDATE users SET locale = $1 WHERE id = $2', [locale, req.user.id]);
            req.user.locale = locale;
        }
        if (theme && ['light', 'dark'].includes(theme)) {
            await pool.query('UPDATE users SET theme = $1 WHERE id = $2', [theme, req.user.id]);
            req.user.theme = theme;
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
            params.push('%' + type + '%');
        }
        query += ' ORDER BY created_at DESC LIMIT $' + (params.length + 1) + ' OFFSET $' + (params.length + 2);
        params.push(limit, offset);

        const result = await pool.query(query, params);
        res.json({ activity: result.rows, total: result.rows.length });
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

// List keys
app.get('/api/v1/keys', authMiddleware, async (req, res) => {
    try {
        const result = await pool.query(
            'SELECT id, name, public_key, LEFT(secret_key, 16) as secret_prefix, status, created_at, last_used FROM api_keys WHERE user_id = $1 ORDER BY created_at DESC',
            [req.user.id]
        );
        res.json({ keys: result.rows });
    } catch (err) {
        res.status(500).json({ error: { code: 'server_error', message: 'Internal server error', status: 500 } });
    }
});

// Create key
app.post('/api/v1/keys', authMiddleware, async (req, res) => {
    try {
        const { name } = req.body;
        if (!name) return res.status(400).json({ error: { code: 'missing_name', message: 'Key name is required', status: 400 } });

        const id = uuidv4();
        const publicKey = 'tpid_pk_' + uuidv4().replace(/-/g, '').substring(0, 16);
        const secretKey = 'tpid_sk_' + uuidv4().replace(/-/g, '') + uuidv4().replace(/-/g, '').substring(0, 8);

        await pool.query(
            `INSERT INTO api_keys (id, user_id, name, public_key, secret_key, status, created_at)
             VALUES ($1, $2, $3, $4, $5, $6, NOW())`,
            [id, req.user.id, name, publicKey, secretKey, 'active']
        );

        await pool.query(
            `INSERT INTO activity_log (id, user_id, type, title, status, ip, created_at)
             VALUES ($1, $2, $3, $4, $5, $6, NOW())`,
            [uuidv4(), req.user.id, 'key_created', 'API ключ "' + name + '" создан', 'success', req.ip]
        );

        res.status(201).json({ id, name, public_key: publicKey, secret_key: secretKey, status: 'active', created_at: new Date().toISOString() });
    } catch (err) {
        res.status(500).json({ error: { code: 'server_error', message: 'Internal server error', status: 500 } });
    }
});

// Revoke key
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

        res.json({ success: true });
    } catch (err) {
        res.status(500).json({ error: { code: 'server_error', message: 'Internal server error', status: 500 } });
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
            params.push('%' + type + '%');
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
        const users = await pool.query('SELECT COUNT(*) FROM users');
        const verified = await pool.query('SELECT COUNT(*) FROM users WHERE email_verified = TRUE');
        const twofa = await pool.query('SELECT COUNT(*) FROM users WHERE two_factor_enabled = TRUE');
        const enterprise = await pool.query("SELECT COUNT(*) FROM users WHERE role = 'enterprise'");
        const keys = await pool.query("SELECT COUNT(*) FROM api_keys WHERE status = 'active'");
        const revokedKeys = await pool.query("SELECT COUNT(*) FROM api_keys WHERE status = 'revoked'");
        const sessions = await pool.query('SELECT COUNT(*) FROM sessions');
        const todayActivity = await pool.query("SELECT COUNT(*) FROM activity_log WHERE created_at > NOW() - INTERVAL '24 hours'");
        const weekActivity = await pool.query("SELECT COUNT(*) FROM activity_log WHERE created_at > NOW() - INTERVAL '7 days'");
        const totalActivity = await pool.query('SELECT COUNT(*) FROM activity_log');
        const todayLogins = await pool.query("SELECT COUNT(*) FROM activity_log WHERE type = 'login' AND created_at > NOW() - INTERVAL '24 hours'");
        const todayRegistrations = await pool.query("SELECT COUNT(*) FROM activity_log WHERE type = 'account_created' AND created_at > NOW() - INTERVAL '24 hours'");
        const failedLogins = await pool.query("SELECT COUNT(*) FROM activity_log WHERE type = 'login_failed' AND created_at > NOW() - INTERVAL '24 hours'");
        const connectedApps = await pool.query('SELECT COUNT(*) FROM connected_apps');
        const oauthCodes = await pool.query("SELECT COUNT(*) FROM oauth_codes WHERE expires_at > NOW() AND used = FALSE");

        // Roles breakdown
        const roleBreakdown = await pool.query("SELECT role, COUNT(*) as count FROM users GROUP BY role ORDER BY count DESC");

        // Recent registrations (last 7 days per day)
        const recentRegs = await pool.query(`
            SELECT DATE(created_at) as date, COUNT(*) as count 
            FROM users WHERE created_at > NOW() - INTERVAL '7 days' 
            GROUP BY DATE(created_at) ORDER BY date DESC
        `);

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
        jwks_uri: `${issuer}/.well-known/jwks.json`,
        response_types_supported: ['code'],
        grant_types_supported: ['authorization_code', 'refresh_token'],
        subject_types_supported: ['public'],
        id_token_signing_alg_values_supported: ['RS256'],
        scopes_supported: ['openid', 'profile', 'email'],
        token_endpoint_auth_methods_supported: ['client_secret_post', 'client_secret_basic'],
        code_challenge_methods_supported: ['S256', 'plain'],
        claims_supported: ['sub', 'email', 'name', 'email_verified', 'iat', 'exp']
    });
});

// ===== FULL OAUTH 2.0 AUTHORIZATION CODE FLOW (+ PKCE) =====

// GET /api/v1/oauth/authorize — redirect user to consent screen
app.get('/api/v1/oauth/authorize', async (req, res) => {
    try {
        const { client_id, redirect_uri, response_type, scope, state } = req.query;
        if (response_type !== 'code') {
            return res.status(400).json({ error: { code: 'unsupported_response_type', message: 'Only response_type=code is supported', status: 400 } });
        }
        if (!client_id || !redirect_uri) {
            return res.status(400).json({ error: { code: 'missing_params', message: 'client_id and redirect_uri are required', status: 400 } });
        }
        const keyResult = await pool.query(
            'SELECT k.*, u.name as owner_name FROM api_keys k JOIN users u ON k.user_id = u.id WHERE k.public_key = $1 AND k.status = $2',
            [client_id, 'active']
        );
        if (keyResult.rows.length === 0) {
            return res.status(400).json({ error: { code: 'invalid_client', message: 'Unknown client_id', status: 400 } });
        }
        // Redirect to consent page with params
        const params = new URLSearchParams({
            client_id, redirect_uri, scope: scope || 'profile', state: state || '',
            app_name: keyResult.rows[0].name, owner_name: keyResult.rows[0].owner_name
        });
        res.redirect(`/oauth-consent.html?${params.toString()}`);
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
            'SELECT * FROM api_keys WHERE public_key = $1 AND status = $2', [client_id, 'active']
        );
        if (keyResult.rows.length === 0) {
            return res.status(400).json({ error: { code: 'invalid_client', message: 'Invalid client_id', status: 400 } });
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
        const redirectUrl = new URL(redirect_uri);
        redirectUrl.searchParams.set('code', code);
        if (state) redirectUrl.searchParams.set('state', state);
        res.json({ redirect_url: redirectUrl.toString(), code });
    } catch (err) {
        console.error('OAuth approve error:', err);
        res.status(500).json({ error: { code: 'server_error', message: 'Internal server error', status: 500 } });
    }
});

// POST /api/v1/oauth/token — exchange auth code for access token (PKCE supported)
app.post('/api/v1/oauth/token', async (req, res) => {
    try {
        const { grant_type, code, client_id, client_secret, redirect_uri, code_verifier } = req.body;
        if (grant_type !== 'authorization_code') {
            return res.status(400).json({ error: { code: 'unsupported_grant', message: 'Only authorization_code is supported', status: 400 } });
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
        email_verified: u.email_verified,
        created_at: u.created_at
    });
});

// POST /api/v1/oauth/revoke — revoke an OAuth token
app.post('/api/v1/oauth/revoke', async (req, res) => {
    try {
        const { token } = req.body;
        if (!token) return res.status(400).json({ error: { code: 'missing_token', message: 'Token required', status: 400 } });
        // We just acknowledge — JWT tokens are stateless, so "revoking" is a no-op
        // In production, add token to a blacklist
        res.json({ success: true });
    } catch (err) {
        res.status(500).json({ error: { code: 'server_error', message: 'Internal server error', status: 500 } });
    }
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
        await pool.query('DELETE FROM connected_apps WHERE id = $1 AND user_id = $2', [req.params.id, req.user.id]);
        res.json({ success: true });
    } catch (err) {
        res.status(500).json({ error: { code: 'server_error', message: 'Server error', status: 500 } });
    }
});

// Enterprise: get settings (callback URL etc)
app.get('/api/v1/enterprise/settings', authMiddleware, async (req, res) => {
    try {
        if (req.user.role !== 'enterprise' && req.user.role !== 'admin') {
            return res.status(403).json({ error: { code: 'forbidden', message: 'Enterprise access required', status: 403 } });
        }
        res.json({ callback_url: req.user.callback_url || '', company_name: req.user.company_name || '', website: req.user.website || '' });
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
        const { callback_url } = req.body;
        if (callback_url !== undefined) {
            const cleanUrl = sanitize(callback_url, 500);
            await pool.query('UPDATE users SET callback_url = $1 WHERE id = $2', [cleanUrl || null, req.user.id]);
            req.user.callback_url = cleanUrl;
        }
        await pool.query(
            `INSERT INTO activity_log (id, user_id, type, title, status, ip, created_at) VALUES ($1, $2, $3, $4, $5, $6, NOW())`,
            [uuidv4(), req.user.id, 'settings_updated', 'Настройки интеграции обновлены', 'success', req.ip]
        );
        res.json({ success: true, callback_url: req.user.callback_url || '' });
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
        // Log to DB for admin review
        try {
            await pool.query(
                `INSERT INTO activity_log (id, user_id, type, title, status, ip, created_at) VALUES ($1, $2, $3, $4, $5, $6, NOW())`,
                [uuidv4(), null, 'contact_form', `Обращение от ${sanitize(name, 50)}: ${sanitize(message, 100)}`, 'info', req.ip]
            );
        } catch(e) {}
        res.json({ success: true });
    } catch (err) {
        console.error('[CONTACT] Error:', err.message);
        res.status(500).json({ error: { message: 'Failed to send' } });
    }
});

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
