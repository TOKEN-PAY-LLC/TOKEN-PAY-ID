const nodemailer = require('nodemailer');

function _h(s) { return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;'); }

// ===== SMTP CONFIG =====
const SMTP_HOST = process.env.SMTP_HOST || 'smtp.timeweb.ru';
const SMTP_PORT = parseInt(process.env.SMTP_PORT) || 465;
const SMTP_USER = process.env.SMTP_USER || 'noreply@tokenpay.space';
const SMTP_PASS = process.env.SMTP_PASS || '';
const FROM_NAME = 'TOKEN PAY ID';
const FROM_EMAIL = process.env.SMTP_FROM || 'noreply@tokenpay.space';
const LOGO_URL = 'https://tokenpay.space/tpid-logo-white.png';
const SITE_URL = 'https://tokenpay.space';
const YEAR = new Date().getFullYear();

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
        magicTitle: 'Подтверждение входа',
        magicText: (n) => `Здравствуйте, ${n}! Нажмите кнопку ниже, чтобы подтвердить вход в аккаунт:`,
        magicBtn: 'Подтвердить вход',
        magicWarn: 'Ссылка действительна 10 минут. Если вы не запрашивали вход — проигнорируйте это письмо.',
        deviceTitle: 'Новое устройство доверено',
        deviceText: (n) => `Здравствуйте, ${n}! Новое устройство добавлено в список доверенных:`,
        deviceWarn: 'Если это были не вы, немедленно смените пароль и отзовите доступ.',
        deviceBtn: 'Управление устройствами',
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
        magicTitle: 'Login Confirmation',
        magicText: (n) => `Hello, ${n}! Click the button below to confirm your sign-in:`,
        magicBtn: 'Confirm Sign-In',
        magicWarn: 'This link is valid for 10 minutes. If you did not request this, ignore this email.',
        deviceTitle: 'New Trusted Device',
        deviceText: (n) => `Hello, ${n}! A new device has been added to your trusted list:`,
        deviceWarn: "If this wasn't you, change your password and revoke access immediately.",
        deviceBtn: 'Manage Devices',
    },
    zh: {
        doNotShare: '请勿将此验证码告诉任何人。TOKEN PAY 工作人员绝不会索要您的验证码。',
        ignoreIfNot: '如果您未请求此验证码，请忽略此邮件。',
        validFor: (m) => `有效期 ${m} 分钟`,
        verifyTitle: '验证码',
        hi: (n) => `您好，${n}！`,
        verifyText: '请使用以下验证码：',
        loginTitle: '新登录提醒',
        loginText: (n) => `您好，${n}！检测到新的账户登录：`,
        ip: 'IP 地址', device: '设备', time: '时间',
        loginWarn: '如果这不是您本人操作，请立即更改密码：',
        loginBtn: '管理账户',
        welcomeTitle: '欢迎！',
        welcomeText: (n) => `您好，${n}！您的账户已成功创建。`,
        feat1: '统一认证', feat2: 'API 密钥', feat3: '控制面板', feat4: '双因素认证',
        welcomeBtn: '打开控制面板',
        welcomeTip: '建议启用双因素认证以获得最高安全性。',
        resetTitle: '重置密码',
        resetText: (n) => `您好，${n}！我们收到了重置密码的请求：`,
        resetIgnore: '如果您未请求重置，请忽略此邮件。',
        resetWarn: '如果您未发起此请求，可能有人试图访问您的账户。',
        oauthTitle: 'OAuth 授权',
        oauthText: (n) => `您好，${n}！您已授权以下应用访问：`,
        app: '应用', scopes: '权限',
        oauthWarn: '如果这不是您本人操作，请立即撤销访问：',
        oauthBtn: '管理权限',
        keyTitle: '新 API 密钥',
        keyText: (n) => `您好，${n}！已创建新的 API 密钥：`,
        keyName: '名称',
        keyWarn: '密钥（sk）仅显示一次。如未保存，请创建新密钥。',
        entApprovedTitle: '企业申请已批准',
        entApprovedText: (n, c) => `您好，${n}！您的企业账户「${c}」申请已批准。`,
        entRejectedTitle: '企业申请已拒绝',
        entRejectedText: (n, c, r) => `您好，${n}！企业账户「${c}」申请已拒绝。${r ? ' 原因: ' + r : ''}`,
        entBtn: '打开控制面板',
        securityTitle: '安全提醒',
        securityText: (n, a) => `您好，${n}！您的账户执行了操作：${a}。`,
        securityBtn: '检查账户',
        magicTitle: '登录确认',
        magicText: (n) => `您好，${n}！点击下方按钮确认登录：`,
        magicBtn: '确认登录',
        magicWarn: '此链接有效期为10分钟。如果您未请求登录，请忽略此邮件。',
        deviceTitle: '新的可信设备',
        deviceText: (n) => `您好，${n}！新设备已添加到可信设备列表：`,
        deviceWarn: '如果这不是您本人操作，请立即更改密码并撤销访问。',
        deviceBtn: '管理设备',
    }
};

function s(lang) { return i18n[lang] || i18n.ru; }

// ===== STYLES (inline — Gmail strips <style> blocks; light design works in ALL clients) =====
const ST = {
    body:        'margin:0;padding:0;background-color:#f4f4f4;font-family:Arial,Helvetica,sans-serif;-webkit-text-size-adjust:100%;-ms-text-size-adjust:100%',
    outer:       'width:100%;background-color:#f4f4f4;padding:32px 0',
    wrap:        'margin:0 auto;padding:0 12px',
    card:        'background-color:#ffffff;border-radius:12px;overflow:hidden',
    head:        'background:#000000;padding:28px 32px 24px;text-align:center',
    headLogo:    'display:block;margin:0 auto',
    headLogoFallback: 'color:#ffffff;font-size:20px;font-weight:700;font-family:Arial,Helvetica,sans-serif;letter-spacing:0.5px;text-decoration:none',
    body_:       'background-color:#ffffff;padding:28px 32px 24px',
    foot:        'background-color:#fafafa;padding:18px 32px;text-align:center;border-top:1px solid #eeeeee',
    h1:          'margin:0 0 12px 0;color:#000000;font-size:22px;font-weight:700;font-family:Arial,Helvetica,sans-serif;line-height:1.3',
    p:           'margin:0 0 14px 0;color:#333333;font-size:15px;line-height:1.7;font-family:Arial,Helvetica,sans-serif',
    psmall:      'margin:0 0 10px 0;color:#666666;font-size:13px;line-height:1.6;font-family:Arial,Helvetica,sans-serif',
    codeOuter:   'margin:20px 0;border:2px solid #000000;border-radius:12px;overflow:hidden',
    codeInner:   'background-color:#fafafa;padding:24px 20px;text-align:center',
    codeLabel:   'color:#888888;font-size:11px;font-weight:700;font-family:Arial,Helvetica,sans-serif;letter-spacing:2px;text-transform:uppercase;margin-bottom:10px;display:block',
    codeVal:     'color:#000000;font-size:32px;font-weight:700;letter-spacing:8px;font-family:Courier New,Courier,monospace;line-height:1.2;display:block',
    codeExp:     'color:#999999;font-size:12px;margin-top:8px;display:block;font-family:Arial,Helvetica,sans-serif',
    btnTd:       'text-align:center;padding:20px 0 8px',
    btn:         'display:inline-block;background:#000000;color:#ffffff;text-decoration:none;padding:14px 40px;border-radius:8px;font-size:15px;font-weight:700;font-family:Arial,Helvetica,sans-serif',
    infoBox:     'margin:16px 0;border:1px solid #e0e0e0;border-radius:8px;overflow:hidden',
    infoRow:     'background-color:#fafafa;padding:10px 16px;border-bottom:1px solid #eeeeee',
    infoRowLast: 'background-color:#fafafa;padding:10px 16px',
    infoLabel:   'color:#888888;font-size:12px;font-family:Arial,Helvetica,sans-serif;display:inline-block',
    infoVal:     'color:#000000;font-size:12px;font-weight:600;font-family:Arial,Helvetica,sans-serif;float:right;max-width:60%;word-break:break-all',
    warn:        'background-color:#f5f5f5;border:1px solid #e0e0e0;border-radius:8px;padding:14px 16px;margin:18px 0',
    warnP:       'margin:0;color:#555555;font-size:12px;line-height:1.6;font-family:Arial,Helvetica,sans-serif',
    footP:       'margin:0;color:#999999;font-size:11px;line-height:1.8;font-family:Arial,Helvetica,sans-serif',
    footA:       'color:#555555;text-decoration:underline',
    pre:         'display:none;max-height:0;overflow:hidden;font-size:1px;line-height:1px;color:#f4f4f4;visibility:hidden',
};

// ===== INFO TABLE helper =====
function infoTable(rows) {
    const cells = rows.map((r, i) => {
        const style = i === rows.length - 1 ? ST.infoRowLast : ST.infoRow;
        return `<tr><td style="${style}"><span style="${ST.infoLabel}">${r[0]}</span><span style="${ST.infoVal}">${r[1]}</span><div style="clear:both"></div></td></tr>`;
    }).join('');
    return `<table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="${ST.infoBox}">${cells}</table>`;
}

// ===== BASE TEMPLATE (table-based, all inline CSS) =====
function baseTemplate(bodyHtml, preheaderText = '', plainText = '') {
    const html = `<!DOCTYPE html>
<html lang="ru" xmlns="http://www.w3.org/1999/xhtml">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<meta http-equiv="X-UA-Compatible" content="IE=edge">
<title>TOKEN PAY ID</title>
</head>
<body style="${ST.body}">
<div style="${ST.pre}">${_h(preheaderText)}&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;</div>
<table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="${ST.outer}">
<tr><td align="center">
  <!--[if (gte mso 9)|(IE)]><table role="presentation" cellspacing="0" cellpadding="0" border="0" width="600" align="center"><tr><td><![endif]-->
  <table role="presentation" cellspacing="0" cellpadding="0" border="0" style="width:100%;max-width:600px;${ST.wrap}">
  <tr><td>
    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="${ST.card}">
      <!-- GRADIENT HEADER -->
      <tr><td style="${ST.head}">
        <!--[if !mso]><!-->
        <a href="${SITE_URL}" style="text-decoration:none;display:block">
          <img src="${LOGO_URL}" alt="TOKEN PAY ID" width="160" height="38" style="display:block;width:160px;height:auto;max-width:160px;border:0;outline:none;margin:0 auto" onerror="this.style.display='none'" />
        </a>
        <!--<![endif]-->
        <!--[if mso]><a href="${SITE_URL}" style="${ST.headLogoFallback}">TOKEN PAY ID</a><![endif]-->
      </td></tr>
      <!-- BODY -->
      <tr><td style="${ST.body_}">${bodyHtml}</td></tr>
      <!-- FOOTER -->
      <tr><td style="${ST.foot}">
        <p style="${ST.footP}">&copy; ${YEAR} TOKEN PAY LLC&nbsp;&nbsp;&bull;&nbsp;&nbsp;<a href="${SITE_URL}" style="${ST.footA}">tokenpay.space</a>&nbsp;&nbsp;&bull;&nbsp;&nbsp;<a href="mailto:info@tokenpay.space" style="${ST.footA}">info@tokenpay.space</a></p>
      </td></tr>
    </table>
  </td></tr>
  </table>
  <!--[if (gte mso 9)|(IE)]></td></tr></table><![endif]-->
</td></tr>
</table>
</body>
</html>`;
    return { html, text: plainText };
}

// ===== TEMPLATES =====

function verificationCodeTemplate(name, code, expiresMin = 10, lang = 'ru') {
    const l = s(lang);
    const preheader = lang === 'en'
        ? `Your verification code is ready — TOKEN PAY ID`
        : `Ваш код подтверждения готов — TOKEN PAY ID`;
    const body = `
<h1 style="${ST.h1}">${l.verifyTitle}</h1>
<p style="${ST.p}">${l.hi(_h(name))}</p>
<p style="${ST.p}">${l.verifyText}</p>
<table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="${ST.codeOuter}">
<tr><td>
  <div style="${ST.codeInner}">
    <span style="${ST.codeLabel}">${lang === 'en' ? 'Verification Code' : 'Код подтверждения'}</span>
    <span style="${ST.codeVal}">${_h(String(code))}</span>
    <span style="${ST.codeExp}">${l.validFor(expiresMin)}</span>
  </div>
</td></tr>
</table>
<p style="${ST.p}">${l.ignoreIfNot}</p>
<table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="${ST.warn}"><tr><td><p style="${ST.warnP}">${l.doNotShare}</p></td></tr></table>`;
    const text = `${l.verifyTitle}\n\n${l.hi(name)}\n${l.verifyText}\n\n${code}\n\n${l.validFor(expiresMin)}\n\n${l.ignoreIfNot}\n${l.doNotShare}\n\n${SITE_URL}`;
    return baseTemplate(body, preheader, text);
}

function loginNotificationTemplate(name, ip, device, time, lang = 'ru') {
    const l = s(lang);
    const preheader = lang === 'en' ? `New sign-in detected — TOKEN PAY ID` : `Новый вход в аккаунт — TOKEN PAY ID`;
    const body = `
<h1 style="${ST.h1}">${l.loginTitle}</h1>
<p style="${ST.p}">${l.loginText(_h(name))}</p>
${infoTable([[l.ip, _h(ip)], [l.device, _h(device)], [l.time, _h(time)]])}
<p style="${ST.p}">${l.loginWarn}</p>
<table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%"><tr><td style="${ST.btnTd}"><a href="${SITE_URL}/dashboard" style="${ST.btn}">${l.loginBtn}</a></td></tr></table>`;
    const text = `${l.loginTitle}\n\n${l.loginText(name)}\n${l.ip}: ${ip}\n${l.device}: ${device}\n${l.time}: ${time}\n\n${l.loginWarn}\n${SITE_URL}/dashboard`;
    return baseTemplate(body, preheader, text);
}

function welcomeTemplate(name, lang = 'ru') {
    const l = s(lang);
    const preheader = lang === 'en' ? `Welcome to TOKEN PAY ID — your account is ready` : `Добро пожаловать в TOKEN PAY ID — аккаунт создан`;
    const body = `
<h1 style="${ST.h1}">${l.welcomeTitle}</h1>
<p style="${ST.p}">${l.welcomeText(_h(name))}</p>
${infoTable([['&#128274;', l.feat1], ['&#128273;', l.feat2], ['&#128202;', l.feat3], ['&#128737;', l.feat4]])}
<table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%"><tr><td style="${ST.btnTd}"><a href="${SITE_URL}/dashboard" style="${ST.btn}">${l.welcomeBtn}</a></td></tr></table>
<p style="${ST.p}">${l.welcomeTip}</p>`;
    const text = `${l.welcomeTitle}\n\n${l.welcomeText(name)}\n\n${l.feat1}, ${l.feat2}, ${l.feat3}, ${l.feat4}\n\n${l.welcomeTip}\n\n${SITE_URL}/dashboard`;
    return baseTemplate(body, preheader, text);
}

function passwordResetTemplate(name, code, expiresMin = 15, lang = 'ru') {
    const l = s(lang);
    const preheader = lang === 'en' ? `Password reset code — TOKEN PAY ID` : `Код сброса пароля — TOKEN PAY ID`;
    const body = `
<h1 style="${ST.h1}">${l.resetTitle}</h1>
<p style="${ST.p}">${l.resetText(_h(name))}</p>
<table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="${ST.codeOuter}">
<tr><td>
  <div style="${ST.codeInner}">
    <span style="${ST.codeLabel}">${lang === 'en' ? 'Reset Code' : 'Код сброса'}</span>
    <span style="${ST.codeVal}">${_h(String(code))}</span>
    <span style="${ST.codeExp}">${l.validFor(expiresMin)}</span>
  </div>
</td></tr>
</table>
<p style="${ST.p}">${l.resetIgnore}</p>
<table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="${ST.warn}"><tr><td><p style="${ST.warnP}">${l.resetWarn}</p></td></tr></table>`;
    const text = `${l.resetTitle}\n\n${l.resetText(name)}\n\n${code}\n\n${l.validFor(expiresMin)}\n\n${l.resetIgnore}\n${l.resetWarn}\n\n${SITE_URL}`;
    return baseTemplate(body, preheader, text);
}

function oauthApprovalTemplate(name, appName, scopes, time, lang = 'ru') {
    const l = s(lang);
    const preheader = lang === 'en' ? `OAuth access granted — TOKEN PAY ID` : `Доступ OAuth предоставлен — TOKEN PAY ID`;
    const body = `
<h1 style="${ST.h1}">${l.oauthTitle}</h1>
<p style="${ST.p}">${l.oauthText(_h(name))}</p>
${infoTable([[l.app, _h(appName)], [l.scopes, _h(scopes)], [l.time, _h(time)]])}
<p style="${ST.p}">${l.oauthWarn}</p>
<table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%"><tr><td style="${ST.btnTd}"><a href="${SITE_URL}/dashboard" style="${ST.btn}">${l.oauthBtn}</a></td></tr></table>`;
    const text = `${l.oauthTitle}\n\n${l.oauthText(name)}\n${l.app}: ${appName}\n${l.scopes}: ${scopes}\n${l.time}: ${time}\n\n${l.oauthWarn}\n${SITE_URL}/dashboard`;
    return baseTemplate(body, preheader, text);
}

function apiKeyCreatedTemplate(name, keyName, publicKey, lang = 'ru') {
    const l = s(lang);
    const preheader = lang === 'en' ? `New API key created — TOKEN PAY ID` : `Новый API ключ создан — TOKEN PAY ID`;
    const body = `
<h1 style="${ST.h1}">${l.keyTitle}</h1>
<p style="${ST.p}">${l.keyText(_h(name))}</p>
${infoTable([[l.keyName, _h(keyName)], ['Public Key', _h(publicKey)]])}
<table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="${ST.warn}"><tr><td><p style="${ST.warnP}">${l.keyWarn}</p></td></tr></table>`;
    const text = `${l.keyTitle}\n\n${l.keyText(name)}\n${l.keyName}: ${keyName}\nPublic Key: ${publicKey}\n\n${l.keyWarn}`;
    return baseTemplate(body, preheader, text);
}

function enterpriseApprovedTemplate(name, company, lang = 'ru') {
    const l = s(lang);
    const preheader = lang === 'en' ? `Enterprise application approved — TOKEN PAY ID` : `Корпоративная заявка одобрена — TOKEN PAY ID`;
    const body = `
<h1 style="${ST.h1}">${l.entApprovedTitle}</h1>
<p style="${ST.p}">${l.entApprovedText(_h(name), _h(company))}</p>
${infoTable([['&#127962;', _h(company)], ['&#128273;', 'API &amp; OAuth 2.0']])}
<table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%"><tr><td style="${ST.btnTd}"><a href="${SITE_URL}/dashboard" style="${ST.btn}">${l.entBtn}</a></td></tr></table>`;
    const text = `${l.entApprovedTitle}\n\n${l.entApprovedText(name, company)}\n\n${SITE_URL}/dashboard`;
    return baseTemplate(body, preheader, text);
}

function enterpriseRejectedTemplate(name, company, reason, lang = 'ru') {
    const l = s(lang);
    const body = `<h1 style="${ST.h1}">${l.entRejectedTitle}</h1><p style="${ST.p}">${l.entRejectedText(_h(name), _h(company), _h(reason))}</p>`;
    const text = `${l.entRejectedTitle}\n\n${l.entRejectedText(name, company, reason)}`;
    return baseTemplate(body, company, text);
}

function securityAlertTemplate(name, action, ip, lang = 'ru') {
    const l = s(lang);
    const preheader = lang === 'en' ? `Security alert on your account — TOKEN PAY ID` : `Уведомление безопасности аккаунта — TOKEN PAY ID`;
    const body = `
<h1 style="${ST.h1}">${l.securityTitle}</h1>
<p style="${ST.p}">${l.securityText(_h(name), _h(action))}</p>
${infoTable([[l.ip || 'IP', _h(ip)]])}
<table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%"><tr><td style="${ST.btnTd}"><a href="${SITE_URL}/dashboard" style="${ST.btn}">${l.securityBtn}</a></td></tr></table>`;
    const text = `${l.securityTitle}\n\n${l.securityText(name, action)}\nIP: ${ip}\n\n${SITE_URL}/dashboard`;
    return baseTemplate(body, preheader, text);
}

function magicLinkTemplate(name, magicUrl, ip, device, lang = 'ru') {
    const l = s(lang);
    const preheader = lang === 'en' ? `Confirm your sign-in — TOKEN PAY ID` : `Подтвердите вход — TOKEN PAY ID`;
    const body = `
<h1 style="${ST.h1}">${l.magicTitle}</h1>
<p style="${ST.p}">${l.magicText(_h(name))}</p>
${infoTable([[l.ip || 'IP', _h(ip)], [l.device || 'Устройство', _h(device)]])}
<table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%"><tr><td style="${ST.btnTd}"><a href="${_h(magicUrl)}" style="${ST.btn}">${l.magicBtn}</a></td></tr></table>
<table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="${ST.warn}"><tr><td><p style="${ST.warnP}">${l.magicWarn}</p></td></tr></table>`;
    const text = `${l.magicTitle}\n\n${l.magicText(name)}\n\n${magicUrl}\n\n${l.magicWarn}`;
    return baseTemplate(body, preheader, text);
}

function deviceTrustTemplate(name, device, ip, time, lang = 'ru') {
    const l = s(lang);
    const preheader = lang === 'en' ? `New trusted device — TOKEN PAY ID` : `Новое доверенное устройство — TOKEN PAY ID`;
    const body = `
<h1 style="${ST.h1}">${l.deviceTitle}</h1>
<p style="${ST.p}">${l.deviceText(_h(name))}</p>
${infoTable([[l.device || 'Устройство', _h(device)], [l.ip || 'IP', _h(ip)], [l.time || 'Время', _h(time)]])}
<p style="${ST.p}">${l.deviceWarn}</p>
<table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%"><tr><td style="${ST.btnTd}"><a href="${SITE_URL}/dashboard" style="${ST.btn}">${l.deviceBtn}</a></td></tr></table>`;
    const text = `${l.deviceTitle}\n\n${l.deviceText(name)}\n${device}\nIP: ${ip}\n${time}\n\n${l.deviceWarn}\n\n${SITE_URL}/dashboard`;
    return baseTemplate(body, preheader, text);
}

// ===== SEND — always multipart/alternative (text + html) =====
async function sendEmail(to, subject, tpl) {
    const html = tpl && tpl.html ? tpl.html : String(tpl || '');
    const text = tpl && tpl.text ? tpl.text : subject;
    if (!transporter) {
        console.log(`[EMAIL] (no SMTP) To: ${to} | Subject: ${subject}`);
        return { accepted: [to], messageId: 'console-' + Date.now() };
    }
    try {
        const msgId = `<${Date.now()}.${Math.random().toString(36).slice(2)}@tokenpay.space>`;
        const info = await transporter.sendMail({
            from: `"${FROM_NAME}" <${FROM_EMAIL}>`,
            to,
            subject,
            text,
            html,
            messageId: msgId,
            headers: {
                'X-Entity-Ref-ID': msgId,
            }
        });
        console.log(`[EMAIL] Sent to ${to}: ${info.messageId}`);
        return info;
    } catch (err) {
        console.error(`[EMAIL] Error sending to ${to}:`, err.message);
        throw err;
    }
}

// ===== ENTERPRISE ERROR ALERT TEMPLATE =====
function enterpriseErrorAlertTemplate(enterpriseName, errorType, errorMessage, endpoint, statusCode, ip, userAgent, timestamp, requestBody) {
    const body = `
<h1 style="${ST.h1}">\u26A0\uFE0F Enterprise Error Alert</h1>
<p style="${ST.p}">An error was reported by enterprise service <strong>${_h(enterpriseName)}</strong>:</p>
${infoTable([
    ['Enterprise', _h(enterpriseName)],
    ['Error Type', _h(errorType)],
    ['Endpoint', _h(endpoint || 'N/A')],
    ['Status Code', _h(String(statusCode || 'N/A'))],
    ['IP Address', _h(ip || 'N/A')],
    ['User-Agent', _h((userAgent || 'N/A').substring(0, 100))],
    ['Time', _h(timestamp)]
])}
<div style="${ST.warn}">
  <p style="${ST.warnP}"><strong>Error Message:</strong></p>
  <p style="${ST.warnP}">${_h(errorMessage || 'No message provided')}</p>
  ${requestBody ? '<p style="' + ST.warnP + '"><strong>Request Body:</strong> ' + _h(JSON.stringify(requestBody).substring(0, 500)) + '</p>' : ''}
</div>
<table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%"><tr><td style="${ST.btnTd}"><a href="${SITE_URL}/admin" style="${ST.btn}">Open Admin Panel</a></td></tr></table>`;
    const text = `Enterprise Error Alert\n\nEnterprise: ${enterpriseName}\nError: ${errorType} — ${errorMessage}\nEndpoint: ${endpoint}\nStatus: ${statusCode}\nIP: ${ip}\nTime: ${timestamp}`;
    return baseTemplate(body, `Enterprise Error: ${enterpriseName} — ${errorType}`, text);
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
        securityAlert: securityAlertTemplate,
        magicLink: magicLinkTemplate,
        deviceTrust: deviceTrustTemplate,
        enterpriseErrorAlert: enterpriseErrorAlertTemplate
    }
};
