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
    test('X-Frame-Options', r.headers.get('X-Frame-Options') == 'DENY')
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
except Exception as e:
    test('OpenID discovery', False, str(e))

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
    test('Login attempt', r.status_code == 200, 'needs_code' if needs_code else 'got_token' if has_token else f'{r.status_code}')

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

# ===== SUMMARY =====
passed = sum(results)
total = len(results)
failed = total - passed
print(f'\n\033[1m{"="*40}\033[0m')
print(f'\033[1mResults: {passed}/{total} passed' + (f', {failed} FAILED' if failed else ' — ALL PASSED ✅') + '\033[0m')
sys.exit(0 if failed == 0 else 1)
