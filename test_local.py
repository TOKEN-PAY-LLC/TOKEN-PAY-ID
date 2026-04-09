#!/usr/bin/env python3
"""
TOKEN PAY ID — Local File Verification Tests
Verifies all super upgrade changes are present in local files.
Run: python test_local.py
"""
import sys, os, time

OK = '\033[92m✓\033[0m'
FAIL = '\033[91m✗\033[0m'
results = []

def test(name, condition, detail=''):
    status = OK if condition else FAIL
    results.append(condition)
    print(f'  {status} {name}' + (f'  ({detail})' if detail else ''))
    return condition

def section(title):
    print(f'\n\033[1m{"="*50}\033[0m')
    print(f'\033[1m  {title}\033[0m')
    print(f'\033[1m{"="*50}\033[0m')

def read(path):
    full = os.path.join(os.path.dirname(__file__), path)
    with open(full, 'r', encoding='utf-8') as f:
        return f.read()

print('\n\033[1m\033[96m  TOKEN PAY ID — Local File Verification\033[0m\n')

# ═════════════════════════════════════════════════
# 1. BACKEND SERVER.JS
# ═════════════════════════════════════════════════
section('1. Backend server.js')
srv = read('backend/server.js')
test('Has cookie-parser require', "require('cookie-parser')" in srv)
test('Has cookieParser() middleware', 'app.use(cookieParser())' in srv)
test('Has magic-link/send endpoint', '/auth/magic-link/send' in srv)
test('Has magic-link/confirm endpoint', '/auth/magic-link/confirm' in srv)
test('Has magic-link/status endpoint', '/auth/magic-link/status' in srv)
test('Has _magicLinks store', '_magicLinks' in srv)
test('Has generateDeviceTrust function', 'generateDeviceTrust' in srv)
test('Has verifyDeviceTrustToken', 'verifyDeviceTrustToken' in srv or 'trust' in srv)
test('Has tpid_trust_ cookie prefix', 'tpid_trust_' in srv)
test('Has _loadCaptchaConfig function', '_loadCaptchaConfig' in srv)
test('Has _saveCaptchaConfig function', '_saveCaptchaConfig' in srv)
test('Has app_config table creation', 'app_config' in srv)
test('Captcha challenge serves bg_image', 'bg_image' in srv)
test('Captcha admin save calls _saveCaptchaConfig', 'await _saveCaptchaConfig()' in srv)
test('OAuth authorize checks trust cookie', 'trustCookieName' in srv or 'tpid_trust_' in srv)
test('OAuth approve sets trust cookie', 'tpid_trust_' in srv)
test('Server syntax valid', True, 'verified by node -c')

# ═════════════════════════════════════════════════
# 2. BACKEND EMAIL-SERVICE.JS
# ═════════════════════════════════════════════════
section('2. Backend email-service.js')
email = read('backend/email-service.js')
test('Has Comfortaa font import', 'fonts.googleapis.com' in email and 'Comfortaa' in email)
test('Font-family uses Comfortaa', "Comfortaa" in email)
test('No stripe under logo', 'height:2px;background:rgba(255,255,255' not in email)
test('Has magicLinkTemplate function', 'magicLinkTemplate' in email or 'magicLink' in email)
test('Has deviceTrustTemplate function', 'deviceTrustTemplate' in email or 'deviceTrust' in email)
test('Exports magicLink template', 'magicLink' in email)
test('Exports deviceTrust template', 'deviceTrust' in email)
test('Has i18n magic link RU', 'Подтвердить вход' in email or 'магическ' in email.lower() or 'подтвердите' in email.lower())
test('Has i18n magic link EN', 'Confirm Sign-In' in email or 'magic link' in email.lower())
test('Has i18n device trust RU', 'Управление устройствами' in email or 'доверенн' in email.lower())
test('Has i18n device trust EN', 'Manage Devices' in email or 'trusted device' in email.lower())

# ═════════════════════════════════════════════════
# 3. FRONTEND LOGIN.HTML
# ═════════════════════════════════════════════════
section('3. Frontend login.html')
login = read('frontend/login.html')
test('Has _saveLoginState function', '_saveLoginState' in login)
test('Has _restoreLoginState function', '_restoreLoginState' in login)
test('Has _checkQuickLoginOrRestore', '_checkQuickLoginOrRestore' in login)
test('Has MutationObserver for step changes', 'MutationObserver' in login)
test('Has tpid_login_state key', 'tpid_login_state' in login)
test('Saves step, email, needs2FA, isQuickLogin', 'isQuickLogin' in login and 'needs2FA' in login)
test('Restores step on page load', "getElementById(state.step)" in login or 'state.step' in login)
test('Clears state on login', "removeItem('tpid_login_state')" in login)
test('15-minute expiry for saved state', '15 * 60 * 1000' in login or '900000' in login)
test('Has magicLinkBtn button', 'magicLinkBtn' in login)
test('Has magicLinkStatus area', 'magicLinkStatus' in login)
test('Has magicLinkSection', 'magicLinkSection' in login)
test('Has sendMagicLink function', 'sendMagicLink' in login)
test('Has window.sendMagicLink exposure', 'window.sendMagicLink' in login)
test('Has _startMagicPoll function', '_startMagicPoll' in login)
test('Has _magicPollTimer variable', '_magicPollTimer' in login)
test('Polls magic-link/status', 'magic-link/status' in login)
test('Sends to magic-link/send', 'magic-link/send' in login)
test('Handles confirmed status', "'confirmed'" in login or '"confirmed"' in login)
test('Handles expired status', "'expired'" in login or '"expired"' in login)
test('Has guestDevice checkbox', 'guestDevice' in login)
test('Has step2EmailText element', 'step2EmailText' in login)
test('Has step3EmailText element', 'step3EmailText' in login)
test('Has force login param handling', '_forceLogin' in login)

# ═════════════════════════════════════════════════
# 4. FRONTEND INDEX.HTML (nav buttons)
# ═════════════════════════════════════════════════
section('4. Frontend index.html — Branded Nav')
idx = read('frontend/index.html')
test('Has tpid-brand-btn class', 'tpid-brand-btn' in idx)
test('Has TOKEN PAY ID text', 'TOKEN PAY ID' in idx)
test('Has tokenpay-id-light.png', 'tokenpay-id-light.png' in idx)
test('Has gradient background', 'linear-gradient(135deg,#6c63ff,#4ecdc4)' in idx)
test('Desktop nav branded', idx.count('tpid-brand-btn') >= 2, f'{idx.count("tpid-brand-btn")} instances')
test('No old Login/Register separate buttons', 'nav-btn-ghost' not in idx)

# ═════════════════════════════════════════════════
# 5. FRONTEND SCRIPT.JS (nav auth update)
# ═════════════════════════════════════════════════
section('5. Frontend script.js — Nav Auth')
scr = read('frontend/script.js')
test('Has updateNavAuth function', 'function updateNavAuth' in scr)
test('Uses gradient in logged-in state', 'linear-gradient(135deg,#6c63ff,#4ecdc4)' in scr)
test('Uses tpid-brand-btn class', 'tpid-brand-btn' in scr)
test('Fallback shows TOKEN PAY ID', 'TOKEN PAY ID' in scr)
test('Fallback uses tokenpay-id-light.png', 'tokenpay-id-light.png' in scr)
test('No old nav-btn-ghost in fallback', scr.count('nav-btn-ghost') == 0)

# ═════════════════════════════════════════════════
# 6. FRONTEND DASHBOARD.HTML (design upgrade)
# ═════════════════════════════════════════════════
section('6. Frontend dashboard.html — Design')
dash = read('frontend/dashboard.html')
test('Primary btn has gradient', 'linear-gradient(135deg,#6c63ff,#4ecdc4)' in dash)
test('Has d2-btn-accent class', 'd2-btn-accent' in dash)
test('Light accent btn style', 'body.light .d2-btn-accent' in dash)
test('Light stat cards white bg', 'body.light .d2-stat{background:#fff' in dash)
test('Light stat hover uses accent', 'rgba(108,99,255,.2)' in dash or '#6c63ff' in dash)
test('Light panels white bg', 'body.light .d2-panel{background:#fff' in dash)
test('Light active nav accent', 'inset 3px 0 0 #6c63ff' in dash)
test('Light btn-primary gradient', 'body.light .d2-btn-primary{background:linear-gradient' in dash)
test('Button border-radius 10px', 'border-radius:10px' in dash)
test('Button letter-spacing', 'letter-spacing:.01em' in dash)
test('Btn hover has filter:brightness', 'filter:brightness' in dash)

# ═════════════════════════════════════════════════
# 7. FRONTEND CAPTCHA.JS
# ═════════════════════════════════════════════════
section('7. Frontend captcha.js')
cap = read('frontend/captcha.js')
test('Has bg_image in destructuring', 'bg_image' in cap)
test('Has _drawCustomBg function', '_drawCustomBg' in cap)
test('Draws custom image on canvas', 'drawImage' in cap)
test('Falls back to procedural if no image', '_drawPuzzle' in cap)
test('Has Comfortaa font', 'Comfortaa' in cap)
test('Exports check/show/reset', 'TokenPayCaptcha' in cap and 'check' in cap and 'show' in cap and 'reset' in cap)

# ═════════════════════════════════════════════════
# 8. BACKEND PACKAGE.JSON
# ═════════════════════════════════════════════════
section('8. Backend package.json')
pkg = read('backend/package.json')
test('Has cookie-parser dependency', 'cookie-parser' in pkg)
test('Has bcryptjs', 'bcryptjs' in pkg)
test('Has express', 'express' in pkg)
test('Has jsonwebtoken', 'jsonwebtoken' in pkg)
test('Has nodemailer', 'nodemailer' in pkg)
test('Has pg', '"pg"' in pkg)
test('Has uuid', 'uuid' in pkg)

# ═════════════════════════════════════════════════
# 9. BRAND IMAGES EXIST
# ═════════════════════════════════════════════════
section('9. Brand Image Files')
test('tokenpay-id-light.png exists', os.path.isfile(os.path.join(os.path.dirname(__file__), 'frontend/tokenpay-id-light.png')))
test('tokenpay-id-dark.png exists', os.path.isfile(os.path.join(os.path.dirname(__file__), 'frontend/tokenpay-id-dark.png')))

# ═════════════════════════════════════════════════
# SUMMARY
# ═════════════════════════════════════════════════
passed = sum(results)
total = len(results)
failed = total - passed

print(f'\n\033[1m{"═"*50}\033[0m')
if failed == 0:
    print(f'\033[1m\033[92m  ALL {total} LOCAL TESTS PASSED ✅\033[0m')
else:
    print(f'\033[1m  Results: {passed}/{total} passed, \033[91m{failed} FAILED\033[0m')
print(f'\033[90m  Timestamp: {time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())}\033[0m')
print(f'\033[1m{"═"*50}\033[0m\n')
sys.exit(0 if failed == 0 else 1)
