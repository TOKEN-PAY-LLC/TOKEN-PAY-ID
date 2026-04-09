/* TOKEN PAY ID — OAuth Login Button Widget v2.0
 *
 * Two button types (like Google / Apple / Telegram login buttons):
 *
 * 1) ICON — round circle with TOKEN PAY icon
 *    <script src="https://tokenpay.space/sdk/tpid-auth.js"
 *            data-client-id="tpid_pk_..." data-redirect-uri="..."
 *            data-mode="icon" data-theme="dark" data-size="medium">
 *    </script>
 *
 * 2) LOGO — rectangular button with logo + text (default)
 *    <script src="https://tokenpay.space/sdk/tpid-auth.js"
 *            data-client-id="tpid_pk_..." data-redirect-uri="..."
 *            data-mode="logo" data-theme="dark" data-size="medium">
 *    </script>
 *
 * Attributes:
 *   data-client-id     (required) Public API key
 *   data-redirect-uri  (required) OAuth redirect URI
 *   data-mode          "icon" | "logo" (default: "logo")
 *   data-theme         "dark" | "light" | "auto" (default: "dark")
 *   data-lang          "ru" | "en" (default: "ru")
 *   data-size          "small" | "medium" | "large" (default: "medium")
 *   data-scope         OAuth scope (default: "openid email profile")
 *   data-container     ID of container element (optional)
 *   data-on-success    Global callback function name (optional)
 *
 * Events: window 'tpid:login' → detail = { code, state, type }
 *
 * Programmatic API:
 *   TokenPayAuth.init({ clientId, redirectUri, mode, theme, size, lang, scope, onSuccess, onError })
 *   TokenPayAuth.renderButton(selector, options)
 *   TokenPayAuth.startAuth()
 */
(function () {
    'use strict';

    var BASE = 'https://tokenpay.space';
    var VERSION = '2.0.0';

    // ─── Logo icon (use hosted image for consistent branding) ─────
    var ICON_IMG_URL = BASE + '/tokenpay-icon.png';
    var ICON_DARK_URL = BASE + '/hero-logo-black.png'; // solid black icon for light bg
    var ICON_LIGHT_URL = BASE + '/hero-logo-black.png'; // same file, inverted via CSS for dark bg

    // ─── Size constraints ──────────────────────────────────────────────────
    var SIZES = {
        icon: {
            small:  { w: 36,  h: 36,  iconSz: 18, radius: '50%' },
            medium: { w: 44,  h: 44,  iconSz: 22, radius: '50%' },
            large:  { w: 54,  h: 54,  iconSz: 26, radius: '50%' }
        },
        logo: {
            small:  { h: 36,  font: 12, pad: '0 14px', iconSz: 16, gap: 8,  radius: '8px',  minW: 180, maxW: 320 },
            medium: { h: 44,  font: 14, pad: '0 20px', iconSz: 20, gap: 10, radius: '10px', minW: 220, maxW: 400 },
            large:  { h: 54,  font: 16, pad: '0 28px', iconSz: 24, gap: 12, radius: '12px', minW: 260, maxW: 480 }
        }
    };

    // ─── Theme colors ──────────────────────────────────────────────────────
    var THEMES = {
        dark: {
            bg: '#ffffff', fg: '#0a0a0a', border: 'rgba(0,0,0,.08)',
            hoverBg: '#f0f0f0', shadow: '0 1px 3px rgba(0,0,0,.12), 0 1px 2px rgba(0,0,0,.08)',
            hoverShadow: '0 4px 12px rgba(0,0,0,.15)'
        },
        light: {
            bg: '#0a0a0a', fg: '#ffffff', border: 'rgba(255,255,255,.12)',
            hoverBg: '#1a1a1a', shadow: '0 1px 3px rgba(0,0,0,.3), 0 1px 2px rgba(0,0,0,.2)',
            hoverShadow: '0 4px 12px rgba(0,0,0,.4)'
        }
    };

    var LABELS = {
        ru: 'Войти через TOKEN PAY',
        en: 'Sign in with TOKEN PAY'
    };

    // ─── State ─────────────────────────────────────────────────────────────
    var _cfg = {};
    var _inited = false;

    // ─── PKCE helpers ──────────────────────────────────────────────────────
    function _randomBytes(len) {
        var arr = new Uint8Array(len);
        window.crypto.getRandomValues(arr);
        return btoa(String.fromCharCode.apply(null, arr))
            .replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '');
    }
    function _sha256b64url(str) {
        return window.crypto.subtle.digest('SHA-256', new TextEncoder().encode(str))
            .then(function (hash) {
                return btoa(String.fromCharCode.apply(null, new Uint8Array(hash)))
                    .replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '');
            });
    }

    // ─── Create icon (round) button ────────────────────────────────────────
    function _createIconButton(sz, theme) {
        var t = THEMES[theme] || THEMES.dark;
        var btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'tpid-btn-icon';
        btn.setAttribute('aria-label', 'TOKEN PAY ID');
        btn.style.cssText = [
            'display:inline-flex', 'align-items:center', 'justify-content:center',
            'width:' + sz.w + 'px', 'height:' + sz.h + 'px',
            'background:' + t.bg, 'color:' + t.fg,
            'border:1px solid ' + t.border, 'border-radius:' + sz.radius,
            'cursor:pointer', 'transition:all .2s ease',
            'box-shadow:' + t.shadow,
            'user-select:none', '-webkit-user-select:none', 'outline:none', 'padding:0'
        ].join(';');

        var isDarkBg = (theme === 'dark'); // dark theme = white bg, light theme = dark bg
        var iconImg = document.createElement('img');
        iconImg.src = ICON_DARK_URL;
        iconImg.alt = 'TOKEN PAY ID';
        iconImg.width = sz.iconSz;
        iconImg.height = sz.iconSz;
        iconImg.style.cssText = 'display:block;pointer-events:none;border-radius:3px' + (isDarkBg ? '' : ';filter:invert(1)');
        btn.appendChild(iconImg);

        btn.onmouseenter = function () { btn.style.background = t.hoverBg; btn.style.boxShadow = t.hoverShadow; btn.style.transform = 'translateY(-1px)'; };
        btn.onmouseleave = function () { btn.style.background = t.bg; btn.style.boxShadow = t.shadow; btn.style.transform = 'none'; };
        btn.onmousedown  = function () { btn.style.transform = 'scale(0.95)'; };
        btn.onmouseup    = function () { btn.style.transform = 'translateY(-1px)'; };

        return btn;
    }

    // ─── Create logo (rectangular) button ──────────────────────────────────
    function _createLogoButton(sz, theme, lang) {
        var t = THEMES[theme] || THEMES.dark;
        var label = LABELS[lang] || LABELS.ru;
        var btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'tpid-btn-logo';
        btn.setAttribute('aria-label', label);
        btn.style.cssText = [
            'display:inline-flex', 'align-items:center', 'justify-content:center',
            'gap:' + sz.gap + 'px',
            'height:' + sz.h + 'px', 'padding:' + sz.pad,
            'min-width:' + sz.minW + 'px', 'max-width:' + sz.maxW + 'px',
            'background:' + t.bg, 'color:' + t.fg,
            'border:1px solid ' + t.border, 'border-radius:' + sz.radius,
            'cursor:pointer', 'transition:all .2s ease',
            'box-shadow:' + t.shadow,
            'font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif',
            'font-size:' + sz.font + 'px', 'font-weight:600',
            'white-space:nowrap', 'text-decoration:none',
            'user-select:none', '-webkit-user-select:none', 'outline:none'
        ].join(';');

        var isDarkBg2 = (theme !== 'dark'); // THEMES.light has dark bg
        var iconImg = document.createElement('img');
        iconImg.src = ICON_DARK_URL;
        iconImg.alt = '';
        iconImg.width = sz.iconSz;
        iconImg.height = sz.iconSz;
        iconImg.style.cssText = 'display:block;pointer-events:none;flex-shrink:0;border-radius:3px' + (isDarkBg2 ? ';filter:invert(1)' : '');

        var span = document.createElement('span');
        span.textContent = label;
        span.style.cssText = 'pointer-events:none;line-height:1';

        btn.appendChild(iconImg);
        btn.appendChild(span);

        btn.onmouseenter = function () { btn.style.background = t.hoverBg; btn.style.boxShadow = t.hoverShadow; btn.style.transform = 'translateY(-1px)'; };
        btn.onmouseleave = function () { btn.style.background = t.bg; btn.style.boxShadow = t.shadow; btn.style.transform = 'none'; };
        btn.onmousedown  = function () { btn.style.transform = 'scale(0.98)'; };
        btn.onmouseup    = function () { btn.style.transform = 'translateY(-1px)'; };

        return btn;
    }

    // ─── Start OAuth flow ──────────────────────────────────────────────────
    function _startAuth(cfg) {
        var clientId = cfg.clientId;
        var redirectUri = cfg.redirectUri;
        var scope = cfg.scope || 'openid email profile';
        var onSuccessFn = cfg.onSuccess;
        var onErrorFn = cfg.onError;

        if (!clientId || !redirectUri) {
            console.error('[TPID] clientId and redirectUri are required');
            if (onErrorFn) onErrorFn({ error: 'missing_params' });
            return;
        }

        var verifier = _randomBytes(64);
        var state = _randomBytes(16);

        _sha256b64url(verifier).then(function (challenge) {
            sessionStorage.setItem('tpid_pkce_verifier', verifier);
            sessionStorage.setItem('tpid_oauth_state', state);

            var params = new URLSearchParams({
                response_type: 'code',
                client_id: clientId,
                redirect_uri: redirectUri,
                scope: scope,
                state: state,
                code_challenge: challenge,
                code_challenge_method: 'S256'
            });
            var authUrl = BASE + '/api/v1/oauth/authorize?' + params.toString();

            var W = 480, H = 640;
            var left = Math.round((screen.width - W) / 2);
            var top = Math.round((screen.height - H) / 2);
            var popup = window.open(authUrl, 'tpid_oauth',
                'width=' + W + ',height=' + H + ',left=' + left + ',top=' + top +
                ',toolbar=no,menubar=no,scrollbars=yes,resizable=yes');

            function onMsg(e) {
                if (e.origin !== BASE) return;
                if (!e.data || e.data.type !== 'tpid_oauth_code') return;
                window.removeEventListener('message', onMsg);
                if (popup && !popup.closed) popup.close();
                var detail = e.data;
                if (typeof onSuccessFn === 'function') {
                    onSuccessFn(detail);
                } else if (typeof onSuccessFn === 'string' && typeof window[onSuccessFn] === 'function') {
                    window[onSuccessFn](detail);
                } else {
                    window.dispatchEvent(new CustomEvent('tpid:login', { detail: detail }));
                }
            }
            window.addEventListener('message', onMsg);

            var poll = setInterval(function () {
                if (popup && popup.closed) {
                    clearInterval(poll);
                    window.removeEventListener('message', onMsg);
                }
            }, 800);
        });
    }

    // ─── Public API ────────────────────────────────────────────────────────
    var TokenPayAuth = {
        version: VERSION,

        init: function (cfg) {
            _cfg = cfg || {};
            _inited = true;
            if (_cfg.theme === 'auto') {
                _cfg.theme = (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) ? 'light' : 'dark';
            }
        },

        renderButton: function (selector, options) {
            var container = typeof selector === 'string' ? document.querySelector(selector) : selector;
            if (!container) { console.error('[TPID] Container not found:', selector); return; }

            var opts = Object.assign({}, _cfg, options || {});
            var mode = opts.mode || 'logo';
            var theme = opts.theme || 'dark';
            var size = opts.size || 'medium';
            var lang = opts.lang || 'ru';

            if (theme === 'auto') {
                theme = (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) ? 'light' : 'dark';
            }

            var sizeDef = (SIZES[mode] || SIZES.logo)[size] || (SIZES[mode] || SIZES.logo).medium;
            var btn;

            if (mode === 'icon') {
                btn = _createIconButton(sizeDef, theme);
            } else {
                btn = _createLogoButton(sizeDef, theme, lang);
            }

            btn.onclick = function () { _startAuth(opts); };
            container.innerHTML = '';
            container.appendChild(btn);
            return btn;
        },

        startAuth: function (overrides) {
            _startAuth(Object.assign({}, _cfg, overrides || {}));
        }
    };

    // ─── Auto-init from script tag attributes ──────────────────────────────
    (function () {
        var scripts = document.getElementsByTagName('script');
        var script = null;
        for (var i = 0; i < scripts.length; i++) {
            if (scripts[i].src && (scripts[i].src.indexOf('oauth-widget') !== -1 || scripts[i].src.indexOf('tpid-auth') !== -1)) {
                script = scripts[i]; break;
            }
        }
        if (!script) return;

        var clientId = script.getAttribute('data-client-id');
        var redirectUri = script.getAttribute('data-redirect-uri');
        if (!clientId || !redirectUri) return;

        var theme = script.getAttribute('data-theme') || 'dark';
        var lang = script.getAttribute('data-lang') || 'ru';
        var size = script.getAttribute('data-size') || 'medium';
        var mode = script.getAttribute('data-mode') || 'logo';
        var scope = script.getAttribute('data-scope') || 'openid email profile';
        var containerId = script.getAttribute('data-container') || '';
        var onSuccessFn = script.getAttribute('data-on-success') || '';

        if (theme === 'auto') {
            theme = (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) ? 'light' : 'dark';
        }

        var cfg = {
            clientId: clientId, redirectUri: redirectUri,
            theme: theme, lang: lang, size: size, mode: mode, scope: scope,
            onSuccess: onSuccessFn || undefined
        };

        TokenPayAuth.init(cfg);

        var container = containerId ? document.getElementById(containerId) : null;
        if (!container) {
            container = document.createElement('div');
            container.style.cssText = 'display:inline-block';
            script.parentNode.insertBefore(container, script.nextSibling);
        }

        TokenPayAuth.renderButton(container, cfg);
    })();

    window.TokenPayAuth = TokenPayAuth;
})();
