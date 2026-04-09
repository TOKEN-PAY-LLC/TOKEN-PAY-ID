/**
 * TOKEN PAY ID — Widget SDK v1.2.0
 * 
 * Быстрый старт (1 строка):
 *   <script src="https://tokenpay.space/sdk/tpid-widget.js" data-client-id="tpid_pk_..."></script>
 *
 * Или с контейнерами:
 *   <div data-tpid-button="standard"></div>
 *   <div data-tpid-button="icon"></div>
 *   <div data-tpid-button="logo"></div>
 *
 * Программный API:
 *   TPID.init({ clientId: '...', redirectUri: '...', onSuccess: fn, onError: fn });
 *   TPID.loginWithOAuth({ prompt: 'login' }).then(result => { ... });
 *   TPID.renderButton(el, opts);
 *   TPID.renderIconButton(el, opts);
 *   TPID.renderLogoButton(el, opts);
 *
 * PKCE (S256) генерируется автоматически.
 */
(function(window, document) {
    'use strict';

    var BASE = 'https://tokenpay.space';
    var AUTH_URL = BASE + '/api/v1/oauth/authorize';
    var VK = 'tpid_wdg_verifier';
    var SK = 'tpid_wdg_state';
    var version = '1.2.0';

    var cfg = {};
    var _popup = null;
    var _resolve = null;
    var _reject = null;

    // ===== PKCE =====
    function _b64u(buf) {
        var s = '';
        for (var i = 0; i < buf.length; i++) s += String.fromCharCode(buf[i]);
        return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
    }
    function _genVerifier() {
        var a = new Uint8Array(32);
        (window.crypto || window.msCrypto).getRandomValues(a);
        return _b64u(a);
    }
    function _genChallenge(v) {
        return (window.crypto || window.msCrypto).subtle.digest('SHA-256', new TextEncoder().encode(v))
            .then(function(d) { return _b64u(new Uint8Array(d)); });
    }
    function _genState() {
        return Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);
    }

    // ===== Shield SVG icon =====
    var SHIELD_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" style="width:1em;height:1em;vertical-align:middle;flex-shrink:0"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>';

    // ===== PostMessage listener =====
    function _onMessage(e) {
        if (e.origin !== BASE) return;
        var d = e.data;
        if (!d) return;
        if (d.type === 'tokenpay_auth_code' || d.type === 'tpid_oauth_code' || d.type === 'tpid_callback') {
            var code = d.code || (d.payload && d.payload.code);
            var st = d.state || (d.payload && d.payload.state);
            var savedState = sessionStorage.getItem(SK);
            if (d.error) {
                var err = { error: d.error, description: d.description || d.error_description };
                if (cfg.onError) cfg.onError(err);
                if (_reject) { _reject(err); _reject = null; _resolve = null; }
            } else if (savedState && st !== savedState) {
                var mismatch = { error: 'state_mismatch', description: 'CSRF state mismatch' };
                if (cfg.onError) cfg.onError(mismatch);
                if (_reject) { _reject(mismatch); _reject = null; _resolve = null; }
            } else {
                var result = { code: code, state: st, codeVerifier: sessionStorage.getItem(VK) };
                if (cfg.onSuccess) cfg.onSuccess(result);
                if (_resolve) { _resolve(result); _resolve = null; _reject = null; }
            }
            if (_popup) { try { _popup.close(); } catch(x) {} _popup = null; }
        }
        if (d.type === 'tokenpay_auth_error') {
            var e2 = { error: d.error, description: d.description };
            if (cfg.onError) cfg.onError(e2);
            if (_reject) { _reject(e2); _reject = null; _resolve = null; }
            if (_popup) { try { _popup.close(); } catch(x) {} _popup = null; }
        }
    }
    window.addEventListener('message', _onMessage);

    // ===== Core authorize =====
    function _authorize(opts) {
        opts = opts || {};
        var state = opts.state || _genState();
        sessionStorage.setItem(SK, state);
        var verifier = _genVerifier();
        sessionStorage.setItem(VK, verifier);

        return _genChallenge(verifier).then(function(challenge) {
            var url = AUTH_URL +
                '?response_type=code' +
                '&client_id=' + encodeURIComponent(cfg.clientId) +
                '&redirect_uri=' + encodeURIComponent(cfg.redirectUri || window.location.origin + '/callback') +
                '&scope=' + encodeURIComponent(cfg.scope || 'openid profile email') +
                '&state=' + encodeURIComponent(state) +
                '&code_challenge=' + encodeURIComponent(challenge) +
                '&code_challenge_method=S256';
            if (opts.prompt) url += '&prompt=' + encodeURIComponent(opts.prompt);
            if (opts.login_hint) url += '&login_hint=' + encodeURIComponent(opts.login_hint);

            var w = 480, h = 640;
            var left = (screen.width - w) / 2, top = (screen.height - h) / 2;
            _popup = window.open(url, 'tpid_auth',
                'width=' + w + ',height=' + h + ',left=' + left + ',top=' + top + ',toolbar=no,menubar=no,scrollbars=yes');
            if (!_popup) {
                window.location.href = url;
            } else {
                var t = setInterval(function() {
                    if (!_popup || _popup.closed) { clearInterval(t); _popup = null; }
                }, 500);
            }
        });
    }

    // ===== Button factory =====
    function _sizes(size) {
        if (size === 'small') return { h: 36, icon: 20, font: 12, pad: 12 };
        if (size === 'large') return { h: 54, icon: 28, font: 15, pad: 20 };
        return { h: 44, icon: 24, font: 13, pad: 16 }; // medium
    }

    function _createStandardBtn(container, opts) {
        var el = typeof container === 'string' ? document.querySelector(container) : container;
        if (!el) return null;
        var o = Object.assign({}, cfg, opts || {});
        var dark = o.theme === 'dark' || (o.theme === 'auto' && window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches);
        var isRu = (o.lang || o.locale || 'ru') === 'ru';
        var s = _sizes(o.size);

        var btn = document.createElement('button');
        btn.type = 'button';
        btn.setAttribute('aria-label', isRu ? 'Войти через TOKEN PAY ID' : 'Sign in with TOKEN PAY ID');
        Object.assign(btn.style, {
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            gap: '8px', height: s.h + 'px', padding: '0 ' + s.pad + 'px',
            border: dark ? '1px solid #333' : '1px solid #ddd',
            borderRadius: '8px', background: dark ? '#111' : '#fff',
            color: dark ? '#fff' : '#111',
            fontFamily: "'Comfortaa',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif",
            fontSize: s.font + 'px', fontWeight: '600', letterSpacing: '0.5px',
            cursor: 'pointer', transition: 'all .15s ease',
            outline: 'none', lineHeight: '1', whiteSpace: 'nowrap'
        });
        var img = document.createElement('img');
        img.src = BASE + '/hero-logo-black.png';
        img.alt = '';
        Object.assign(img.style, { width: s.icon + 'px', height: s.icon + 'px', borderRadius: '50%', pointerEvents: 'none', userSelect: 'none', flexShrink: '0', filter: dark ? 'invert(1)' : 'none' });
        var label = document.createElement('span');
        label.textContent = isRu ? 'Войти через TOKEN PAY' : 'Sign in with TOKEN PAY';
        btn.appendChild(img);
        btn.appendChild(label);

        btn.onmouseenter = function() { btn.style.background = dark ? '#1a1a1a' : '#f5f5f5'; btn.style.borderColor = dark ? '#555' : '#bbb'; btn.style.transform = 'scale(1.02)'; };
        btn.onmouseleave = function() { btn.style.background = dark ? '#111' : '#fff'; btn.style.borderColor = dark ? '#333' : '#ddd'; btn.style.transform = 'scale(1)'; };
        btn.onclick = function() { _authorize(); };

        el.appendChild(btn);
        return btn;
    }

    function _createIconBtn(container, opts) {
        var el = typeof container === 'string' ? document.querySelector(container) : container;
        if (!el) return null;
        var o = Object.assign({}, cfg, opts || {});
        var dark = o.theme === 'dark' || (o.theme === 'auto' && window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches);
        var s = _sizes(o.size);

        var btn = document.createElement('button');
        btn.type = 'button';
        btn.setAttribute('aria-label', 'TOKEN PAY ID');
        Object.assign(btn.style, {
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            width: s.h + 'px', height: s.h + 'px', padding: '0',
            border: dark ? '1px solid #333' : '1px solid #ddd',
            borderRadius: '50%', background: dark ? '#111' : '#fff',
            cursor: 'pointer', transition: 'all .15s ease', outline: 'none'
        });
        var img = document.createElement('img');
        img.src = BASE + '/hero-logo-black.png';
        img.alt = 'TOKEN PAY ID';
        Object.assign(img.style, { width: (s.icon + 4) + 'px', height: (s.icon + 4) + 'px', borderRadius: '50%', pointerEvents: 'none', userSelect: 'none', filter: dark ? 'invert(1)' : 'none' });
        btn.appendChild(img);

        btn.onmouseenter = function() { btn.style.background = dark ? '#1a1a1a' : '#f5f5f5'; btn.style.borderColor = dark ? '#555' : '#bbb'; btn.style.transform = 'scale(1.05)'; };
        btn.onmouseleave = function() { btn.style.background = dark ? '#111' : '#fff'; btn.style.borderColor = dark ? '#333' : '#ddd'; btn.style.transform = 'scale(1)'; };
        btn.onclick = function() { _authorize(); };

        el.appendChild(btn);
        return btn;
    }

    function _createLogoBtn(container, opts) {
        var el = typeof container === 'string' ? document.querySelector(container) : container;
        if (!el) return null;
        var o = Object.assign({}, cfg, opts || {});
        var dark = o.theme === 'dark' || (o.theme === 'auto' && window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches);
        var s = _sizes(o.size);

        var btn = document.createElement('button');
        btn.type = 'button';
        btn.setAttribute('aria-label', 'TOKEN PAY ID');
        Object.assign(btn.style, {
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            gap: '6px', height: s.h + 'px', padding: '0 ' + s.pad + 'px',
            border: 'none', borderRadius: '8px', background: 'transparent',
            color: dark ? '#fff' : '#111',
            fontFamily: "'Comfortaa',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif",
            fontSize: s.font + 'px', fontWeight: '600', letterSpacing: '0.5px',
            cursor: 'pointer', transition: 'all .15s ease',
            outline: 'none', lineHeight: '1', whiteSpace: 'nowrap', opacity: '0.85'
        });
        var img = document.createElement('img');
        img.src = BASE + (dark ? '/tokenpay-id-light.png' : '/tokenpay-id-dark.png');
        img.alt = 'TOKEN PAY ID';
        Object.assign(img.style, { height: (s.h - 12) + 'px', width: 'auto', pointerEvents: 'none', userSelect: 'none' });
        btn.appendChild(img);

        btn.onmouseenter = function() { btn.style.opacity = '1'; btn.style.transform = 'scale(1.02)'; };
        btn.onmouseleave = function() { btn.style.opacity = '0.85'; btn.style.transform = 'scale(1)'; };
        btn.onclick = function() { _authorize(); };

        el.appendChild(btn);
        return btn;
    }

    // ===== Public API =====
    var TPID = {
        version: version,

        init: function(opts) {
            if (!opts) opts = {};
            cfg = {
                clientId: opts.clientId || '',
                redirectUri: opts.redirectUri || '',
                scope: opts.scope || 'openid profile email',
                onSuccess: opts.onSuccess || null,
                onError: opts.onError || null,
                theme: opts.theme || 'auto',
                lang: opts.lang || opts.locale || 'ru',
                size: opts.size || 'medium',
                autoButton: opts.autoButton !== false
            };
        },

        open: function(opts) {
            _authorize(opts);
        },

        loginWithOAuth: function(opts) {
            return new Promise(function(resolve, reject) {
                _resolve = resolve;
                _reject = reject;
                _authorize(opts);
            });
        },

        renderButton: function(el, opts) { return _createStandardBtn(el, opts); },
        renderIconButton: function(el, opts) { return _createIconBtn(el, opts); },
        renderLogoButton: function(el, opts) { return _createLogoBtn(el, opts); },

        getCodeVerifier: function() { return sessionStorage.getItem(VK); }
    };

    window.TPID = TPID;

    // ===== Auto-init from script tag =====
    function _autoInit() {
        var scripts = document.getElementsByTagName('script');
        var me = null;
        for (var i = 0; i < scripts.length; i++) {
            if (scripts[i].src && scripts[i].src.indexOf('tpid-widget') !== -1) { me = scripts[i]; break; }
        }
        if (!me) return;

        var clientId = me.getAttribute('data-client-id');
        if (!clientId) return;

        TPID.init({
            clientId: clientId,
            redirectUri: me.getAttribute('data-redirect-uri') || window.location.origin + '/callback',
            scope: me.getAttribute('data-scope') || 'openid profile email',
            theme: me.getAttribute('data-theme') || 'auto',
            lang: me.getAttribute('data-lang') || 'ru',
            size: me.getAttribute('data-size') || 'medium'
        });

        // Auto-render data-tpid-button containers
        var containers = document.querySelectorAll('[data-tpid-button]');
        containers.forEach(function(el) {
            var type = el.getAttribute('data-tpid-button');
            if (type === 'icon') TPID.renderIconButton(el);
            else if (type === 'logo') TPID.renderLogoButton(el);
            else TPID.renderButton(el);
        });

        // If no containers, create default button after the script tag
        if (containers.length === 0 && me.getAttribute('data-auto-button') !== 'false') {
            var wrap = document.createElement('div');
            wrap.style.cssText = 'display:inline-block;margin:4px 0';
            me.parentNode.insertBefore(wrap, me.nextSibling);
            TPID.renderButton(wrap);
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', _autoInit);
    } else {
        _autoInit();
    }

})(window, document);
