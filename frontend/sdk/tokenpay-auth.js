/**
 * TOKEN PAY ID — OAuth SDK v3.0
 * 
 * Usage:
 *   <script src="https://tokenpay.space/sdk/tokenpay-auth.js"></script>
 *   <div id="tokenpay-login"></div>
 *   <script>
 *     TokenPayAuth.init({
 *       clientId: 'tpid_pk_your_key',
 *       redirectUri: 'https://your-site.com/callback',
 *       scope: 'profile',
 *       onSuccess: function(data) { console.log('Code:', data.code); },
 *       onError: function(err) { console.error(err); }
 *     });
 *     TokenPayAuth.renderButton('#tokenpay-login');
 *   </script>
 *
 * PKCE (S256) is generated automatically.
 * code_verifier is saved in sessionStorage and accessible via TokenPayAuth.getCodeVerifier()
 *
 * Button variants: 'default' | 'filled' | 'outline' | 'minimal' | 'icon'
 * Locales: 'ru' | 'en' | 'zh'
 * Themes: 'dark' | 'light' | 'auto'
 */
(function(window) {
    'use strict';

    var TOKENPAY_BASE = 'https://tokenpay.space';
    var AUTHORIZE_URL = TOKENPAY_BASE + '/api/v1/oauth/authorize';
    var TOKEN_URL = TOKENPAY_BASE + '/api/v1/oauth/token';
    var USERINFO_URL = TOKENPAY_BASE + '/api/v1/oauth/userinfo';
    var VERIFIER_KEY = 'tpid_code_verifier';
    var STATE_KEY = 'tpid_oauth_state';

    var config = {};
    var popup = null;

    // ===== i18n =====
    var _labels = {
        ru: { btn: 'Войти через TOKEN PAY ID', btnShort: 'TOKEN PAY ID', aria: 'Войти через TOKEN PAY ID' },
        en: { btn: 'Sign in with TOKEN PAY ID', btnShort: 'TOKEN PAY ID', aria: 'Sign in with TOKEN PAY ID' },
        zh: { btn: '通过 TOKEN PAY ID 登录', btnShort: 'TOKEN PAY ID', aria: '通过 TOKEN PAY ID 登录' }
    };

    // ===== Logo (use hosted icon image for consistent branding) =====
    var _logoImgUrl = TOKENPAY_BASE + '/tokenpay-icon.png';
    var _iconBlackUrl = TOKENPAY_BASE + '/hero-logo-black.png';

    // ===== PKCE helpers =====
    function _generateVerifier() {
        var arr = new Uint8Array(32);
        (window.crypto || window.msCrypto).getRandomValues(arr);
        return _base64url(arr);
    }
    function _base64url(buf) {
        var str = '';
        for (var i = 0; i < buf.length; i++) str += String.fromCharCode(buf[i]);
        return btoa(str).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
    }
    async function _generateChallenge(verifier) {
        var enc = new TextEncoder();
        var digest = await (window.crypto || window.msCrypto).subtle.digest('SHA-256', enc.encode(verifier));
        return _base64url(new Uint8Array(digest));
    }

    // ===== Detect browser theme =====
    function _detectTheme() {
        return window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
    }

    // ===== Inject CSS keyframes once =====
    var _stylesInjected = false;
    function _injectStyles() {
        if (_stylesInjected) return;
        _stylesInjected = true;
        var style = document.createElement('style');
        style.textContent = [
            '@keyframes tpid-pulse{0%,100%{box-shadow:0 0 0 0 rgba(99,102,241,0.4)}70%{box-shadow:0 0 0 6px rgba(99,102,241,0)}}',
            '.tpid-btn{font-family:"Comfortaa",-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;box-sizing:border-box;cursor:pointer;outline:none;border:none;text-decoration:none;transition:all .2s cubic-bezier(.4,0,.2,1);position:relative;overflow:hidden}',
            '.tpid-btn:active{transform:scale(0.97)}',
            '.tpid-btn:focus-visible{outline:2px solid #6366f1;outline-offset:2px}',
            '.tpid-btn .tpid-ripple{position:absolute;border-radius:50%;background:rgba(255,255,255,0.3);transform:scale(0);animation:tpid-ripple .5s ease-out forwards;pointer-events:none}',
            '@keyframes tpid-ripple{to{transform:scale(3);opacity:0}}'
        ].join('\n');
        (document.head || document.documentElement).appendChild(style);
    }

    var TokenPayAuth = {
        version: '3.0.0',

        /**
         * Initialize SDK
         * @param {Object} opts
         * @param {string} opts.clientId — public API key (tpid_pk_...)
         * @param {string} opts.redirectUri — redirect URL after authorization
         * @param {string} [opts.scope='profile'] — requested permissions
         * @param {Function} [opts.onSuccess] — callback on success
         * @param {Function} [opts.onError] — callback on error
         * @param {string} [opts.locale='auto'] — locale ('ru'|'en'|'zh'|'auto')
         * @param {string} [opts.theme='auto'] — theme ('dark'|'light'|'auto')
         * @param {string} [opts.variant='default'] — button variant
         */
        init: function(opts) {
            if (!opts.clientId) throw new Error('TokenPayAuth: clientId is required');
            if (!opts.redirectUri) throw new Error('TokenPayAuth: redirectUri is required');

            var autoLocale = 'ru';
            try {
                var nav = (navigator.language || '').toLowerCase();
                if (nav.startsWith('zh')) autoLocale = 'zh';
                else if (nav.startsWith('en')) autoLocale = 'en';
            } catch(e) {}

            config = {
                clientId: opts.clientId,
                redirectUri: opts.redirectUri,
                scope: opts.scope || 'profile',
                onSuccess: opts.onSuccess || function() {},
                onError: opts.onError || function() {},
                locale: (opts.locale && opts.locale !== 'auto') ? opts.locale : autoLocale,
                theme: (opts.theme && opts.theme !== 'auto') ? opts.theme : _detectTheme(),
                variant: opts.variant || 'default'
            };

            window.addEventListener('message', function(e) {
                if (e.origin !== TOKENPAY_BASE) return;
                var d = e.data;
                if (!d) return;
                if (d.type === 'tokenpay_auth_code' || d.type === 'tpid_oauth_code' || d.type === 'tpid_callback') {
                    if (d.error) {
                        config.onError({ error: d.error, description: d.description || d.error_description });
                    } else {
                        var code = d.code || (d.payload && d.payload.code);
                        var st = d.state || (d.payload && d.payload.state);
                        var savedState = sessionStorage.getItem(STATE_KEY);
                        if (savedState && st !== savedState) {
                            config.onError({ error: 'state_mismatch', description: 'CSRF state mismatch' });
                        } else {
                            config.onSuccess({ code: code, state: st, codeVerifier: sessionStorage.getItem(VERIFIER_KEY) });
                        }
                    }
                    if (popup) { try { popup.close(); } catch(ex) {} popup = null; }
                }
                if (d.type === 'tokenpay_auth_error') {
                    config.onError({ error: d.error, description: d.description });
                    if (popup) { try { popup.close(); } catch(ex) {} popup = null; }
                }
            });
        },

        /**
         * Start authorization (open popup) — PKCE generated automatically
         */
        authorize: async function(customState) {
            var state = customState || Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);
            sessionStorage.setItem(STATE_KEY, state);

            var verifier = _generateVerifier();
            sessionStorage.setItem(VERIFIER_KEY, verifier);
            var challenge = await _generateChallenge(verifier);

            var url = AUTHORIZE_URL +
                '?response_type=code' +
                '&client_id=' + encodeURIComponent(config.clientId) +
                '&redirect_uri=' + encodeURIComponent(config.redirectUri) +
                '&scope=' + encodeURIComponent(config.scope) +
                '&state=' + encodeURIComponent(state) +
                '&code_challenge=' + encodeURIComponent(challenge) +
                '&code_challenge_method=S256';

            var w = 480, h = 640;
            var left = (screen.width - w) / 2;
            var top = (screen.height - h) / 2;
            popup = window.open(url, 'tokenpay_auth',
                'width=' + w + ',height=' + h + ',left=' + left + ',top=' + top + ',toolbar=no,menubar=no,scrollbars=yes');

            if (!popup) {
                window.location.href = url;
                return;
            }

            var pollTimer = setInterval(function() {
                if (!popup || popup.closed) {
                    clearInterval(pollTimer);
                    popup = null;
                }
            }, 500);
        },

        getCodeVerifier: function() {
            return sessionStorage.getItem(VERIFIER_KEY);
        },

        exchangeCode: async function(code, clientSecret) {
            var body = {
                grant_type: 'authorization_code',
                code: code,
                client_id: config.clientId,
                redirect_uri: config.redirectUri
            };
            var verifier = sessionStorage.getItem(VERIFIER_KEY);
            if (verifier) body.code_verifier = verifier;
            if (clientSecret) body.client_secret = clientSecret;
            var resp = await fetch(TOKEN_URL, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });
            return resp.json();
        },

        getUserInfo: async function(accessToken) {
            var resp = await fetch(USERINFO_URL, {
                headers: { 'Authorization': 'Bearer ' + accessToken }
            });
            return resp.json();
        },

        /**
         * Render "Sign in with TOKEN PAY ID" button
         * @param {string|HTMLElement} container — CSS selector or DOM element
         * @param {Object} [opts] — override settings
         * @param {string} [opts.variant] — 'default'|'filled'|'outline'|'minimal'|'icon'
         * @param {string} [opts.width] — CSS width (e.g. '100%', '300px')
         * @param {string} [opts.locale] — 'ru'|'en'|'zh'
         * @param {string} [opts.theme] — 'dark'|'light'
         */
        renderButton: function(container, opts) {
            _injectStyles();

            var el = typeof container === 'string' ? document.querySelector(container) : container;
            if (!el) { console.error('TokenPayAuth: container not found'); return null; }

            var o = {};
            for (var k in config) o[k] = config[k];
            if (opts) { for (var k2 in opts) o[k2] = opts[k2]; }

            var loc = _labels[o.locale] || _labels.ru;
            var isDark = o.theme === 'dark';
            var variant = o.variant || 'default';

            var btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'tpid-btn';
            btn.setAttribute('aria-label', loc.aria);

            // ===== VARIANT STYLES =====
            var styles = {};

            if (variant === 'icon') {
                // Compact circle icon button
                styles = {
                    display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                    width: '48px', height: '48px', padding: '0',
                    borderRadius: '50%',
                    background: isDark ? '#ffffff' : '#111111',
                    color: isDark ? '#111111' : '#ffffff',
                    boxShadow: '0 2px 8px rgba(0,0,0,0.15)'
                };
            } else if (variant === 'filled') {
                // Solid dark/light filled button
                styles = {
                    display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                    gap: '10px', height: '52px', padding: '0 32px',
                    borderRadius: '14px',
                    background: isDark ? '#ffffff' : '#111111',
                    color: isDark ? '#111111' : '#ffffff',
                    fontSize: '15px', fontWeight: '700',
                    letterSpacing: '0.8px', lineHeight: '1',
                    whiteSpace: 'nowrap',
                    boxShadow: '0 2px 12px rgba(0,0,0,0.12)'
                };
            } else if (variant === 'outline') {
                // Transparent with border
                styles = {
                    display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                    gap: '10px', height: '52px', padding: '0 32px',
                    borderRadius: '14px',
                    background: 'transparent',
                    border: isDark ? '2px solid rgba(255,255,255,0.25)' : '2px solid rgba(0,0,0,0.15)',
                    color: isDark ? '#ffffff' : '#111111',
                    fontSize: '15px', fontWeight: '700',
                    letterSpacing: '0.8px', lineHeight: '1',
                    whiteSpace: 'nowrap',
                    backdropFilter: 'blur(8px)',
                    WebkitBackdropFilter: 'blur(8px)'
                };
            } else if (variant === 'minimal') {
                // Text-only, no bg
                styles = {
                    display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                    gap: '8px', height: '44px', padding: '0 16px',
                    borderRadius: '10px',
                    background: 'transparent',
                    color: isDark ? '#ffffff' : '#111111',
                    fontSize: '14px', fontWeight: '600',
                    letterSpacing: '0.5px', lineHeight: '1',
                    whiteSpace: 'nowrap'
                };
            } else {
                // DEFAULT — the premium button (like cupol.space reference)
                styles = {
                    display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                    gap: '10px', height: '52px', padding: '0 36px',
                    borderRadius: '14px',
                    background: isDark ? '#ffffff' : '#111111',
                    color: isDark ? '#111111' : '#ffffff',
                    fontSize: '15px', fontWeight: '800',
                    letterSpacing: '1.2px', lineHeight: '1',
                    whiteSpace: 'nowrap',
                    boxShadow: isDark
                        ? '0 4px 20px rgba(255,255,255,0.08), 0 1px 3px rgba(255,255,255,0.06)'
                        : '0 4px 20px rgba(0,0,0,0.10), 0 1px 3px rgba(0,0,0,0.06)',
                    textTransform: 'uppercase'
                };
            }

            if (o.width) styles.width = o.width;

            for (var s in styles) btn.style[s] = styles[s];

            // ===== LOGO ICON =====
            if (variant !== 'icon') {
                var logoImg = document.createElement('img');
                var iconSize = variant === 'minimal' ? 16 : variant === 'filled' ? 18 : 20;
                logoImg.src = _iconBlackUrl;
                logoImg.alt = '';
                logoImg.width = iconSize;
                logoImg.height = iconSize;
                // For outline/minimal (transparent bg): icon matches text (isDark=white→invert, !isDark=black→no)
                // For default/filled (solid bg): icon contrasts bg (isDark=white bg→no invert, !isDark=dark bg→invert)
                var needsInvert = (variant === 'outline' || variant === 'minimal') ? isDark : !isDark;
                var logoFilter = needsInvert ? 'filter:invert(1);' : '';
                logoImg.style.cssText = 'flex-shrink:0;display:block;border-radius:3px;' + logoFilter;
                btn.appendChild(logoImg);

                var label = document.createElement('span');
                label.textContent = (variant === 'minimal') ? loc.btnShort : loc.btn;
                label.style.pointerEvents = 'none';
                btn.appendChild(label);
            } else {
                // Icon variant: use solid black icon, invert for dark bg
                var logoImg2 = document.createElement('img');
                logoImg2.src = _iconBlackUrl;
                logoImg2.alt = 'TOKEN PAY ID';
                logoImg2.width = 22;
                logoImg2.height = 22;
                var iconFilter = isDark ? '' : 'filter:invert(1);'; // isDark=white bg (no filter), !isDark=dark bg (invert)
                logoImg2.style.cssText = 'display:block;border-radius:3px;' + iconFilter;
                btn.appendChild(logoImg2);
            }

            // ===== HOVER EFFECTS =====
            var hoverBg, defaultBg;
            if (variant === 'default' || variant === 'filled') {
                defaultBg = isDark ? '#ffffff' : '#111111';
                hoverBg = isDark ? '#e8e8e8' : '#2a2a2a';
            } else if (variant === 'outline') {
                defaultBg = 'transparent';
                hoverBg = isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.04)';
            } else if (variant === 'minimal') {
                defaultBg = 'transparent';
                hoverBg = isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.04)';
            } else if (variant === 'icon') {
                defaultBg = isDark ? '#ffffff' : '#111111';
                hoverBg = isDark ? '#e8e8e8' : '#2a2a2a';
            }

            btn.addEventListener('mouseenter', function() {
                btn.style.background = hoverBg;
                btn.style.transform = 'translateY(-1px)';
                if (variant === 'default' || variant === 'filled') {
                    btn.style.boxShadow = isDark
                        ? '0 6px 28px rgba(255,255,255,0.12)'
                        : '0 6px 28px rgba(0,0,0,0.15)';
                }
            });
            btn.addEventListener('mouseleave', function() {
                btn.style.background = defaultBg;
                btn.style.transform = 'translateY(0)';
                if (variant === 'default' || variant === 'filled') {
                    btn.style.boxShadow = styles.boxShadow || 'none';
                }
            });

            // Ripple effect on click
            btn.addEventListener('click', function(e) {
                var rect = btn.getBoundingClientRect();
                var ripple = document.createElement('span');
                ripple.className = 'tpid-ripple';
                var size = Math.max(rect.width, rect.height);
                ripple.style.width = ripple.style.height = size + 'px';
                ripple.style.left = (e.clientX - rect.left - size / 2) + 'px';
                ripple.style.top = (e.clientY - rect.top - size / 2) + 'px';
                btn.appendChild(ripple);
                setTimeout(function() { ripple.remove(); }, 600);
                TokenPayAuth.authorize();
            });

            el.appendChild(btn);
            return btn;
        },

        /**
         * Report an error to TOKEN PAY ID monitoring
         * @param {Object} errorData — { error_type, error_message, endpoint, status_code, metadata }
         * @param {string} apiKey — enterprise API key (Authorization: Bearer ...)
         */
        reportError: async function(errorData, apiKey) {
            if (!apiKey || !errorData) return;
            try {
                await fetch(TOKENPAY_BASE + '/api/v1/enterprise/errors', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': 'Bearer ' + apiKey
                    },
                    body: JSON.stringify(errorData)
                });
            } catch(e) { /* silent — don't crash the host app */ }
        }
    };

    window.TokenPayAuth = TokenPayAuth;

})(window);
