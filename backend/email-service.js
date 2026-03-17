const nodemailer = require('nodemailer');

// HTML escape to prevent injection in email templates
function _h(s) { return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;'); }

// ===== SMTP CONFIG =====
const SMTP_HOST = process.env.SMTP_HOST || 'smtp.timeweb.ru';
const SMTP_PORT = parseInt(process.env.SMTP_PORT) || 465;
const SMTP_USER = process.env.SMTP_USER || 'info@tokenpay.space';
const SMTP_PASS = process.env.SMTP_PASS || '';
const FROM_NAME = 'TOKEN PAY ID';
const FROM_EMAIL = process.env.SMTP_FROM || 'info@tokenpay.space';
const LOGO_URL = 'https://tokenpay.space/tokenpay-logo.png';
const SITE_URL = 'https://tokenpay.space';

let transporter = null;

function initTransporter() {
    if (SMTP_PASS) {
        transporter = nodemailer.createTransport({
            host: SMTP_HOST,
            port: SMTP_PORT,
            secure: SMTP_PORT === 465,
            auth: { user: SMTP_USER, pass: SMTP_PASS },
            tls: { rejectUnauthorized: true }
        });
        console.log('[EMAIL] SMTP configured:', SMTP_HOST);
    } else {
        console.log('[EMAIL] SMTP not configured — emails will be logged to console');
    }
}

// ===== i18n =====
const i18n = {
    ru: {
        doNotShare: 'Никогда не сообщайте этот код другим людям. Сотрудники TOKEN PAY никогда не попросят ваш код.',
        ignoreIfNot: 'Если вы не запрашивали этот код — просто проигнорируйте это письмо.',
        validFor: (m) => `Действителен ${m} минут`,
        verifyTitle: 'Код подтверждения',
        hi: (n) => `Здравствуйте, ${n}!`,
        verifyText: 'Используйте этот код для подтверждения:',
        loginTitle: 'Новый вход в аккаунт',
        loginText: (n) => `Здравствуйте, ${n}! Зафиксирован новый вход в ваш аккаунт:`,
        ip: 'IP-адрес', device: 'Устройство', time: 'Время',
        loginWarn: 'Если это были не вы, немедленно смените пароль:',
        loginBtn: 'Управление аккаунтом',
        welcomeTitle: 'Добро пожаловать!',
        welcomeText: (n) => `Здравствуйте, ${n}! Ваш аккаунт успешно создан.`,
        feat1: 'Единая авторизация', feat2: 'API ключи', feat3: 'Панель управления', feat4: '2FA защита',
        welcomeBtn: 'Открыть личный кабинет',
        welcomeTip: 'Рекомендуем включить 2FA для максимальной безопасности.',
        resetTitle: 'Сброс пароля',
        resetText: (n) => `Здравствуйте, ${n}! Мы получили запрос на сброс пароля:`,
        resetIgnore: 'Если вы не запрашивали сброс — проигнорируйте это письмо.',
        resetWarn: 'Если вы не делали запрос, возможно кто-то пытается получить доступ к вашему аккаунту.',
        oauthTitle: 'OAuth авторизация',
        oauthText: (n) => `Здравствуйте, ${n}! Вы предоставили доступ приложению:`,
        app: 'Приложение', scopes: 'Разрешения',
        oauthWarn: 'Если это были не вы, отзовите доступ:',
        oauthBtn: 'Управление доступом',
        keyTitle: 'Новый API ключ',
        keyText: (n) => `Здравствуйте, ${n}! Создан новый API ключ:`,
        keyName: 'Название',
        keyWarn: 'Секретный ключ (sk) был показан только один раз. Если не сохранили — создайте новый.',
        entApprovedTitle: 'Заявка одобрена',
        entApprovedText: (n, c) => `Здравствуйте, ${n}! Ваша заявка на корпоративный аккаунт «${c}» одобрена.`,
        entRejectedTitle: 'Заявка отклонена',
        entRejectedText: (n, c, r) => `Здравствуйте, ${n}! Заявка на корпоративный аккаунт «${c}» отклонена.${r ? ' Причина: ' + r : ''}`,
        entBtn: 'Открыть личный кабинет',
        securityTitle: 'Уведомление безопасности',
        securityText: (n, a) => `Здравствуйте, ${n}! В вашем аккаунте выполнено действие: ${a}.`,
        securityBtn: 'Проверить аккаунт',
    },
    en: {
        doNotShare: 'Never share this code with anyone. TOKEN PAY employees will never ask for your code.',
        ignoreIfNot: "If you didn't request this code, simply ignore this email.",
        validFor: (m) => `Valid for ${m} minutes`,
        verifyTitle: 'Verification Code',
        hi: (n) => `Hello, ${n}!`,
        verifyText: 'Use this code to verify your identity:',
        loginTitle: 'New Sign-In Detected',
        loginText: (n) => `Hello, ${n}! A new sign-in to your account was detected:`,
        ip: 'IP Address', device: 'Device', time: 'Time',
        loginWarn: "If this wasn't you, change your password immediately:",
        loginBtn: 'Manage Account',
        welcomeTitle: 'Welcome!',
        welcomeText: (n) => `Hello, ${n}! Your account has been created successfully.`,
        feat1: 'Single sign-on', feat2: 'API keys', feat3: 'Dashboard', feat4: '2FA protection',
        welcomeBtn: 'Open Dashboard',
        welcomeTip: 'We recommend enabling 2FA for maximum account security.',
        resetTitle: 'Password Reset',
        resetText: (n) => `Hello, ${n}! We received a password reset request:`,
        resetIgnore: "If you didn't request this, simply ignore this email.",
        resetWarn: "If you didn't make this request, someone may be trying to access your account.",
        oauthTitle: 'OAuth Authorization',
        oauthText: (n) => `Hello, ${n}! You granted access to an application:`,
        app: 'Application', scopes: 'Permissions',
        oauthWarn: "If this wasn't you, revoke access immediately:",
        oauthBtn: 'Manage Access',
        keyTitle: 'New API Key',
        keyText: (n) => `Hello, ${n}! A new API key was created:`,
        keyName: 'Name',
        keyWarn: "The secret key (sk) was shown only once. If you didn't save it, create a new key.",
        entApprovedTitle: 'Application Approved',
        entApprovedText: (n, c) => `Hello, ${n}! Your enterprise application for "${c}" has been approved.`,
        entRejectedTitle: 'Application Rejected',
        entRejectedText: (n, c, r) => `Hello, ${n}! Your enterprise application for "${c}" has been rejected.${r ? ' Reason: ' + r : ''}`,
        entBtn: 'Open Dashboard',
        securityTitle: 'Security Alert',
        securityText: (n, a) => `Hello, ${n}! An action was performed on your account: ${a}.`,
        securityBtn: 'Check Account',
    }
};

function s(lang) { return i18n[lang] || i18n.ru; }

// ===== BASE TEMPLATE — Comfortaa font, logo image, single language =====
function baseTemplate(content, preheader = '') {
    return `<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>TOKEN PAY ID</title>
<style>
body{margin:0;padding:0;background:#050505;font-family:'Comfortaa','Segoe UI',Roboto,Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased}
.pre{display:none!important;max-height:0;overflow:hidden;font-size:1px;line-height:1px;color:#050505}
.w{max-width:580px;margin:0 auto;padding:48px 20px}
.c{background:#0a0a0c;border:1px solid rgba(255,255,255,.06);border-radius:24px;overflow:hidden;box-shadow:0 32px 64px rgba(0,0,0,.5)}
.h{padding:40px 36px 32px;text-align:center;border-bottom:1px solid rgba(255,255,255,.05);background:linear-gradient(180deg,rgba(255,255,255,.015),transparent)}
.b{padding:36px 36px 32px}
.b h1{font-family:'Comfortaa',sans-serif;color:#fff;font-size:22px;font-weight:700;margin:0 0 8px}
.b p{color:rgba(255,255,255,.5);font-size:13px;line-height:1.7;margin:0 0 14px;font-family:'Comfortaa',sans-serif}
.cb{background:linear-gradient(135deg,rgba(255,255,255,.03),rgba(255,255,255,.01));border:1px solid rgba(255,255,255,.08);border-radius:16px;padding:28px;text-align:center;margin:24px 0}
.cv{font-size:22px;font-weight:700;color:#fff;letter-spacing:6px;font-family:'Comfortaa','Segoe UI',monospace}
.cl{font-size:11px;color:rgba(255,255,255,.25);margin-top:12px;font-family:'Comfortaa',sans-serif}
.bw{text-align:center;margin:28px 0}
.bt{display:inline-block;background:#fff;color:#000;text-decoration:none;padding:14px 40px;border-radius:12px;font-size:13px;font-weight:700;font-family:'Comfortaa',sans-serif}
.in{margin:20px 0;border:1px solid rgba(255,255,255,.05);border-radius:14px;overflow:hidden;background:rgba(255,255,255,.01)}
.ir{display:flex;justify-content:space-between;align-items:center;padding:12px 18px;border-bottom:1px solid rgba(255,255,255,.03)}
.ir:last-child{border-bottom:none}
.il{color:rgba(255,255,255,.3);font-size:11px;font-family:'Comfortaa',sans-serif}
.iv{color:rgba(255,255,255,.8);font-size:12px;font-weight:600;font-family:'Comfortaa',sans-serif;text-align:right}
.wn{background:rgba(255,180,0,.03);border:1px solid rgba(255,180,0,.1);border-radius:12px;padding:14px 18px;margin:20px 0}
.wn p{color:rgba(255,180,0,.65);font-size:11px;margin:0;line-height:1.55;font-family:'Comfortaa',sans-serif}
.f{padding:28px 36px;text-align:center;border-top:1px solid rgba(255,255,255,.04)}
.f p{color:rgba(255,255,255,.15);font-size:10px;margin:0;line-height:1.7;font-family:'Comfortaa',sans-serif}
.f a{color:rgba(255,255,255,.25);text-decoration:underline}
</style></head><body>
<div class="pre">${preheader}</div>
<div class="w"><div class="c">
<div class="h"><a href="${SITE_URL}" style="text-decoration:none"><img src="${LOGO_URL}" alt="TOKEN PAY ID" width="240" style="max-width:280px;width:240px;height:auto" /></a></div>
<div class="b">${content}</div>
<div class="f"><p>\u00A9 ${new Date().getFullYear()} TOKEN PAY LLC<br><a href="${SITE_URL}">tokenpay.space</a> \u00B7 <a href="mailto:info@tokenpay.space">info@tokenpay.space</a></p></div>
</div></div></body></html>`;
}

// ===== TEMPLATE FUNCTIONS (single-language, lang param) =====

function verificationCodeTemplate(name, code, expiresMin = 10, lang = 'ru') {
    const l = s(lang);
    return baseTemplate(`<h1>${l.verifyTitle}</h1><p>${l.hi(_h(name))}</p><p>${l.verifyText}</p>
<div class="cb"><div class="cv">${_h(code)}</div><div class="cl">${l.validFor(expiresMin)}</div></div>
<p>${l.ignoreIfNot}</p><div class="wn"><p>${l.doNotShare}</p></div>`, String(code));
}

function loginNotificationTemplate(name, ip, device, time, lang = 'ru') {
    const l = s(lang);
    return baseTemplate(`<h1>${l.loginTitle}</h1><p>${l.loginText(_h(name))}</p>
<div class="in"><div class="ir"><span class="il">${l.ip}</span><span class="iv">${_h(ip)}</span></div>
<div class="ir"><span class="il">${l.device}</span><span class="iv">${_h(device)}</span></div>
<div class="ir"><span class="il">${l.time}</span><span class="iv">${_h(time)}</span></div></div>
<p>${l.loginWarn}</p><div class="bw"><a href="${SITE_URL}/dashboard" class="bt">${l.loginBtn}</a></div>`, _h(ip));
}

function welcomeTemplate(name, lang = 'ru') {
    const l = s(lang);
    return baseTemplate(`<h1>${l.welcomeTitle}</h1><p>${l.welcomeText(_h(name))}</p>
<div class="in"><div class="ir"><span class="il">\uD83D\uDD10</span><span class="iv">${l.feat1}</span></div>
<div class="ir"><span class="il">\uD83D\uDD11</span><span class="iv">${l.feat2}</span></div>
<div class="ir"><span class="il">\uD83D\uDCCA</span><span class="iv">${l.feat3}</span></div>
<div class="ir"><span class="il">\uD83D\uDEE1\uFE0F</span><span class="iv">${l.feat4}</span></div></div>
<div class="bw"><a href="${SITE_URL}/dashboard" class="bt">${l.welcomeBtn}</a></div>
<p>${l.welcomeTip}</p>`, _h(name));
}

function passwordResetTemplate(name, code, expiresMin = 15, lang = 'ru') {
    const l = s(lang);
    return baseTemplate(`<h1>${l.resetTitle}</h1><p>${l.resetText(_h(name))}</p>
<div class="cb"><div class="cv">${_h(code)}</div><div class="cl">${l.validFor(expiresMin)}</div></div>
<p>${l.resetIgnore}</p><div class="wn"><p>${l.resetWarn}</p></div>`, String(code));
}

function oauthApprovalTemplate(name, appName, scopes, time, lang = 'ru') {
    const l = s(lang);
    return baseTemplate(`<h1>${l.oauthTitle}</h1><p>${l.oauthText(_h(name))}</p>
<div class="in"><div class="ir"><span class="il">${l.app}</span><span class="iv">${_h(appName)}</span></div>
<div class="ir"><span class="il">${l.scopes}</span><span class="iv">${_h(scopes)}</span></div>
<div class="ir"><span class="il">${l.time}</span><span class="iv">${_h(time)}</span></div></div>
<p>${l.oauthWarn}</p><div class="bw"><a href="${SITE_URL}/dashboard" class="bt">${l.oauthBtn}</a></div>`, _h(appName));
}

function apiKeyCreatedTemplate(name, keyName, publicKey, lang = 'ru') {
    const l = s(lang);
    return baseTemplate(`<h1>${l.keyTitle}</h1><p>${l.keyText(_h(name))}</p>
<div class="in"><div class="ir"><span class="il">${l.keyName}</span><span class="iv">${_h(keyName)}</span></div>
<div class="ir"><span class="il">Public Key</span><span class="iv" style="font-family:'Comfortaa',monospace;font-size:10px">${_h(publicKey)}</span></div></div>
<div class="wn"><p>${l.keyWarn}</p></div>`, _h(keyName));
}

function enterpriseApprovedTemplate(name, company, lang = 'ru') {
    const l = s(lang);
    return baseTemplate(`<h1>${l.entApprovedTitle}</h1><p>${l.entApprovedText(_h(name), _h(company))}</p>
<div class="in"><div class="ir"><span class="il">\uD83C\uDFE2</span><span class="iv">${_h(company)}</span></div>
<div class="ir"><span class="il">\uD83D\uDD11</span><span class="iv">API & OAuth 2.0</span></div></div>
<div class="bw"><a href="${SITE_URL}/dashboard" class="bt">${l.entBtn}</a></div>`, _h(company));
}

function enterpriseRejectedTemplate(name, company, reason, lang = 'ru') {
    const l = s(lang);
    return baseTemplate(`<h1>${l.entRejectedTitle}</h1><p>${l.entRejectedText(_h(name), _h(company), _h(reason))}</p>`, _h(company));
}

function securityAlertTemplate(name, action, ip, lang = 'ru') {
    const l = s(lang);
    return baseTemplate(`<h1>${l.securityTitle}</h1><p>${l.securityText(_h(name), _h(action))}</p>
<div class="in"><div class="ir"><span class="il">${l.ip || 'IP'}</span><span class="iv">${_h(ip)}</span></div></div>
<div class="bw"><a href="${SITE_URL}/dashboard" class="bt">${l.securityBtn}</a></div>`, _h(action));
}

// ===== SEND =====
async function sendEmail(to, subject, html) {
    if (!transporter) {
        console.log(`[EMAIL] (no SMTP) To: ${to} | Subject: ${subject}`);
        return { accepted: [to], messageId: 'console-' + Date.now() };
    }
    try {
        const info = await transporter.sendMail({
            from: `"${FROM_NAME}" <${FROM_EMAIL}>`,
            to, subject, html,
            headers: { 'X-Mailer': 'TokenPayID/2.0', 'List-Unsubscribe': `<mailto:${FROM_EMAIL}?subject=unsubscribe>` }
        });
        console.log(`[EMAIL] Sent to ${to}: ${info.messageId}`);
        return info;
    } catch (err) {
        console.error(`[EMAIL] Error sending to ${to}:`, err.message);
        throw err;
    }
}

module.exports = {
    initTransporter,
    sendEmail,
    templates: {
        verificationCode: verificationCodeTemplate,
        loginNotification: loginNotificationTemplate,
        welcome: welcomeTemplate,
        passwordReset: passwordResetTemplate,
        oauthApproval: oauthApprovalTemplate,
        apiKeyCreated: apiKeyCreatedTemplate,
        enterpriseApproved: enterpriseApprovedTemplate,
        enterpriseRejected: enterpriseRejectedTemplate,
        securityAlert: securityAlertTemplate
    }
};
