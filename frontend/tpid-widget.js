/**
 * TOKEN PAY ID Widget v1.2.0
 * Embed: <script src="https://tokenpay.space/sdk/tpid-widget.js" data-client-id="YOUR_CLIENT_ID"></script>
 * Manual: window.TPID.init({ clientId, onSuccess, onError, lang })
 *         window.TPID.open()
 */
(function (w, d) {
  'use strict';

  const WIDGET_VERSION = '1.2.0';
  const API = 'https://tokenpay.space/api/v1';
  const ORIGIN = 'https://tokenpay.space';
  const LS_KEY = 'tpid_saved_accounts';
  const LS_TOKEN = 'tpid_token';

  // ─── CSS ────────────────────────────────────────────────────────────────────
  const CSS = `
@import url('https://fonts.googleapis.com/css2?family=Comfortaa:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap');
.tpid-backdrop{position:fixed;inset:0;z-index:2147483640;background:rgba(0,0,0,.72);backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);display:flex;align-items:center;justify-content:center;padding:16px;opacity:0;transition:opacity .3s cubic-bezier(.4,0,.2,1);pointer-events:none}
.tpid-backdrop.tpid-open{opacity:1;pointer-events:auto}
.tpid-modal{font-family:'Comfortaa',system-ui,sans-serif;position:relative;width:100%;max-width:400px;background:rgba(7,7,9,.96);border:1px solid rgba(255,255,255,.12);border-radius:24px;padding:40px 36px 36px;box-shadow:0 0 0 1px rgba(255,255,255,.04),0 40px 100px rgba(0,0,0,.7),inset 0 1px 0 rgba(255,255,255,.1);overflow:hidden;transform:translateY(24px) scale(.97);transition:transform .35s cubic-bezier(.34,1.56,.64,1),opacity .3s;opacity:0;will-change:transform}
.tpid-backdrop.tpid-open .tpid-modal{transform:translateY(0) scale(1);opacity:1}
.tpid-modal::before{content:'';position:absolute;top:0;left:0;right:0;height:1px;background:linear-gradient(90deg,transparent,rgba(255,255,255,.3),transparent)}
.tpid-close{position:absolute;top:14px;right:14px;width:32px;height:32px;background:rgba(255,255,255,.06);border:none;border-radius:50%;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:background .2s;color:rgba(255,255,255,.4)}
.tpid-close:hover{background:rgba(255,255,255,.12);color:#fff}
.tpid-logo-area{text-align:center;margin-bottom:28px}
.tpid-logo-area img{max-width:220px;height:auto;pointer-events:none;filter:drop-shadow(0 0 30px rgba(255,255,255,.12));animation:tpidLogoPulse 3s ease-in-out infinite}
@keyframes tpidLogoPulse{0%,100%{filter:drop-shadow(0 0 30px rgba(255,255,255,.1))}50%{filter:drop-shadow(0 0 50px rgba(255,255,255,.2))}}
.tpid-step{display:none;animation:tpidStepIn .32s cubic-bezier(.4,0,.2,1) both}
.tpid-step.tpid-active{display:block}
@keyframes tpidStepIn{from{opacity:0;transform:translateX(18px)}to{opacity:1;transform:translateX(0)}}
.tpid-back{display:inline-flex;align-items:center;gap:5px;background:none;border:none;color:rgba(255,255,255,.35);font-family:inherit;font-size:.78rem;cursor:pointer;padding:0;margin-bottom:20px;transition:color .2s}
.tpid-back:hover{color:rgba(255,255,255,.7)}
.tpid-user-chip{display:flex;align-items:center;gap:8px;padding:8px 12px;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.07);border-radius:10px;margin-bottom:18px;font-size:.8rem;color:rgba(255,255,255,.6)}
.tpid-user-chip-av{width:26px;height:26px;border-radius:50%;background:rgba(255,255,255,.1);display:flex;align-items:center;justify-content:center;font-size:.7rem;font-weight:700;color:rgba(255,255,255,.6);flex-shrink:0}
.tpid-label{display:block;font-size:.72rem;color:rgba(255,255,255,.35);margin-bottom:6px;letter-spacing:.5px}
.tpid-input{width:100%;padding:12px 14px;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.1);border-radius:10px;color:#fff;font-family:inherit;font-size:.9rem;outline:none;transition:all .2s;box-sizing:border-box}
.tpid-input:focus{border-color:rgba(255,255,255,.3);background:rgba(255,255,255,.06);box-shadow:0 0 0 3px rgba(255,255,255,.04)}
.tpid-input-wrap{position:relative;margin-bottom:14px}
.tpid-eye{position:absolute;right:10px;top:50%;transform:translateY(-50%);background:none;border:none;cursor:pointer;color:rgba(255,255,255,.3);padding:4px;display:flex;transition:color .2s}
.tpid-eye:hover{color:rgba(255,255,255,.6)}
.tpid-btn{width:100%;padding:13px;background:#fff;color:#000;border:none;border-radius:10px;font-family:inherit;font-size:.9rem;font-weight:700;cursor:pointer;transition:all .2s;position:relative;overflow:hidden;margin-top:6px}
.tpid-btn:hover{background:#e8e8e8;transform:translateY(-1px);box-shadow:0 6px 20px rgba(255,255,255,.1)}
.tpid-btn:active{transform:translateY(0)}
.tpid-btn-loading{opacity:.7;cursor:not-allowed}
.tpid-btn-loading::after{content:'';position:absolute;inset:0;background:linear-gradient(90deg,transparent,rgba(0,0,0,.08),transparent);animation:tpidShimmer 1.2s infinite}
@keyframes tpidShimmer{0%{transform:translateX(-100%)}100%{transform:translateX(100%)}}
.tpid-err{display:none;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.1);border-radius:8px;padding:9px 12px;font-size:.78rem;color:rgba(255,255,255,.55);margin-top:10px;text-align:center}
.tpid-err.tpid-show{display:block}
.tpid-hint{font-size:.72rem;color:rgba(255,255,255,.25);text-align:center;margin-top:10px}
.tpid-hint a{color:rgba(255,255,255,.45);text-decoration:underline;cursor:pointer}
.tpid-footer{text-align:center;margin-top:20px;padding-top:16px;border-top:1px solid rgba(255,255,255,.06)}
.tpid-footer-main{display:flex;align-items:center;justify-content:center;gap:5px;font-size:.72rem;color:rgba(255,255,255,.2);margin-bottom:6px}
.tpid-footer-main a{display:inline-flex;align-items:center;gap:4px;color:rgba(255,255,255,.2);text-decoration:none;transition:color .2s}
.tpid-footer-main a:hover{color:rgba(255,255,255,.45)}
.tpid-footer-links{display:flex;align-items:center;justify-content:center;gap:4px;font-size:.62rem}
.tpid-footer-links a{color:rgba(255,255,255,.15);text-decoration:none;transition:color .2s}
.tpid-footer-links a:hover{color:rgba(255,255,255,.35)}
.tpid-footer-links span{color:rgba(255,255,255,.08)}
.tpid-saved-list{margin-bottom:16px}
.tpid-saved-item{display:flex;align-items:center;gap:10px;padding:9px 12px;background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.06);border-radius:10px;cursor:pointer;margin-bottom:6px;transition:all .15s}
.tpid-saved-item:hover{background:rgba(255,255,255,.07);border-color:rgba(255,255,255,.12)}
.tpid-saved-av{width:30px;height:30px;border-radius:50%;background:rgba(255,255,255,.08);display:flex;align-items:center;justify-content:center;font-size:.72rem;font-weight:700;color:rgba(255,255,255,.5);flex-shrink:0}
.tpid-saved-info{flex:1;min-width:0}
.tpid-saved-name{font-size:.8rem;color:rgba(255,255,255,.7);font-weight:600}
.tpid-saved-email{font-size:.72rem;color:rgba(255,255,255,.3);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.tpid-divider{display:flex;align-items:center;gap:10px;margin:16px 0;color:rgba(255,255,255,.18);font-size:.72rem}
.tpid-divider::before,.tpid-divider::after{content:'';flex:1;height:1px;background:rgba(255,255,255,.06)}
.tpid-captcha-wrap{background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.07);border-radius:10px;padding:12px;margin-bottom:14px}
.tpid-captcha-label{font-size:.68rem;color:rgba(255,255,255,.3);margin-bottom:8px;text-transform:uppercase;letter-spacing:1.5px}
.tpid-captcha-box{display:flex;align-items:center;gap:8px;margin-bottom:8px}
.tpid-captcha-code{flex:1;background:rgba(0,0,0,.3);border:1px solid rgba(255,255,255,.1);border-radius:8px;padding:10px;font-family:'JetBrains Mono',monospace;font-size:.95rem;font-weight:700;letter-spacing:1px;color:#fff;text-align:center}
.tpid-captcha-refresh{width:34px;height:34px;background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.07);border-radius:7px;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:all .2s;flex-shrink:0;color:rgba(255,255,255,.4)}
.tpid-captcha-refresh:hover{background:rgba(255,255,255,.1);transform:rotate(180deg)}
.tpid-success{text-align:center;padding:8px 0}
.tpid-success-icon{width:56px;height:56px;background:rgba(255,255,255,.08);border-radius:50%;display:flex;align-items:center;justify-content:center;margin:0 auto 16px;animation:tpidPop .5s cubic-bezier(.34,1.56,.64,1)}
@keyframes tpidPop{from{transform:scale(0)}to{transform:scale(1)}}
.tpid-success h3{color:#fff;font-size:1.1rem;margin-bottom:6px}
.tpid-success p{color:rgba(255,255,255,.4);font-size:.82rem}
@keyframes tpidShake{0%,100%{transform:translateX(0)}25%{transform:translateX(-8px)}75%{transform:translateX(8px)}}
.tpid-shake{animation:tpidShake .35s}

/* ─── Standard Button ────────────────────────────────────────────────────── */
.tpid-trigger-btn{display:inline-flex;align-items:center;gap:10px;padding:11px 20px;background:#000;color:#fff;border:1.5px solid rgba(255,255,255,.15);border-radius:10px;font-family:'Comfortaa',system-ui,sans-serif;font-size:.85rem;font-weight:600;cursor:pointer;transition:all .2s;text-decoration:none;white-space:nowrap;position:relative;overflow:hidden}
.tpid-trigger-btn::before{content:'';position:absolute;inset:0;background:linear-gradient(135deg,rgba(255,255,255,.06),transparent);opacity:0;transition:opacity .2s}
.tpid-trigger-btn:hover{transform:translateY(-1px);box-shadow:0 6px 20px rgba(0,0,0,.25);border-color:rgba(255,255,255,.3)}
.tpid-trigger-btn:hover::before{opacity:1}
.tpid-trigger-btn .tpid-btn-icon{width:20px;height:20px;flex-shrink:0}
.tpid-trigger-btn img{width:20px;height:20px;object-fit:contain}

/* ─── Round Icon Button (circle, no text) ────────────────────────────────── */
.tpid-icon-btn{display:inline-flex;align-items:center;justify-content:center;width:44px;height:44px;padding:0;background:#000;border:1.5px solid rgba(255,255,255,.15);border-radius:50%;cursor:pointer;transition:all .25s cubic-bezier(.4,0,.2,1);position:relative;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.2)}
.tpid-icon-btn::before{content:'';position:absolute;inset:0;border-radius:50%;background:radial-gradient(circle at 30% 30%,rgba(255,255,255,.12),transparent 70%);opacity:0;transition:opacity .25s}
.tpid-icon-btn:hover{transform:translateY(-2px) scale(1.05);box-shadow:0 6px 24px rgba(0,0,0,.35);border-color:rgba(255,255,255,.35)}
.tpid-icon-btn:hover::before{opacity:1}
.tpid-icon-btn:active{transform:translateY(0) scale(.97)}
.tpid-icon-btn .tpid-btn-icon{width:22px;height:22px}
.tpid-icon-btn.tpid-icon-sm{width:36px;height:36px}
.tpid-icon-btn.tpid-icon-sm .tpid-btn-icon{width:18px;height:18px}
.tpid-icon-btn.tpid-icon-lg{width:52px;height:52px}
.tpid-icon-btn.tpid-icon-lg .tpid-btn-icon{width:26px;height:26px}

/* ─── Logo Button (transparent bg, just logo+text) ──────────────────────── */
.tpid-logo-btn{display:inline-flex;align-items:center;gap:10px;padding:10px 18px;background:transparent;color:#fff;border:1.5px solid rgba(255,255,255,.12);border-radius:12px;font-family:'Comfortaa',system-ui,sans-serif;font-size:.82rem;font-weight:600;cursor:pointer;transition:all .25s;text-decoration:none;white-space:nowrap;backdrop-filter:blur(4px);-webkit-backdrop-filter:blur(4px)}
.tpid-logo-btn:hover{border-color:rgba(255,255,255,.3);background:rgba(255,255,255,.04);transform:translateY(-1px);box-shadow:0 4px 16px rgba(0,0,0,.15)}
.tpid-logo-btn:active{transform:translateY(0)}
.tpid-logo-btn .tpid-btn-icon{width:20px;height:20px;flex-shrink:0}
.tpid-logo-btn .tpid-btn-logo{height:16px;width:auto;opacity:.9}
.tpid-logo-btn img{height:16px;width:auto;object-fit:contain;opacity:.9}

/* ─── Light theme ────────────────────────────────────────────────────────── */
.tpid-light .tpid-modal{background:rgba(255,255,255,.97);border-color:rgba(0,0,0,.08);box-shadow:0 0 0 1px rgba(0,0,0,.04),0 40px 100px rgba(0,0,0,.15),inset 0 1px 0 rgba(255,255,255,.8)}
.tpid-light .tpid-modal::before{background:linear-gradient(90deg,transparent,rgba(0,0,0,.06),transparent)}
.tpid-light .tpid-close{background:rgba(0,0,0,.04);color:rgba(0,0,0,.3)}
.tpid-light .tpid-close:hover{background:rgba(0,0,0,.08);color:rgba(0,0,0,.7)}
.tpid-light .tpid-logo-area img{content:url('${ORIGIN}/tokenpay-id-dark.png');filter:drop-shadow(0 0 20px rgba(0,0,0,.06))}
.tpid-light .tpid-back{color:rgba(0,0,0,.35)}
.tpid-light .tpid-back:hover{color:rgba(0,0,0,.7)}
.tpid-light .tpid-user-chip{background:rgba(0,0,0,.03);border-color:rgba(0,0,0,.06);color:rgba(0,0,0,.6)}
.tpid-light .tpid-user-chip-av{background:rgba(0,0,0,.06);color:rgba(0,0,0,.5)}
.tpid-light .tpid-label{color:rgba(0,0,0,.4)}
.tpid-light .tpid-input{background:rgba(0,0,0,.03);border-color:rgba(0,0,0,.1);color:#111}
.tpid-light .tpid-input:focus{border-color:rgba(0,0,0,.25);background:rgba(0,0,0,.02);box-shadow:0 0 0 3px rgba(0,0,0,.04)}
.tpid-light .tpid-input::placeholder{color:rgba(0,0,0,.25)}
.tpid-light .tpid-eye{color:rgba(0,0,0,.25)}
.tpid-light .tpid-eye:hover{color:rgba(0,0,0,.5)}
.tpid-light .tpid-btn{background:#111;color:#fff}
.tpid-light .tpid-btn:hover{background:#222;box-shadow:0 6px 20px rgba(0,0,0,.12)}
.tpid-light .tpid-err{background:rgba(0,0,0,.04);border-color:rgba(0,0,0,.1);color:rgba(0,0,0,.55)}
.tpid-light .tpid-hint{color:rgba(0,0,0,.3)}
.tpid-light .tpid-hint a{color:rgba(0,0,0,.5)}
.tpid-light .tpid-footer{border-color:rgba(0,0,0,.04)}
.tpid-light .tpid-footer-main,.tpid-light .tpid-footer-main a{color:rgba(0,0,0,.25)}
.tpid-light .tpid-footer-main a:hover{color:rgba(0,0,0,.5)}
.tpid-light .tpid-footer-links a{color:rgba(0,0,0,.2)}
.tpid-light .tpid-footer-links a:hover{color:rgba(0,0,0,.4)}
.tpid-light .tpid-footer-links span{color:rgba(0,0,0,.1)}
.tpid-light .tpid-saved-item{background:rgba(0,0,0,.02);border-color:rgba(0,0,0,.06)}
.tpid-light .tpid-saved-item:hover{background:rgba(0,0,0,.05);border-color:rgba(0,0,0,.1)}
.tpid-light .tpid-saved-av{background:rgba(0,0,0,.06);color:rgba(0,0,0,.45)}
.tpid-light .tpid-saved-name{color:rgba(0,0,0,.7)}
.tpid-light .tpid-saved-email{color:rgba(0,0,0,.35)}
.tpid-light .tpid-divider{color:rgba(0,0,0,.15)}
.tpid-light .tpid-divider::before,.tpid-light .tpid-divider::after{background:rgba(0,0,0,.06)}
.tpid-light .tpid-captcha-wrap{background:rgba(0,0,0,.02);border-color:rgba(0,0,0,.06)}
.tpid-light .tpid-captcha-label{color:rgba(0,0,0,.3)}
.tpid-light .tpid-captcha-code{background:rgba(0,0,0,.03);border-color:rgba(0,0,0,.08);color:#111}
.tpid-light .tpid-captcha-refresh{background:rgba(0,0,0,.04);border-color:rgba(0,0,0,.06);color:rgba(0,0,0,.35)}
.tpid-light .tpid-captcha-refresh:hover{background:rgba(0,0,0,.08)}
.tpid-light .tpid-success-icon{background:rgba(0,0,0,.06)}
.tpid-light .tpid-success-icon svg{stroke:#111}
.tpid-light .tpid-success h3{color:#111}
.tpid-light .tpid-success p{color:rgba(0,0,0,.4)}
.tpid-light .tpid-trigger-btn{background:#fff;color:#111;border-color:rgba(0,0,0,.12)}
.tpid-light .tpid-trigger-btn:hover{box-shadow:0 6px 20px rgba(0,0,0,.08);border-color:rgba(0,0,0,.2)}
.tpid-light .tpid-icon-btn{background:#fff;border-color:rgba(0,0,0,.1);box-shadow:0 2px 8px rgba(0,0,0,.06)}
.tpid-light .tpid-icon-btn:hover{box-shadow:0 6px 24px rgba(0,0,0,.12);border-color:rgba(0,0,0,.2)}
.tpid-light .tpid-icon-btn .tpid-btn-icon{color:#111}
.tpid-light .tpid-logo-btn{color:#111;border-color:rgba(0,0,0,.1)}
.tpid-light .tpid-logo-btn:hover{border-color:rgba(0,0,0,.2);background:rgba(0,0,0,.02)}
@media(max-width:480px){.tpid-modal{padding:32px 24px 28px;border-radius:20px;max-width:calc(100vw - 32px)}.tpid-logo-area img{max-width:180px}.tpid-input{font-size:16px;padding:14px}}
`;

  // ─── HTML ────────────────────────────────────────────────────────────────────
  function buildModal() {
    return `
<div class="tpid-backdrop" id="tpid-backdrop">
  <div class="tpid-modal" role="dialog" aria-modal="true" aria-label="TOKEN PAY ID">
    <button class="tpid-close" id="tpid-close" aria-label="Закрыть">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
    </button>
    <div class="tpid-logo-area">
      <img src="${ORIGIN}/tokenpay-id-light.png" alt="TOKEN PAY ID">
    </div>

    <!-- Step 1: Email + saved accounts -->
    <div class="tpid-step tpid-active" id="tpid-s1">
      <div class="tpid-saved-list" id="tpid-saved" style="display:none"></div>
      <div id="tpid-s1-divider" style="display:none"><div class="tpid-divider">или введите email</div></div>
      <label class="tpid-label">Email</label>
      <div class="tpid-input-wrap">
        <input class="tpid-input" id="tpid-email" type="email" placeholder="you@example.com" autocomplete="email">
      </div>
      <button class="tpid-btn" id="tpid-s1-next">Далее</button>
      <p class="tpid-hint">Нет аккаунта? <a id="tpid-to-reg">Зарегистрироваться</a></p>
    </div>

    <!-- Step 2: Password + captcha -->
    <div class="tpid-step" id="tpid-s2">
      <button class="tpid-back" id="tpid-s2-back">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>
        Назад
      </button>
      <div class="tpid-user-chip" id="tpid-chip">
        <div class="tpid-user-chip-av" id="tpid-chip-av">ИМ</div>
        <span id="tpid-chip-email"></span>
      </div>
      <label class="tpid-label">Пароль</label>
      <div class="tpid-input-wrap">
        <input class="tpid-input" id="tpid-pass" type="password" placeholder="Ваш пароль" autocomplete="current-password" style="padding-right:40px">
        <button class="tpid-eye" type="button" id="tpid-eye">
          <svg id="tpid-eye-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
        </button>
      </div>
      <div class="tpid-captcha-wrap">
        <div class="tpid-captcha-label">Проверка</div>
        <div class="tpid-captcha-box">
          <div class="tpid-captcha-code" id="tpid-captcha-code">42 + 8 = ?</div>
          <button class="tpid-captcha-refresh" type="button" id="tpid-captcha-refresh">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0118.8-4.3M22 12.5a10 10 0 01-18.8 4.2"/></svg>
          </button>
        </div>
        <input class="tpid-input" id="tpid-captcha-input" type="text" placeholder="Ответ" maxlength="4" inputmode="numeric" autocomplete="off" style="font-size:.85rem;padding:9px 12px">
      </div>
      <div class="tpid-err" id="tpid-s2-err"></div>
      <button class="tpid-btn" id="tpid-s2-submit">Войти</button>
    </div>

    <!-- Step 3: 2FA -->
    <div class="tpid-step" id="tpid-s3">
      <button class="tpid-back" id="tpid-s3-back">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>
        Назад
      </button>
      <label class="tpid-label">Код подтверждения</label>
      <div class="tpid-input-wrap">
        <input class="tpid-input" id="tpid-tfa" type="text" placeholder="000 000" maxlength="7" autocomplete="one-time-code" style="text-align:center;letter-spacing:4px;font-family:'JetBrains Mono',monospace;font-size:1.1rem">
      </div>
      <p class="tpid-hint" style="margin-bottom:10px">Введите 6-значный код из приложения аутентификации</p>
      <div class="tpid-err" id="tpid-s3-err"></div>
      <button class="tpid-btn" id="tpid-s3-submit">Подтвердить</button>
    </div>

    <!-- Step 4: Register -->
    <div class="tpid-step" id="tpid-s4">
      <button class="tpid-back" id="tpid-s4-back">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>
        Назад
      </button>
      <label class="tpid-label">Имя</label>
      <div class="tpid-input-wrap">
        <input class="tpid-input" id="tpid-reg-name" type="text" placeholder="Ваше имя" autocomplete="name">
      </div>
      <label class="tpid-label">Email</label>
      <div class="tpid-input-wrap">
        <input class="tpid-input" id="tpid-reg-email" type="email" placeholder="you@example.com" autocomplete="email">
      </div>
      <label class="tpid-label">Пароль</label>
      <div class="tpid-input-wrap">
        <input class="tpid-input" id="tpid-reg-pass" type="password" placeholder="Минимум 8 символов" autocomplete="new-password" style="padding-right:40px">
        <button class="tpid-eye" type="button" id="tpid-reg-eye">
          <svg id="tpid-reg-eye-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
        </button>
      </div>
      <div class="tpid-captcha-wrap">
        <div class="tpid-captcha-label">Проверка</div>
        <div class="tpid-captcha-box">
          <div class="tpid-captcha-code" id="tpid-reg-captcha-code">12 + 7 = ?</div>
          <button class="tpid-captcha-refresh" type="button" id="tpid-reg-captcha-refresh">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0118.8-4.3M22 12.5a10 10 0 01-18.8 4.2"/></svg>
          </button>
        </div>
        <input class="tpid-input" id="tpid-reg-captcha-input" type="text" placeholder="Ответ" maxlength="4" inputmode="numeric" autocomplete="off" style="font-size:.85rem;padding:9px 12px">
      </div>
      <div class="tpid-err" id="tpid-s4-err"></div>
      <button class="tpid-btn" id="tpid-s4-submit">Создать аккаунт</button>
      <p class="tpid-hint">Уже есть аккаунт? <a id="tpid-to-login">Войти</a></p>
    </div>

    <!-- Step 5: Success -->
    <div class="tpid-step" id="tpid-s5">
      <div class="tpid-success">
        <div class="tpid-success-icon">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5"><path d="M20 6L9 17l-5-5"/></svg>
        </div>
        <h3>Успешный вход!</h3>
        <p id="tpid-success-name"></p>
      </div>
    </div>

    <div class="tpid-footer">
      <div class="tpid-footer-main">
        <a href="${ORIGIN}" target="_blank" rel="noopener">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
          <span id="tpid-footer-text">Защищено TOKEN PAY ID</span>
        </a>
      </div>
      <div class="tpid-footer-links">
        <a href="${ORIGIN}/privacy" target="_blank" id="tpid-footer-privacy">Конфиденциальность</a>
        <span>&middot;</span>
        <a href="${ORIGIN}/terms" target="_blank" id="tpid-footer-terms">Условия</a>
        <span>&middot;</span>
        <a href="${ORIGIN}/dashboard" target="_blank" id="tpid-footer-account">Мой аккаунт</a>
      </div>
    </div>
  </div>
</div>`;
  }

  // ─── i18n ──────────────────────────────────────────────────────────────────
  var _t = {
    ru: {
      email: 'Email', password: 'Пароль', name: 'Имя', next: 'Далее', login: 'Войти',
      confirm: 'Подтвердить', createAccount: 'Создать аккаунт', back: 'Назад',
      noAccount: 'Нет аккаунта?', register: 'Зарегистрироваться',
      hasAccount: 'Уже есть аккаунт?', loginLink: 'Войти',
      code2fa: 'Код подтверждения', code2faHint: 'Введите 6-значный код из приложения аутентификации',
      emailPlaceholder: 'you@example.com', passPlaceholder: 'Ваш пароль',
      namePlaceholder: 'Ваше имя', passMin: 'Минимум 8 символов',
      captcha: 'Проверка', captchaAnswer: 'Ответ',
      wrongCaptcha: 'Неверный ответ на задачу',
      wrongLogin: 'Неверный email или пароль', wrongCode: 'Неверный код',
      enterName: 'Введите имя', enterEmail: 'Введите корректный email',
      passMinErr: 'Пароль минимум 8 символов', regError: 'Ошибка регистрации',
      networkError: 'Ошибка соединения с сервером',
      regDone: 'Аккаунт создан! Войдите через форму входа.',
      successTitle: 'Успешный вход!', welcome: 'Добро пожаловать,',
      orEmail: 'или введите email',
      protected: 'Защищено TOKEN PAY ID',
      privacy: 'Конфиденциальность', terms: 'Условия', account: 'Мой аккаунт',
      btnLabel: 'Войти через TOKEN PAY ID'
    },
    en: {
      email: 'Email', password: 'Password', name: 'Name', next: 'Next', login: 'Sign In',
      confirm: 'Confirm', createAccount: 'Create Account', back: 'Back',
      noAccount: "Don't have an account?", register: 'Sign Up',
      hasAccount: 'Already have an account?', loginLink: 'Sign In',
      code2fa: 'Verification Code', code2faHint: 'Enter the 6-digit code from your authenticator app',
      emailPlaceholder: 'you@example.com', passPlaceholder: 'Your password',
      namePlaceholder: 'Your name', passMin: 'At least 8 characters',
      captcha: 'Verify', captchaAnswer: 'Answer',
      wrongCaptcha: 'Wrong answer', wrongLogin: 'Wrong email or password',
      wrongCode: 'Wrong code', enterName: 'Enter your name',
      enterEmail: 'Enter a valid email', passMinErr: 'Password must be at least 8 characters',
      regError: 'Registration error', networkError: 'Connection error',
      regDone: 'Account created! Please sign in.',
      successTitle: 'Signed In!', welcome: 'Welcome,',
      orEmail: 'or enter email',
      protected: 'Protected by TOKEN PAY ID',
      privacy: 'Privacy', terms: 'Terms', account: 'My Account',
      btnLabel: 'Sign in with TOKEN PAY ID'
    }
  };
  var _lang = 'ru';
  function t(k) { return (_t[_lang] && _t[_lang][k]) || _t.ru[k] || k; }

  // ─── State ───────────────────────────────────────────────────────────────────
  let _cfg = {};
  let _captchaAnswer = 0;
  let _regCaptchaAnswer = 0;
  let _injected = false;
  let _theme = 'dark';

  // ─── Utils ───────────────────────────────────────────────────────────────────
  function injectStyles() {
    if (d.getElementById('tpid-css')) return;
    const s = d.createElement('style');
    s.id = 'tpid-css';
    s.textContent = CSS;
    d.head.appendChild(s);
  }

  function injectModal() {
    if (d.getElementById('tpid-backdrop')) return;
    const div = d.createElement('div');
    div.innerHTML = buildModal();
    d.body.appendChild(div.firstElementChild);
    _injected = true;
    bindEvents();
    applyTheme();
    applyLang();
  }

  function applyTheme() {
    var backdrop = $id('tpid-backdrop');
    if (!backdrop) return;
    if (_theme === 'light') backdrop.classList.add('tpid-light');
    else backdrop.classList.remove('tpid-light');
  }

  function applyLang() {
    var m = { 'tpid-footer-text': 'protected', 'tpid-footer-privacy': 'privacy', 'tpid-footer-terms': 'terms', 'tpid-footer-account': 'account' };
    for (var id in m) { var el = $id(id); if (el) el.textContent = t(m[id]); }
  }

  function $id(id) { return d.getElementById(id); }
  function _esc(s) { return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;'); }

  function showStep(n) {
    [1,2,3,4,5].forEach(i => {
      const el = $id('tpid-s' + i);
      if (el) el.classList.toggle('tpid-active', i === n);
    });
  }

  function setBtn(id, loading) {
    const btn = $id(id);
    if (!btn) return;
    btn.classList.toggle('tpid-btn-loading', loading);
    btn.disabled = loading;
  }

  function showErr(id, msg) {
    const el = $id(id);
    if (!el) return;
    el.textContent = msg;
    el.classList.add('tpid-show');
  }

  function hideErr(id) {
    const el = $id(id);
    if (el) el.classList.remove('tpid-show');
  }

  function makeCaptcha() {
    const ops = ['+', '+', '+', '×', '−'];
    const op = ops[Math.floor(Math.random() * ops.length)];
    let a, b, ans;
    if (op === '×') { a = Math.floor(Math.random()*9)+2; b = Math.floor(Math.random()*9)+2; ans = a*b; }
    else if (op === '−') { a = Math.floor(Math.random()*40)+20; b = Math.floor(Math.random()*(a-1))+1; ans = a-b; }
    else { a = Math.floor(Math.random()*50)+5; b = Math.floor(Math.random()*50)+5; ans = a+b; }
    return { text: a + ' ' + op + ' ' + b + ' = ?', ans };
  }

  function refreshCaptcha(codeId, inputId) {
    const c = makeCaptcha();
    const codeEl = $id(codeId), inputEl = $id(inputId);
    if (codeEl) codeEl.textContent = c.text;
    if (inputEl) { inputEl.value = ''; }
    return c.ans;
  }

  function savedAccounts() {
    try { return JSON.parse(localStorage.getItem(LS_KEY) || '[]'); } catch(e) { return []; }
  }

  function saveAccount(user) {
    const list = savedAccounts().filter(a => a.email !== user.email);
    list.unshift({ email: user.email, name: user.name || user.email, id: user.id });
    if (list.length > 5) list.length = 5;
    try { localStorage.setItem(LS_KEY, JSON.stringify(list)); } catch(e) {}
  }

  function renderSaved() {
    const accounts = savedAccounts();
    const container = $id('tpid-saved');
    const divider = $id('tpid-s1-divider');
    if (!container) return;
    if (!accounts.length) { container.style.display = 'none'; if (divider) divider.style.display = 'none'; return; }
    container.style.display = 'block';
    if (divider) divider.style.display = 'block';
    container.innerHTML = '';
    accounts.forEach(function(a) {
      const initials = (a.name || a.email).substring(0, 2).toUpperCase();
      const item = d.createElement('div');
      item.className = 'tpid-saved-item';
      item.innerHTML =
        '<div class="tpid-saved-av">' + _esc(initials) + '</div>' +
        '<div class="tpid-saved-info"><div class="tpid-saved-name">' + _esc(a.name || '') + '</div>' +
        '<div class="tpid-saved-email">' + _esc(a.email) + '</div></div>' +
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,.3)" stroke-width="2"><path d="M9 18l6-6-6-6"/></svg>';
      item.onclick = function() {
        $id('tpid-email').value = a.email;
        goStep2();
      };
      container.appendChild(item);
    });
  }

  function toggleEye(inputId, eyeIconId) {
    const inp = $id(inputId);
    const icon = $id(eyeIconId);
    if (!inp) return;
    const isPass = inp.type === 'password';
    inp.type = isPass ? 'text' : 'password';
    if (icon) {
      icon.innerHTML = isPass
        ? '<path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/>'
        : '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>';
    }
  }

  // ─── Navigation ──────────────────────────────────────────────────────────────
  function goStep1() {
    showStep(1);
    renderSaved();
    _captchaAnswer = refreshCaptcha('tpid-captcha-code', 'tpid-captcha-input');
    setTimeout(function() { const e = $id('tpid-email'); if (e) e.focus(); }, 80);
  }

  function goStep2() {
    const email = ($id('tpid-email') && $id('tpid-email').value.trim()) || '';
    if (!email || !email.includes('@')) {
      const el = $id('tpid-email');
      if (el) { el.style.borderColor = 'rgba(255,255,255,.3)'; setTimeout(function() { el.style.borderColor = ''; }, 1500); }
      return;
    }
    const chipEmail = $id('tpid-chip-email');
    const chipAv = $id('tpid-chip-av');
    if (chipEmail) chipEmail.textContent = email;
    if (chipAv) chipAv.textContent = email.substring(0, 2).toUpperCase();
    showStep(2);
    hideErr('tpid-s2-err');
    setTimeout(function() { const e = $id('tpid-pass'); if (e) e.focus(); }, 80);
  }

  function goStep4() {
    showStep(4);
    const regEmail = $id('tpid-reg-email');
    const loginEmail = $id('tpid-email');
    if (regEmail && loginEmail) regEmail.value = loginEmail.value;
    _regCaptchaAnswer = refreshCaptcha('tpid-reg-captcha-code', 'tpid-reg-captcha-input');
    hideErr('tpid-s4-err');
  }

  // ─── API Calls ───────────────────────────────────────────────────────────────
  async function doLogin(email, password, tfa) {
    const res = await fetch(API + '/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password, two_factor_code: tfa || undefined })
    });
    return { ok: res.ok, data: await res.json() };
  }

  async function doRegister(name, email, password) {
    const res = await fetch(API + '/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, email, password })
    });
    return { ok: res.ok, data: await res.json() };
  }

  // ─── Handlers ────────────────────────────────────────────────────────────────
  async function handleLoginSubmit() {
    const email = $id('tpid-email') && $id('tpid-email').value.trim();
    const pass = $id('tpid-pass') && $id('tpid-pass').value;
    const captchaInput = parseInt(($id('tpid-captcha-input') && $id('tpid-captcha-input').value) || '0', 10);

    if (captchaInput !== _captchaAnswer) {
      const wrap = $id('tpid-s2');
      if (wrap) { wrap.classList.add('tpid-shake'); setTimeout(function() { wrap.classList.remove('tpid-shake'); }, 400); }
      _captchaAnswer = refreshCaptcha('tpid-captcha-code', 'tpid-captcha-input');
      showErr('tpid-s2-err', 'Неверный ответ на задачу');
      return;
    }

    setBtn('tpid-s2-submit', true);
    hideErr('tpid-s2-err');
    try {
      const { ok, data } = await doLogin(email, pass);
      if (data.requires_2fa) {
        showStep(3);
        setTimeout(function() { const e = $id('tpid-tfa'); if (e) e.focus(); }, 80);
        return;
      }
      if (!ok) {
        showErr('tpid-s2-err', (data.error && data.error.message) || 'Неверный email или пароль');
        _captchaAnswer = refreshCaptcha('tpid-captcha-code', 'tpid-captcha-input');
      } else {
        onLoginSuccess(data);
      }
    } catch(e) {
      showErr('tpid-s2-err', 'Ошибка соединения с сервером');
    } finally {
      setBtn('tpid-s2-submit', false);
    }
  }

  async function handleTFASubmit() {
    const email = $id('tpid-email') && $id('tpid-email').value.trim();
    const pass = $id('tpid-pass') && $id('tpid-pass').value;
    const tfa = $id('tpid-tfa') && $id('tpid-tfa').value.replace(/\s/g, '');

    setBtn('tpid-s3-submit', true);
    hideErr('tpid-s3-err');
    try {
      const { ok, data } = await doLogin(email, pass, tfa);
      if (!ok) {
        showErr('tpid-s3-err', (data.error && data.error.message) || 'Неверный код');
      } else {
        onLoginSuccess(data);
      }
    } catch(e) {
      showErr('tpid-s3-err', 'Ошибка соединения с сервером');
    } finally {
      setBtn('tpid-s3-submit', false);
    }
  }

  async function handleRegisterSubmit() {
    const name = $id('tpid-reg-name') && $id('tpid-reg-name').value.trim();
    const email = $id('tpid-reg-email') && $id('tpid-reg-email').value.trim();
    const pass = $id('tpid-reg-pass') && $id('tpid-reg-pass').value;
    const captchaInput = parseInt(($id('tpid-reg-captcha-input') && $id('tpid-reg-captcha-input').value) || '0', 10);

    if (!name) { showErr('tpid-s4-err', 'Введите имя'); return; }
    if (!email || !email.includes('@')) { showErr('tpid-s4-err', 'Введите корректный email'); return; }
    if (!pass || pass.length < 8) { showErr('tpid-s4-err', 'Пароль минимум 8 символов'); return; }
    if (captchaInput !== _regCaptchaAnswer) {
      showErr('tpid-s4-err', 'Неверный ответ на задачу');
      _regCaptchaAnswer = refreshCaptcha('tpid-reg-captcha-code', 'tpid-reg-captcha-input');
      return;
    }

    setBtn('tpid-s4-submit', true);
    hideErr('tpid-s4-err');
    try {
      const { ok, data } = await doRegister(name, email, pass);
      if (!ok) {
        showErr('tpid-s4-err', (data.error && data.error.message) || 'Ошибка регистрации');
        _regCaptchaAnswer = refreshCaptcha('tpid-reg-captcha-code', 'tpid-reg-captcha-input');
      } else {
        // Auto-login after register
        const loginResult = await doLogin(email, pass);
        if (loginResult.ok) {
          onLoginSuccess(loginResult.data);
        } else {
          showErr('tpid-s4-err', 'Аккаунт создан! Войдите через форму входа.');
          setTimeout(function() { goStep1(); }, 2000);
        }
      }
    } catch(e) {
      showErr('tpid-s4-err', 'Ошибка соединения с сервером');
    } finally {
      setBtn('tpid-s4-submit', false);
    }
  }

  function onLoginSuccess(data) {
    try { localStorage.setItem(LS_TOKEN, data.accessToken); } catch(e) {}
    try { localStorage.setItem('tpid_user', JSON.stringify(data.user)); } catch(e) {}
    saveAccount(data.user);

    showStep(5);
    const nameEl = $id('tpid-success-name');
    if (nameEl) nameEl.textContent = 'Добро пожаловать, ' + (data.user.name || data.user.email) + '!';

    if (typeof _cfg.onSuccess === 'function') {
      _cfg.onSuccess({ user: data.user, accessToken: data.accessToken, refreshToken: data.refreshToken });
    }

    if (_cfg.redirectUri) {
      const sep = _cfg.redirectUri.includes('?') ? '&' : '?';
      setTimeout(function() { w.location.href = _cfg.redirectUri + sep + 'token=' + encodeURIComponent(data.accessToken); }, 1200);
      return;
    }

    setTimeout(function() { TPID.close(); }, 2000);
  }

  // ─── Event binding ───────────────────────────────────────────────────────────
  function bindEvents() {
    function on(id, evt, fn) { const el = $id(id); if (el) el.addEventListener(evt, fn); }
    function onKey(id, fn) { on(id, 'keydown', function(e) { if (e.key === 'Enter') { e.preventDefault(); fn(); } }); }

    on('tpid-close', 'click', TPID.close.bind(TPID));
    on('tpid-backdrop', 'click', function(e) { if (e.target === $id('tpid-backdrop')) TPID.close(); });

    on('tpid-s1-next', 'click', goStep2);
    onKey('tpid-email', goStep2);
    on('tpid-to-reg', 'click', goStep4);

    on('tpid-s2-back', 'click', goStep1);
    on('tpid-s2-submit', 'click', handleLoginSubmit);
    onKey('tpid-pass', handleLoginSubmit);
    onKey('tpid-captcha-input', handleLoginSubmit);
    on('tpid-eye', 'click', function() { toggleEye('tpid-pass', 'tpid-eye-icon'); });
    on('tpid-captcha-refresh', 'click', function() {
      _captchaAnswer = refreshCaptcha('tpid-captcha-code', 'tpid-captcha-input');
    });

    on('tpid-s3-back', 'click', function() { showStep(2); });
    on('tpid-s3-submit', 'click', handleTFASubmit);
    onKey('tpid-tfa', handleTFASubmit);

    on('tpid-s4-back', 'click', goStep1);
    on('tpid-s4-submit', 'click', handleRegisterSubmit);
    on('tpid-to-login', 'click', goStep1);
    on('tpid-reg-eye', 'click', function() { toggleEye('tpid-reg-pass', 'tpid-reg-eye-icon'); });
    on('tpid-reg-captcha-refresh', 'click', function() {
      _regCaptchaAnswer = refreshCaptcha('tpid-reg-captcha-code', 'tpid-reg-captcha-input');
    });

    // Escape key
    d.addEventListener('keydown', function(e) {
      if (e.key === 'Escape') TPID.close();
    });
  }

  // ─── Public API ──────────────────────────────────────────────────────────────
  var TPID = {
    version: WIDGET_VERSION,
    /**
     * @param {object} cfg
     * @param {string} cfg.clientId
     * @param {function} [cfg.onSuccess] - called with { user, accessToken, refreshToken }
     * @param {function} [cfg.onError]
     * @param {string} [cfg.redirectUri]
     * @param {string} [cfg.lang] - 'ru'|'en'
     */
    init: function(cfg) {
      _cfg = cfg || {};
      _lang = (cfg && cfg.lang) || 'ru';
      _theme = (cfg && cfg.theme) || 'dark';
      if (_theme === 'auto') _theme = (w.matchMedia && w.matchMedia('(prefers-color-scheme: light)').matches) ? 'light' : 'dark';
      injectStyles();
      injectModal();
      if (cfg && cfg.autoButton !== false) {
        this._autoButton();
      }
      // Auto-update check (non-blocking)
      this._checkUpdate();
    },

    _checkUpdate: function() {
      try {
        fetch(API + '/sdk/version').then(function(r) { return r.json(); }).then(function(data) {
          if (data.widget && data.widget !== WIDGET_VERSION) {
            console.warn('[TPID] Widget update available: v' + WIDGET_VERSION + ' → v' + data.widget + '. Update: ' + (data.widget_url || ORIGIN + '/sdk/tpid-widget.js'));
            if (data.breaking_changes) {
              console.error('[TPID] BREAKING CHANGES in new version. Please update immediately.');
            }
          }
        }).catch(function() {});
      } catch(e) {}
    },

    setTheme: function(theme) {
      _theme = theme;
      if (_theme === 'auto') _theme = (w.matchMedia && w.matchMedia('(prefers-color-scheme: light)').matches) ? 'light' : 'dark';
      applyTheme();
    },

    setLang: function(lang) {
      _lang = lang || 'ru';
      applyLang();
    },

    open: function() {
      injectStyles();
      injectModal();
      goStep1();
      const backdrop = $id('tpid-backdrop');
      if (backdrop) {
        backdrop.style.display = 'flex';
        requestAnimationFrame(function() {
          requestAnimationFrame(function() {
            backdrop.classList.add('tpid-open');
          });
        });
        d.body.style.overflow = 'hidden';
      }
    },

    close: function() {
      const backdrop = $id('tpid-backdrop');
      if (backdrop) {
        backdrop.classList.remove('tpid-open');
        setTimeout(function() {
          backdrop.style.display = 'none';
          d.body.style.overflow = '';
        }, 300);
      }
    },

    /**
     * Open a native browser popup window for login — enterprise-grade UX
     * Like Google/Apple/Facebook login popup
     * @param {object} [options] - { onSuccess, onError, onClose, theme, lang }
     * @returns {Window} popup window reference
     */
    openPopup: function(options) {
      var opts = options || {};
      var onSuccess = opts.onSuccess || _cfg.onSuccess || function(){};
      var onError = opts.onError || _cfg.onError || function(){};
      var onClose = opts.onClose || function(){};
      var theme = opts.theme || _theme || 'dark';
      var lang = opts.lang || _lang || 'ru';

      var W = 480, H = 640;
      var left = Math.max(0, Math.round(w.screen.width / 2 - W / 2));
      var top = Math.max(0, Math.round(w.screen.height / 2 - H / 2));
      var features = 'width=' + W + ',height=' + H + ',left=' + left + ',top=' + top +
        ',menubar=no,toolbar=no,location=no,status=no,scrollbars=yes,resizable=yes';

      var popupUrl = ORIGIN + '/login?popup=1&theme=' + theme + '&lang=' + lang +
        '&cb=' + encodeURIComponent(w.location.origin);

      var popup = w.open(popupUrl, 'tpid_login_popup', features);
      if (!popup) {
        onError(new Error('popup_blocked'));
        return null;
      }

      var resolved = false;
      var pollTimer = setInterval(function() {
        if (!popup || popup.closed) {
          clearInterval(pollTimer);
          w.removeEventListener('message', onMsg);
          if (!resolved) onClose();
        }
      }, 500);

      function onMsg(ev) {
        if (!ev.data) return;
        var origin = ev.origin;
        if (origin !== ORIGIN && origin !== 'https://auth.tokenpay.space' && origin !== 'https://id.tokenpay.space') return;
        if (ev.data.type === 'TPID_LOGIN_SUCCESS') {
          resolved = true;
          clearInterval(pollTimer);
          w.removeEventListener('message', onMsg);
          try { popup.close(); } catch(e) {}
          onSuccess(ev.data);
        } else if (ev.data.type === 'TPID_LOGIN_ERROR') {
          resolved = true;
          clearInterval(pollTimer);
          w.removeEventListener('message', onMsg);
          onError(new Error(ev.data.message || 'login_failed'));
        } else if (ev.data.type === 'TPID_POPUP_READY') {
          popup.focus();
        }
      }
      w.addEventListener('message', onMsg);
      return popup;
    },

    /**
     * Inline SVG shield icon — no external image dependency
     */
    _shieldSVG: function(size) {
      size = size || 20;
      return '<svg class="tpid-btn-icon" width="' + size + '" height="' + size + '" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">' +
        '<path d="M12 2L3 7v5c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V7l-9-5z" fill="currentColor" opacity=".15"/>' +
        '<path d="M12 2L3 7v5c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V7l-9-5z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" fill="none"/>' +
        '<path d="M9.5 12.5l2 2 3.5-4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" fill="none"/>' +
        '</svg>';
    },

    /**
     * Render a standard "Sign in with TOKEN PAY ID" button
     * @param {string|Element} selector - CSS selector or DOM element
     * @param {object} [options] - { label, theme, size, onClick }
     */
    renderButton: function(selector, options) {
      var container = typeof selector === 'string' ? d.querySelector(selector) : selector;
      if (!container) return null;
      var opts = options || {};
      var btn = d.createElement('button');
      btn.className = 'tpid-trigger-btn';
      btn.type = 'button';
      btn.innerHTML = this._shieldSVG(20) + '<span>' + _esc(opts.label || t('btnLabel')) + '</span>';
      if (opts.theme === 'light' || (_theme === 'light' && opts.theme !== 'dark')) btn.classList.add('tpid-light');
      btn.onclick = opts.onClick || function() { TPID.open(); };
      container.appendChild(btn);
      return btn;
    },

    /**
     * Render a round icon-only button (perfect for navbars)
     * @param {string|Element} selector
     * @param {object} [options] - { size: 'sm'|'md'|'lg', theme, onClick, title }
     */
    renderIconButton: function(selector, options) {
      var container = typeof selector === 'string' ? d.querySelector(selector) : selector;
      if (!container) return null;
      var opts = options || {};
      var sizes = { sm: 18, md: 22, lg: 26 };
      var iconSize = sizes[opts.size] || sizes.md;
      var btn = d.createElement('button');
      btn.className = 'tpid-icon-btn';
      if (opts.size === 'sm') btn.classList.add('tpid-icon-sm');
      if (opts.size === 'lg') btn.classList.add('tpid-icon-lg');
      btn.type = 'button';
      btn.title = opts.title || t('btnLabel');
      btn.setAttribute('aria-label', opts.title || t('btnLabel'));
      btn.innerHTML = this._shieldSVG(iconSize);
      if (opts.theme === 'light' || (_theme === 'light' && opts.theme !== 'dark')) btn.classList.add('tpid-light');
      btn.onclick = opts.onClick || function() { TPID.open(); };
      container.appendChild(btn);
      return btn;
    },

    /**
     * Render a transparent logo button (TOKEN PAY ID text + shield icon)
     * @param {string|Element} selector
     * @param {object} [options] - { label, theme, onClick }
     */
    renderLogoButton: function(selector, options) {
      var container = typeof selector === 'string' ? d.querySelector(selector) : selector;
      if (!container) return null;
      var opts = options || {};
      var btn = d.createElement('button');
      btn.className = 'tpid-logo-btn';
      btn.type = 'button';
      btn.innerHTML = this._shieldSVG(20) + '<span>' + _esc(opts.label || 'TOKEN PAY ID') + '</span>';
      if (opts.theme === 'light' || (_theme === 'light' && opts.theme !== 'dark')) btn.classList.add('tpid-light');
      btn.onclick = opts.onClick || function() { TPID.open(); };
      container.appendChild(btn);
      return btn;
    },

    /**
     * OAuth popup flow — opens OAuth consent in popup, resolves with auth code
     * Enterprise calls: TPID.loginWithOAuth({ clientId, redirectUri, scope, state })
     * @returns {Promise<{code, state}>}
     */
    loginWithOAuth: function(options) {
      var opts = options || _cfg;
      var clientId = opts.clientId || _cfg.clientId;
      var redirectUri = opts.redirectUri || _cfg.redirectUri;
      var scope = opts.scope || 'profile';
      var state = opts.state || ('tpid_' + Math.random().toString(36).slice(2, 10));
      var codeChallenge = opts.codeChallenge || '';
      var codeChallengeMethod = opts.codeChallengeMethod || 'S256';
      if (!clientId) {
        return Promise.reject(new Error('clientId is required'));
      }
      var url = ORIGIN + '/api/v1/oauth/authorize?response_type=code&client_id=' +
        encodeURIComponent(clientId) + '&scope=' + encodeURIComponent(scope) +
        '&state=' + encodeURIComponent(state) +
        '&prompt=login';
      if (redirectUri) url += '&redirect_uri=' + encodeURIComponent(redirectUri);
      if (codeChallenge) url += '&code_challenge=' + encodeURIComponent(codeChallenge) + '&code_challenge_method=' + encodeURIComponent(codeChallengeMethod);

      var w2 = w.open(url, 'tpid_oauth', 'width=480,height=640,menubar=no,toolbar=no,location=yes,status=no');
      return new Promise(function(resolve, reject) {
        var resolved = false;
        function onMessage(ev) {
          if (!ev.data || ev.data.type !== 'tpid_oauth_code') return;
          resolved = true;
          w.removeEventListener('message', onMessage);
          clearInterval(pollTimer);
          if (ev.data.error) {
            reject(new Error(ev.data.error));
          } else {
            resolve({ code: ev.data.code, state: ev.data.state, redirect_url: ev.data.redirect_url });
          }
        }
        w.addEventListener('message', onMessage);
        var pollTimer = setInterval(function() {
          if (!w2 || w2.closed) {
            clearInterval(pollTimer);
            w.removeEventListener('message', onMessage);
            if (!resolved) reject(new Error('popup_closed'));
          }
        }, 500);
      });
    },

    _autoButton: function() {
      var containers = d.querySelectorAll('[data-tpid-button]');
      var self = this;
      containers.forEach(function(c) {
        var variant = c.getAttribute('data-tpid-button') || 'standard';
        var label = c.getAttribute('data-tpid-label');
        var size = c.getAttribute('data-tpid-size') || 'md';
        var btnTheme = c.getAttribute('data-tpid-theme');
        var opts = { theme: btnTheme, size: size };
        if (label) opts.label = label;
        if (variant === 'icon') {
          self.renderIconButton(c, opts);
        } else if (variant === 'logo') {
          self.renderLogoButton(c, opts);
        } else {
          self.renderButton(c, opts);
        }
      });
    }
  };

  // ─── Auto-init from script tag ───────────────────────────────────────────────
  (function() {
    var scripts = d.querySelectorAll('script[src*="tpid-widget"]');
    var script = scripts[scripts.length - 1];
    if (script && script.dataset.clientId) {
      var onSuccess = w.TPIDConfig && w.TPIDConfig.onSuccess;
      var redirectUri = (w.TPIDConfig && w.TPIDConfig.redirectUri) || script.dataset.redirectUri;
      TPID.init({
        clientId: script.dataset.clientId,
        onSuccess: onSuccess,
        redirectUri: redirectUri,
        autoButton: true
      });
    }
  })();

  w.TPID = TPID;

})(window, document);
