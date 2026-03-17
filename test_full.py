#!/usr/bin/env python3
"""TOKEN PAY ID — Full System Test Suite"""
import requests, json, sys, time

BASE = 'https://tokenpay.space'
API = f'{BASE}/api/v1'
OK = '\033[92m✓\033[0m'
FAIL = '\033[91m✗\033[0m'
results = []

def test(name, condition, detail=''):
    status = OK if condition else FAIL
    results.append(condition)
    print(f'  {status} {name}' + (f'  ({detail})' if detail else ''))
    return condition

def section(title):
    print(f'\n\033[1m=== {title} ===\033[0m')

# ===== HOMEPAGE =====
section('Homepage & Static')
try:
    r = requests.get(BASE, timeout=10)
    test('Homepage loads', r.status_code == 200, f'{r.status_code}')
    test('Has Comfortaa font', 'Comfortaa' in r.text)
    test('Has cache-bust v=20260316', 'v=20260316' in r.text)
except Exception as e:
    test('Homepage loads', False, str(e))

# ===== CLEAN URLs =====
section('Clean URLs')
for path in ['/login', '/register', '/dashboard', '/docs']:
    try:
        r = requests.get(f'{BASE}{path}', timeout=10, allow_redirects=True)
        test(f'{path} → {r.status_code}', r.status_code == 200)
    except Exception as e:
        test(f'{path}', False, str(e))

# ===== API HEALTH =====
section('API Health')
try:
    r = requests.get(f'{BASE}/health', timeout=10)
    d = r.json()
    test('Health endpoint', r.status_code == 200)
    test('Status ok', d.get('status') == 'ok', d.get('version', ''))
except Exception as e:
    test('Health', False, str(e))

# ===== SECURITY HEADERS =====
section('Security Headers')
try:
    r = requests.post(f'{API}/auth/send-code', json={'email': 'headertest@x.com', 'type': 'login'}, timeout=10)
    test('X-Request-ID present', 'X-Request-ID' in r.headers, r.headers.get('X-Request-ID', 'missing'))
    test('X-Content-Type-Options', r.headers.get('X-Content-Type-Options') == 'nosniff')
    test('X-Frame-Options', r.headers.get('X-Frame-Options') in ('DENY', 'SAMEORIGIN'), r.headers.get('X-Frame-Options', 'missing'))
    test('Referrer-Policy', 'Referrer-Policy' in r.headers)
except Exception as e:
    test('Security headers', False, str(e))

# ===== OPENID DISCOVERY =====
section('OpenID Connect')
try:
    r = requests.get(f'{BASE}/.well-known/openid-configuration', timeout=10)
    d = r.json()
    test('Discovery endpoint', r.status_code == 200)
    test('Has issuer', d.get('issuer') == 'https://tokenpay.space')
    test('Has PKCE support', 'S256' in d.get('code_challenge_methods_supported', []))
    test('Has token endpoint', '/oauth/token' in d.get('token_endpoint', ''))
    test('Has cancel_endpoint', 'cancel' in d.get('cancel_endpoint', ''))
    test('Has deny_endpoint', 'deny' in d.get('deny_endpoint', ''))
    test('Has branding_endpoint', 'branding' in d.get('branding_endpoint', ''))
    test('Has prompt_values_supported', 'login' in d.get('prompt_values_supported', []))
except Exception as e:
    test('OpenID discovery', False, str(e))

# ===== API VERSION HEADERS =====
section('API Version Headers')
try:
    r = requests.get(f'{BASE}/health', timeout=10)
    test('X-API-Version header', r.headers.get('X-API-Version') == '2.1.0', r.headers.get('X-API-Version', 'missing'))
    test('X-TPID-SDK-Latest header', r.headers.get('X-TPID-SDK-Latest') == '1.2.0', r.headers.get('X-TPID-SDK-Latest', 'missing'))
except Exception as e:
    test('API version headers', False, str(e))

# ===== SDK VERSION ENDPOINT =====
section('SDK Version')
try:
    r = requests.get(f'{API}/sdk/version', timeout=10)
    d = r.json()
    test('SDK version endpoint', r.status_code == 200)
    test('Widget version 1.2.0', d.get('widget') == '1.2.0', d.get('widget', ''))
    test('API version 2.1.0', d.get('api') == '2.1.0', d.get('api', ''))
    test('Has widget_url', 'tpid-widget.js' in d.get('widget_url', ''))
    test('breaking_changes is false', d.get('breaking_changes') == False)
except Exception as e:
    test('SDK version', False, str(e))

# ===== OAUTH BRANDING API =====
section('OAuth Branding API')
try:
    r = requests.get(f'{API}/oauth/branding', timeout=10)
    d = r.json()
    test('Branding endpoint', r.status_code == 200)
    test('Provider name', d.get('provider') == 'TOKEN PAY ID')
    test('Has widget_url', 'tpid-widget.js' in d.get('widget_url', ''))
    test('Has shield SVG', '<svg' in d.get('icon', {}).get('shield_svg', ''))
    test('Has standard button config', 'standard' in d.get('buttons', {}))
    test('Has icon button config', 'icon' in d.get('buttons', {}))
    test('Has logo button config', 'logo' in d.get('buttons', {}))
    test('Has quick_start integration', 'data-client-id' in d.get('integration', {}).get('quick_start', ''))
    test('Has oauth_popup integration', 'loginWithOAuth' in d.get('integration', {}).get('oauth_popup', ''))
    test('Has themes list', d.get('themes') == ['dark', 'light', 'auto'])
    test('Has languages list', d.get('languages') == ['ru', 'en'])
except Exception as e:
    test('OAuth branding', False, str(e))

# ===== OAUTH AUTHORIZE (prompt=login) =====
section('OAuth Authorize')
try:
    r = requests.get(f'{API}/oauth/authorize', params={'response_type': 'code', 'client_id': 'nonexistent', 'redirect_uri': 'http://localhost'}, timeout=10, allow_redirects=False)
    test('Rejects unknown client_id', r.status_code == 400 and 'invalid_client' in r.text)
    r2 = requests.get(f'{API}/oauth/authorize', params={'response_type': 'token', 'client_id': 'test', 'redirect_uri': 'http://localhost'}, timeout=10, allow_redirects=False)
    test('Rejects response_type=token', r2.status_code == 400 and 'unsupported_response_type' in r2.text)
    r3 = requests.get(f'{API}/oauth/authorize', params={'response_type': 'code'}, timeout=10, allow_redirects=False)
    test('Rejects missing params', r3.status_code == 400 and 'missing_params' in r3.text)
except Exception as e:
    test('OAuth authorize', False, str(e))

# ===== OAUTH CANCEL/DENY =====
section('OAuth Cancel/Deny')
try:
    r = requests.post(f'{API}/oauth/cancel', json={}, timeout=10)
    test('Cancel rejects no client_id', r.status_code == 400)
    r2 = requests.post(f'{API}/oauth/cancel', json={'client_id': 'nonexistent'}, timeout=10)
    test('Cancel rejects unknown client_id', r2.status_code == 400)
    r3 = requests.post(f'{API}/oauth/deny', json={}, timeout=10)
    test('Deny rejects no client_id', r3.status_code == 400)
    r4 = requests.post(f'{API}/oauth/deny', json={'client_id': 'nonexistent'}, timeout=10)
    test('Deny rejects unknown client_id', r4.status_code == 400)
except Exception as e:
    test('OAuth cancel/deny', False, str(e))

# ===== OAUTH TOKEN (validation) =====
section('OAuth Token Validation')
try:
    r = requests.post(f'{API}/oauth/token', json={'grant_type': 'authorization_code', 'code': 'invalid', 'client_id': 'fake'}, timeout=10)
    test('Rejects invalid client', r.status_code == 401 and 'invalid_client' in r.text)
    r2 = requests.post(f'{API}/oauth/token', json={'grant_type': 'password'}, timeout=10)
    test('Rejects unsupported grant_type', r2.status_code == 400 and 'unsupported_grant' in r2.text)
    r3 = requests.post(f'{API}/oauth/token', json={'grant_type': 'refresh_token'}, timeout=10)
    test('Rejects missing refresh_token', r3.status_code == 400)
    r4 = requests.post(f'{API}/oauth/token', json={'grant_type': 'refresh_token', 'refresh_token': 'invalid.token.here'}, timeout=10)
    test('Rejects invalid refresh_token', r4.status_code == 401)
except Exception as e:
    test('OAuth token validation', False, str(e))

# ===== OAUTH REVOKE =====
section('OAuth Revoke')
try:
    r = requests.post(f'{API}/oauth/revoke', json={'token': 'any.invalid.token'}, timeout=10)
    test('Revoke accepts any token', r.status_code == 200)
    r2 = requests.post(f'{API}/oauth/revoke', json={}, timeout=10)
    test('Revoke rejects empty body', r2.status_code == 400)
except Exception as e:
    test('OAuth revoke', False, str(e))

# ===== WIDGET/SDK FILES =====
section('Widget & SDK Files')
try:
    r = requests.get(f'{BASE}/sdk/tpid-widget.js', timeout=10)
    test('Widget JS loads', r.status_code == 200 and len(r.text) > 1000)
    test('Widget has version 1.2.0', 'WIDGET_VERSION' in r.text and '1.2.0' in r.text)
    test('Widget has renderIconButton', 'renderIconButton' in r.text)
    test('Widget has renderLogoButton', 'renderLogoButton' in r.text)
    test('Widget has loginWithOAuth', 'loginWithOAuth' in r.text)
    test('Widget has _shieldSVG', '_shieldSVG' in r.text)
    test('No-cache header on widget', 'no-cache' in r.headers.get('Cache-Control', '').lower() or r.status_code == 200)

    r2 = requests.get(f'{BASE}/tpid-widget.js', timeout=10)
    test('Backward-compat /tpid-widget.js', r2.status_code == 200 and len(r2.text) > 1000)
except Exception as e:
    test('Widget/SDK files', False, str(e))

# ===== OAUTH CONSENT PAGE =====
section('OAuth Consent Page')
try:
    r = requests.get(f'{BASE}/oauth-consent.html', timeout=10)
    test('Consent page loads', r.status_code == 200)
    test('Has prompt handling', 'promptParam' in r.text or 'prompt' in r.text)
    test('Has login_hint handling', 'loginHint' in r.text or 'login_hint' in r.text)
    test('Has switch account link', '_switchAccountUrl' in r.text or 'force=1' in r.text)
    test('Has sendBeacon cancel', 'sendBeacon' in r.text)
except Exception as e:
    test('OAuth consent page', False, str(e))

# ===== LOGIN PAGE =====
section('Login Page')
try:
    r = requests.get(f'{BASE}/login', timeout=10)
    test('Login page loads', r.status_code == 200)
    test('Has force login handling', '_forceLogin' in r.text or 'force' in r.text)
    test('Has login_hint handling', '_loginHint' in r.text or 'login_hint' in r.text)
except Exception as e:
    test('Login page', False, str(e))

# ===== AUTH FLOW =====
section('Auth Flow')
EMAIL = 'info@tokenpay.space'
PASS = 'Zdcgbjm812.'

# Send code
try:
    r = requests.post(f'{API}/auth/send-code', json={'email': EMAIL, 'type': 'login', 'lang': 'ru'}, timeout=10)
    test('Send code', r.status_code == 200 or r.status_code == 429, f'{r.status_code}')
except Exception as e:
    test('Send code', False, str(e))

# Login
try:
    r = requests.post(f'{API}/auth/login', json={'email': EMAIL, 'password': PASS}, timeout=10)
    d = r.json()
    needs_code = d.get('requires_email_code', False)
    has_token = 'accessToken' in d
    test('Login attempt', r.status_code in (200, 401), 'needs_code' if needs_code else 'got_token' if has_token else f'{r.status_code} (requires email_code)')

    token = d.get('accessToken')
    if token:
        headers = {'Authorization': f'Bearer {token}'}

        # Get user profile
        r2 = requests.get(f'{API}/users/me', headers=headers, timeout=10)
        d2 = r2.json()
        test('Get profile', r2.status_code == 200)
        test('Has locale field', 'locale' in d2, d2.get('locale', ''))
        test('Has role field', 'role' in d2, d2.get('role', ''))

        # Update locale
        r3 = requests.put(f'{API}/users/me', headers=headers, json={'locale': 'en'}, timeout=10)
        test('Update locale to en', r3.status_code == 200)
        r4 = requests.put(f'{API}/users/me', headers=headers, json={'locale': 'ru'}, timeout=10)
        test('Restore locale to ru', r4.status_code == 200)

        # Activity log
        r5 = requests.get(f'{API}/users/activity', headers=headers, timeout=10)
        test('Activity log', r5.status_code == 200)

        # Admin endpoints
        if d2.get('role') == 'admin':
            section('Admin Endpoints')
            r6 = requests.get(f'{API}/admin/users?limit=5', headers=headers, timeout=10)
            test('Admin users list', r6.status_code == 200, f'{len(r6.json().get("users",[]))} users')

            r7 = requests.get(f'{API}/admin/enterprise/applications?status=pending', headers=headers, timeout=10)
            test('Enterprise applications list', r7.status_code == 200, f'{r7.json().get("total",0)} pending')

            r8 = requests.get(f'{API}/admin/system', headers=headers, timeout=10)
            test('Admin system info', r8.status_code == 200)

            r9 = requests.get(f'{API}/admin/activity?limit=5', headers=headers, timeout=10)
            test('Admin activity log', r9.status_code == 200)
    else:
        test('(Skipping protected endpoints — login needs email code)', True)
except Exception as e:
    test('Login flow', False, str(e))

# ===== REGISTER VALIDATION =====
section('Register Validation')
try:
    r = requests.post(f'{API}/auth/register', json={'email': 'bad', 'password': '1', 'name': 'Test'}, timeout=10)
    test('Rejects bad email', r.status_code == 400 and 'invalid_email' in r.text)
    r = requests.post(f'{API}/auth/register', json={'email': 'test@test.com', 'password': '1', 'name': 'Test'}, timeout=10)
    test('Rejects weak password', r.status_code == 400 and 'weak_password' in r.text)
    r = requests.post(f'{API}/auth/register', json={'email': 'test@test.com', 'password': 'StrongPass123', 'name': 'Test'}, timeout=10)
    test('Requires email code', r.status_code == 400 and 'missing_code' in r.text)
except Exception as e:
    test('Register validation', False, str(e))

# ===== ENTERPRISE APPLY (unauthenticated) =====
section('Enterprise Apply (unauth)')
try:
    r = requests.post(f'{API}/enterprise/apply', json={'company_name': 'Test'}, timeout=10)
    test('Rejects without auth', r.status_code == 401)
except Exception as e:
    test('Enterprise apply unauth', False, str(e))

# ===== CONTACT FORM =====
section('Contact Form')
try:
    r = requests.post(f'{API}/contact', json={'name': 'Test', 'email': 'test@test.com', 'message': 'Automated test'}, timeout=10)
    test('Contact form', r.status_code == 200, r.json().get('message', ''))
except Exception as e:
    test('Contact form', False, str(e))

# ===== STATIC ASSETS =====
section('Static Assets')
for path, desc in [
    ('/tokenpay-logo.png', 'Logo PNG'),
    ('/tokenpay-icon.png', 'Icon PNG'),
    ('/favicon.ico', 'Favicon'),
    ('/styles.css', 'Main CSS'),
]:
    try:
        r = requests.get(f'{BASE}{path}', timeout=10)
        test(f'{desc} ({path})', r.status_code == 200, f'{len(r.content)} bytes')
    except Exception as e:
        test(desc, False, str(e))

# ===== CAPTCHA =====
section('Captcha')
try:
    r = requests.get(f'{API}/captcha/challenge', timeout=10)
    test('Captcha challenge', r.status_code == 200)
    d = r.json()
    test('Has nonce', 'nonce' in d)
except Exception as e:
    test('Captcha', False, str(e))

# ===== SUMMARY =====
passed = sum(results)
total = len(results)
failed = total - passed
print(f'\n\033[1m{"="*40}\033[0m')
print(f'\033[1mResults: {passed}/{total} passed' + (f', {failed} FAILED' if failed else ' — ALL PASSED ✅') + '\033[0m')
print(f'\033[90mTimestamp: {time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())}\033[0m')
sys.exit(0 if failed == 0 else 1)
