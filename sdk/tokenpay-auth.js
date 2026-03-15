/**
 * TOKEN PAY ID — OAuth SDK v1.0
 * 
 * Использование:
 *   <script src="https://tokenpay.space/sdk/tokenpay-auth.js"></script>
 *   <div id="tokenpay-login"></div>
 *   <script>
 *     TokenPayAuth.init({
 *       clientId: 'tpid_pk_ваш_ключ',
 *       redirectUri: 'https://ваш-сайт.com/callback',
 *       scope: 'profile',
 *       onSuccess: function(data) { console.log('Код:', data.code); },
 *       onError: function(err) { console.error(err); }
 *     });
 *     TokenPayAuth.renderButton('#tokenpay-login');
 *   </script>
 */
(function(window) {
    'use strict';

    const TOKENPAY_BASE = 'https://tokenpay.space';
    const AUTHORIZE_URL = TOKENPAY_BASE + '/api/v1/oauth/authorize';
    const TOKEN_URL = TOKENPAY_BASE + '/api/v1/oauth/token';
    const USERINFO_URL = TOKENPAY_BASE + '/api/v1/oauth/userinfo';

    let config = {};
    let popup = null;

    const TokenPayAuth = {
        /**
         * Инициализация SDK
         * @param {Object} opts
         * @param {string} opts.clientId — публичный ключ API (tpid_pk_...)
         * @param {string} opts.redirectUri — URL для редиректа после авторизации
         * @param {string} [opts.scope='profile'] — запрашиваемые разрешения
         * @param {Function} [opts.onSuccess] — callback при успешной авторизации
         * @param {Function} [opts.onError] — callback при ошибке
         * @param {string} [opts.locale='ru'] — язык кнопки ('ru' | 'en')
         * @param {string} [opts.theme='dark'] — тема ('dark' | 'light')
         * @param {string} [opts.size='large'] — размер ('small' | 'medium' | 'large')
         */
        init: function(opts) {
            if (!opts.clientId) throw new Error('TokenPayAuth: clientId обязателен');
            if (!opts.redirectUri) throw new Error('TokenPayAuth: redirectUri обязателен');
            // Auto-detect theme from browser if not specified
            const autoTheme = window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
            config = {
                clientId: opts.clientId,
                redirectUri: opts.redirectUri,
                scope: opts.scope || 'profile',
                onSuccess: opts.onSuccess || function() {},
                onError: opts.onError || function() {},
                locale: opts.locale || 'ru',
                theme: opts.theme || autoTheme,
                size: opts.size || 'large'
            };

            // Listen for postMessage from popup/redirect
            window.addEventListener('message', function(e) {
                if (e.origin !== TOKENPAY_BASE) return;
                if (e.data && e.data.type === 'tokenpay_auth_code') {
                    config.onSuccess({ code: e.data.code, state: e.data.state });
                    if (popup) popup.close();
                }
                if (e.data && e.data.type === 'tokenpay_auth_error') {
                    config.onError({ error: e.data.error, description: e.data.description });
                    if (popup) popup.close();
                }
            });
        },

        /**
         * Начать авторизацию (открыть popup)
         */
        authorize: function(customState) {
            const state = customState || Math.random().toString(36).substring(2, 15);
            const url = AUTHORIZE_URL +
                '?response_type=code' +
                '&client_id=' + encodeURIComponent(config.clientId) +
                '&redirect_uri=' + encodeURIComponent(config.redirectUri) +
                '&scope=' + encodeURIComponent(config.scope) +
                '&state=' + encodeURIComponent(state);

            const w = 480, h = 640;
            const left = (screen.width - w) / 2;
            const top = (screen.height - h) / 2;
            popup = window.open(url, 'tokenpay_auth', 
                `width=${w},height=${h},left=${left},top=${top},toolbar=no,menubar=no,scrollbars=yes`);
            
            if (!popup) {
                // Popup blocked — redirect instead
                window.location.href = url;
            }
        },

        /**
         * Обменять код на токен (серверная сторона, но можно и из JS для тестов)
         */
        exchangeCode: async function(code, clientSecret) {
            const resp = await fetch(TOKEN_URL, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    grant_type: 'authorization_code',
                    code: code,
                    client_id: config.clientId,
                    client_secret: clientSecret,
                    redirect_uri: config.redirectUri
                })
            });
            return resp.json();
        },

        /**
         * Получить информацию о пользователе по access_token
         */
        getUserInfo: async function(accessToken) {
            const resp = await fetch(USERINFO_URL, {
                headers: { 'Authorization': 'Bearer ' + accessToken }
            });
            return resp.json();
        },

        /**
         * Отрисовать кнопку "Войти через TOKEN PAY"
         * @param {string|HTMLElement} container — CSS-селектор или DOM-элемент
         * @param {Object} [opts] — переопределение настроек
         */
        renderButton: function(container, opts) {
            const el = typeof container === 'string' ? document.querySelector(container) : container;
            if (!el) { console.error('TokenPayAuth: контейнер не найден'); return; }

            const o = Object.assign({}, config, opts || {});
            const isRu = o.locale === 'ru';
            const isDark = o.theme === 'dark';
            const mode = o.mode || 'button'; // 'button' | 'icon'

            const btn = document.createElement('button');
            btn.type = 'button';
            btn.setAttribute('aria-label', isRu ? 'Войти через TOKEN PAY' : 'Sign in with TOKEN PAY');

            if (mode === 'icon') {
                // Compact icon-only mode (like Google/Yandex one-tap)
                Object.assign(btn.style, {
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    width: '40px', height: '40px', padding: '0',
                    border: isDark ? '1px solid #333' : '1px solid #ddd',
                    borderRadius: '50%', background: isDark ? '#111' : '#fff',
                    cursor: 'pointer', transition: 'all .15s ease', outline: 'none'
                });
                const img = document.createElement('img');
                img.src = TOKENPAY_BASE + '/tokenpay-icon.jpg';
                img.alt = 'TOKEN PAY';
                Object.assign(img.style, {
                    width: '28px', height: '28px', borderRadius: '50%',
                    pointerEvents: 'none', userSelect: 'none'
                });
                btn.appendChild(img);
            } else {
                // Standard button mode — compact, no scroll
                Object.assign(btn.style, {
                    display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                    gap: '8px', height: '40px', padding: '0 16px',
                    border: isDark ? '1px solid #333' : '1px solid #ddd',
                    borderRadius: '8px', background: isDark ? '#111' : '#fff',
                    color: isDark ? '#fff' : '#111',
                    fontFamily: "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif",
                    fontSize: '13px', fontWeight: '500', letterSpacing: '0',
                    cursor: 'pointer', transition: 'all .15s ease',
                    outline: 'none', lineHeight: '1', whiteSpace: 'nowrap'
                });
                const img = document.createElement('img');
                img.src = TOKENPAY_BASE + '/tokenpay-icon.jpg';
                img.alt = '';
                Object.assign(img.style, {
                    width: '20px', height: '20px', borderRadius: '50%',
                    pointerEvents: 'none', userSelect: 'none', flexShrink: '0'
                });
                const label = document.createElement('span');
                label.textContent = isRu ? 'TOKEN PAY' : 'TOKEN PAY';
                btn.appendChild(img);
                btn.appendChild(label);
            }

            btn.addEventListener('mouseenter', function() {
                btn.style.background = isDark ? '#1a1a1a' : '#f5f5f5';
                btn.style.borderColor = isDark ? '#555' : '#bbb';
                btn.style.transform = 'scale(1.02)';
            });
            btn.addEventListener('mouseleave', function() {
                btn.style.background = isDark ? '#111' : '#fff';
                btn.style.borderColor = isDark ? '#333' : '#ddd';
                btn.style.transform = 'scale(1)';
            });

            btn.addEventListener('click', function() {
                TokenPayAuth.authorize();
            });

            el.appendChild(btn);
            return btn;
        }
    };

    // Expose globally
    window.TokenPayAuth = TokenPayAuth;

})(window);
