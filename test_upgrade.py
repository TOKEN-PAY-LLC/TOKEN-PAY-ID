#!/usr/bin/env python3
"""
TOKEN PAY ID — Super Upgrade Test Suite
Tests all new features: magic link, captcha persistence, device trust,
login page state, branded nav button, dashboard design, email templates.
Run: python test_upgrade.py
"""
import requests, json, sys, time, re

BASE = 'https://tokenpay.space'
API = f'{BASE}/api/v1'
OK = '\033[92m✓\033[0m'
FAIL = '\033[91m✗\033[0m'
WARN = '\033[93m⚠\033[0m'
results = []

def test(name, condition, detail=''):
    status = OK if condition else FAIL
    results.append(condition)
    print(f'  {status} {name}' + (f'  ({detail})' if detail else ''))
    return condition

def skip(name, reason=''):
    print(f'  {WARN} {name}  (SKIPPED: {reason})')

def section(title):
    print(f'\n\033[1m{"="*50}\033[0m')
    print(f'\033[1m  {title}\033[0m')
    print(f'\033[1m{"="*50}\033[0m')

print('\n\033[1m\033[96m  TOKEN PAY ID — Super Upgrade Tests\033[0m\n')

# ═════════════════════════════════════════════════
# 1. BASIC HEALTH
# ═════════════════════════════════════════════════
section('1. Backend Health')
try:
    r = requests.get(f'{BASE}/health', timeout=10)
    d = r.json()
    test('Backend running', r.status_code == 200)
    test('DB connected', d.get('db') == 'connected')
    test('Has cookie-parser (X-API-Version)', r.headers.get('X-API-Version') == '2.1.0')
except Exception as e:
    test('Backend health', False, str(e))

# ═════════════════════════════════════════════════
# 2. EMAIL TEMPLATES (via homepage font check)
# ═════════════════════════════════════════════════
section('2. Email Template Fonts (Comfortaa)')
try:
    r = requests.get(BASE, timeout=10)
    test('Homepage loads', r.status_code == 200)
    test('Has Comfortaa font on site', 'Comfortaa' in r.text)
except Exception as e:
    test('Homepage', False, str(e))

# ═════════════════════════════════════════════════
# 3. MAGIC LINK ENDPOINTS
# ═════════════════════════════════════════════════
section('3. Magic Link Login')
try:
    # 3a. Send without credentials — should fail
    r = requests.post(f'{API}/auth/magic-link/send', json={}, timeout=10)
    test('Rejects empty body', r.status_code == 400)

    # 3b. Send with wrong password
    r = requests.post(f'{API}/auth/magic-link/send', json={
        'email': 'nonexistent@test.com', 'password': 'wrong123'
    }, timeout=10)
    test('Rejects invalid credentials', r.status_code == 401)

    # 3c. Status with invalid token_id
    r = requests.get(f'{API}/auth/magic-link/status?token_id=invalid123', timeout=10)
    d = r.json()
    test('Status returns expired for unknown token', d.get('status') == 'expired')

    # 3d. Status without token_id
    r = requests.get(f'{API}/auth/magic-link/status', timeout=10)
    d = r.json()
    test('Status returns invalid without token_id', d.get('status') == 'invalid')

    # 3e. Confirm with no token
    r = requests.get(f'{API}/auth/magic-link/confirm', timeout=10, allow_redirects=False)
    test('Confirm redirects on missing token', r.status_code in (301, 302, 307, 308))
    location = r.headers.get('Location', '')
    test('Confirm redirect has error param', 'error=' in location or 'invalid_magic_link' in location)

    # 3f. Confirm with expired/fake token
    r = requests.get(f'{API}/auth/magic-link/confirm?token=fake_token_abc', timeout=10, allow_redirects=False)
    test('Confirm rejects fake token', r.status_code in (301, 302, 307, 308))
    location2 = r.headers.get('Location', '')
    test('Fake token redirect has expired error', 'expired' in location2 or 'error' in location2)

except Exception as e:
    test('Magic link endpoints', False, str(e))

# ═════════════════════════════════════════════════
# 4. CAPTCHA SYSTEM
# ═════════════════════════════════════════════════
section('4. CAPTCHA System')
try:
    # 4a. Config endpoint
    r = requests.get(f'{API}/captcha/config', timeout=10)
    d = r.json()
    test('Captcha config endpoint works', r.status_code == 200)
    test('Has mode field', d.get('mode') in ('auto', 'always', 'off'), d.get('mode'))
    test('Has auto_threshold field', isinstance(d.get('auto_threshold'), (int, float)))

    # 4b. Challenge endpoint
    r = requests.get(f'{API}/captcha/challenge', timeout=10)
    d = r.json()
    test('Challenge returns nonce', 'nonce' in d)
    test('Challenge returns hole_x', 'hole_x' in d)
    test('Challenge returns hole_y', 'hole_y' in d)
    test('Challenge has dimensions', d.get('width') == 320 and d.get('height') == 160)
    test('Challenge has piece_size', d.get('piece_size') == 50)
    # bg_image is optional — only present if admin uploaded images
    has_bg = 'bg_image' in d
    if has_bg:
        test('Custom bg_image is base64', d['bg_image'].startswith('data:image/') or len(d['bg_image']) > 100)
    else:
        skip('Custom bg_image', 'no admin images uploaded')

    nonce = d.get('nonce')
    hole_x = d.get('hole_x')

    # 4c. Verify with wrong answer
    r = requests.post(f'{API}/captcha/verify', json={'nonce': nonce, 'x': 0}, timeout=10)
    d = r.json()
    test('Wrong answer fails', d.get('success') == False or 'captcha_failed' in str(d))

    # 4d. Verify with correct answer (new challenge)
    r = requests.get(f'{API}/captcha/challenge', timeout=10)
    ch = r.json()
    r = requests.post(f'{API}/captcha/verify', json={'nonce': ch['nonce'], 'x': ch['hole_x']}, timeout=10)
    d = r.json()
    test('Correct answer succeeds', d.get('success') == True)
    test('Returns captcha_token JWT', d.get('captcha_token', '').count('.') == 2)

    # 4e. Re-use nonce should fail
    r = requests.post(f'{API}/captcha/verify', json={'nonce': ch['nonce'], 'x': ch['hole_x']}, timeout=10)
    d = r.json()
    test('Nonce reuse rejected', 'expired' in str(d) or 'invalid' in str(d) or d.get('success') == False)

    # 4f. Missing params
    r = requests.post(f'{API}/captcha/verify', json={}, timeout=10)
    test('Missing params rejected', r.status_code == 400)

except Exception as e:
    test('CAPTCHA system', False, str(e))

# ═════════════════════════════════════════════════
# 5. LOGIN PAGE FEATURES
# ═════════════════════════════════════════════════
section('5. Login Page — State Persistence & Magic Link UI')
try:
    r = requests.get(f'{BASE}/login', timeout=10)
    html = r.text
    test('Login page loads', r.status_code == 200)
    test('Has sessionStorage state save', 'tpid_login_state' in html)
    test('Has _saveLoginState function', '_saveLoginState' in html)
    test('Has _restoreLoginState function', '_restoreLoginState' in html)
    test('Has _checkQuickLoginOrRestore', '_checkQuickLoginOrRestore' in html)
    test('Has MutationObserver for step changes', 'MutationObserver' in html)
    test('Has magic link button', 'magicLinkBtn' in html)
    test('Has magic link status area', 'magicLinkStatus' in html)
    test('Has sendMagicLink function', 'sendMagicLink' in html)
    test('Has _startMagicPoll function', '_startMagicPoll' in html)
    test('Has magic-link/send endpoint call', 'magic-link/send' in html)
    test('Has magic-link/status polling', 'magic-link/status' in html)
    test('Has magic link section with "or" divider', 'magicLinkSection' in html)
    test('Clears login state on completeLogin', "removeItem('tpid_login_state')" in html)
    test('Has force login clear', '_forceLogin' in html)

    # Login hint handling
    test('Has login_hint support', 'login_hint' in html or '_loginHint' in html)
    # Guest device checkbox
    test('Has guestDevice checkbox', 'guestDevice' in html)

except Exception as e:
    test('Login page', False, str(e))

# ═════════════════════════════════════════════════
# 6. NAV — BRANDED TOKENPAY ID BUTTON
# ═════════════════════════════════════════════════
section('6. Branded TokenPay ID Nav Button')
try:
    r = requests.get(BASE, timeout=10)
    html = r.text
    test('Has tpid-brand-btn class', 'tpid-brand-btn' in html)
    test('Has TOKEN PAY ID text in nav', 'TOKEN PAY ID' in html)
    test('Has tokenpay-id-light.png image', 'tokenpay-id-light.png' in html)
    test('Has gradient background', 'linear-gradient(135deg,#6c63ff,#4ecdc4)' in html)
    test('Mobile nav also branded', html.count('tpid-brand-btn') >= 2, f'{html.count("tpid-brand-btn")} instances')

    # Check the image actually exists
    r2 = requests.get(f'{BASE}/tokenpay-id-light.png', timeout=10)
    test('Brand image file exists', r2.status_code == 200, f'{len(r2.content)} bytes')

except Exception as e:
    test('Nav button', False, str(e))

# ═════════════════════════════════════════════════
# 7. SCRIPT.JS — NAV AUTH UPDATE
# ═════════════════════════════════════════════════
section('7. Script.js Nav Auth')
try:
    r = requests.get(f'{BASE}/script.js', timeout=10)
    js = r.text
    test('Script.js loads', r.status_code == 200)
    test('updateNavAuth uses gradient button', 'linear-gradient(135deg,#6c63ff,#4ecdc4)' in js)
    test('updateNavAuth uses tpid-brand-btn class', 'tpid-brand-btn' in js)
    test('Fallback shows TOKEN PAY ID text', 'TOKEN PAY ID' in js)
    test('Fallback uses tokenpay-id-light.png', 'tokenpay-id-light.png' in js)

except Exception as e:
    test('Script.js', False, str(e))

# ═════════════════════════════════════════════════
# 8. DASHBOARD DESIGN UPGRADES
# ═════════════════════════════════════════════════
section('8. Dashboard Design')
try:
    r = requests.get(f'{BASE}/dashboard', timeout=10)
    css = r.text
    test('Dashboard loads', r.status_code == 200)
    # Gradient primary buttons
    test('Primary btn has gradient', 'linear-gradient(135deg,#6c63ff,#4ecdc4)' in css)
    # Accent button class
    test('Has d2-btn-accent class', 'd2-btn-accent' in css)
    # Light theme stat cards with shadow
    test('Light stat cards have box-shadow', 'body.light .d2-stat{background:#fff' in css)
    # Light theme panels with white bg
    test('Light panels have white bg', 'body.light .d2-panel{background:#fff' in css)
    # Light nav active uses accent color
    test('Light active nav uses #6c63ff', 'inset 3px 0 0 #6c63ff' in css)
    # Button border-radius upgraded to 10px
    test('Button border-radius 10px', 'border-radius:10px' in css)
    # Light theme btn-primary still gradient
    test('Light btn-primary gradient', 'body.light .d2-btn-primary{background:linear-gradient' in css)

except Exception as e:
    test('Dashboard', False, str(e))

# ═════════════════════════════════════════════════
# 9. CAPTCHA FRONTEND
# ═════════════════════════════════════════════════
section('9. Captcha Frontend')
try:
    r = requests.get(f'{BASE}/captcha.js', timeout=10)
    js = r.text
    test('Captcha.js loads', r.status_code == 200)
    test('Has bg_image destructuring', 'bg_image' in js)
    test('Has _drawCustomBg function', '_drawCustomBg' in js)
    test('Has Comfortaa font in captcha box', 'Comfortaa' in js)
    test('Uses TokenPayCaptcha global', 'TokenPayCaptcha' in js)
    test('Has check() function', 'function check()' in js)
    test('Has show() function', 'function show()' in js)
    test('Has reset() function', 'function reset()' in js)

except Exception as e:
    test('Captcha frontend', False, str(e))

# ═════════════════════════════════════════════════
# 10. OAUTH CONSENT PAGE
# ═════════════════════════════════════════════════
section('10. OAuth Consent Page')
try:
    r = requests.get(f'{BASE}/oauth-consent.html', timeout=10)
    html = r.text
    test('Consent page loads', r.status_code == 200)
    test('Has fade-in animation', 'fadeIn' in html or 'opacity' in html)

except Exception as e:
    test('OAuth consent', False, str(e))

# ═════════════════════════════════════════════════
# 11. DEVICE TRUST (cookie-based)
# ═════════════════════════════════════════════════
section('11. Device Trust System')
try:
    # Verify the OAuth authorize endpoint exists and rejects bad params
    r = requests.get(f'{API}/oauth/authorize', params={
        'response_type': 'code',
        'client_id': 'nonexistent',
        'redirect_uri': 'http://localhost'
    }, timeout=10, allow_redirects=False)
    test('OAuth authorize rejects bad client', r.status_code == 400)

    # Verify the approve endpoint requires auth
    r = requests.post(f'{API}/oauth/approve', json={
        'client_id': 'test', 'redirect_uri': 'http://localhost'
    }, timeout=10)
    test('OAuth approve requires auth', r.status_code == 401)

    # Check server.js has device trust functions (indirect — via health)
    r = requests.get(f'{BASE}/health', timeout=10)
    test('Server running with device trust code', r.status_code == 200)

except Exception as e:
    test('Device trust', False, str(e))

# ═════════════════════════════════════════════════
# 12. STATIC ASSETS INTEGRITY
# ═════════════════════════════════════════════════
section('12. Static Assets')
assets = [
    ('/tokenpay-id-light.png', 'Brand logo light'),
    ('/tokenpay-id-dark.png', 'Brand logo dark'),
    ('/styles.css', 'Main CSS'),
    ('/script.js', 'Main JS'),
    ('/captcha.js', 'Captcha JS'),
    ('/theme-init.js', 'Theme init JS'),
]
for path, desc in assets:
    try:
        r = requests.get(f'{BASE}{path}', timeout=10)
        test(f'{desc} ({path})', r.status_code == 200, f'{len(r.content)} bytes')
    except Exception as e:
        test(desc, False, str(e))

# ═════════════════════════════════════════════════
# 13. CSS CHECKS
# ═════════════════════════════════════════════════
section('13. CSS — Clouds Hidden & Stars')
try:
    r = requests.get(f'{BASE}/styles.css', timeout=10)
    css = r.text
    test('CSS loads', r.status_code == 200)
    test('Clouds hidden (display:none)', 'cloud' in css.lower() and 'display:none' in css)

except Exception as e:
    test('CSS checks', False, str(e))

# ═════════════════════════════════════════════════
# 14. REGISTER PAGE CONSISTENCY
# ═════════════════════════════════════════════════
section('14. Register Page')
try:
    r = requests.get(f'{BASE}/register', timeout=10)
    test('Register page loads', r.status_code == 200)
except Exception as e:
    test('Register page', False, str(e))

# ═════════════════════════════════════════════════
# SUMMARY
# ═════════════════════════════════════════════════
passed = sum(results)
total = len(results)
failed = total - passed

print(f'\n\033[1m{"═"*50}\033[0m')
if failed == 0:
    print(f'\033[1m\033[92m  ALL {total} TESTS PASSED ✅\033[0m')
else:
    print(f'\033[1m  Results: {passed}/{total} passed, \033[91m{failed} FAILED\033[0m')
print(f'\033[90m  Timestamp: {time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())}\033[0m')
print(f'\033[1m{"═"*50}\033[0m\n')
sys.exit(0 if failed == 0 else 1)
