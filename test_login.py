#!/usr/bin/env python3
"""TOKEN PAY ID — Real Login Flow Test (with email code from DB)"""
import requests, json, sys, time

# Connect to DB directly to read the email code after sending
import subprocess

API = 'https://tokenpay.space/api/v1'
EMAIL = 'info@tokenpay.space'
PASS = 'Zdcgbjm812.'

# SSH to read code from DB
SSH_HOST = '5.23.54.205'
SSH_USER = 'root'
SSH_PASS = 'vE^6t-zFS3dpNT'

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

def get_code_from_db():
    """Read the latest unused login code from the DB via SSH + docker exec"""
    import paramiko
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SSH_HOST, username=SSH_USER, password=SSH_PASS, timeout=10)
    cmd = f'''docker exec tokenpay-id-api node -e "
const {{ Pool }} = require('pg');
const p = new Pool({{ host: '5.23.55.152', port: 5432, database: 'default_db', user: 'gen_user', password: '93JJFQLAYC=Uo)' }});
p.query(\\"SELECT code, expires_at, used FROM email_codes WHERE email = '{EMAIL}' AND type = 'login' AND used = FALSE ORDER BY created_at DESC LIMIT 1\\").then(r => {{ console.log(JSON.stringify(r.rows[0] || {{}})); p.end(); }}).catch(e => {{ console.error(e.message); p.end(); }});
"'''
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=15)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    ssh.close()
    try:
        data = json.loads(out)
        return data.get('code')
    except:
        print(f'  [DB] stdout: {out[:200]}')
        if err: print(f'  [DB] stderr: {err[:200]}')
        return None

# ===== STEP 1: Login without code → triggers email code =====
section('Step 1: Trigger email code')
try:
    r = requests.post(f'{API}/auth/login', json={'email': EMAIL, 'password': PASS}, timeout=10)
    d = r.json()
    test('Login returns requires_email_code', d.get('requires_email_code') == True)
    test('Status 200', r.status_code == 200)
except Exception as e:
    test('Trigger code', False, str(e))

time.sleep(1)

# ===== STEP 2: Read code from DB =====
section('Step 2: Read code from DB')
code = get_code_from_db()
test('Got code from DB', code is not None and len(code) == 6, code or 'None')

if not code:
    print('\n\033[91mFATAL: Could not read code from DB. Aborting.\033[0m')
    sys.exit(1)

# ===== STEP 3: Login with email code =====
section('Step 3: Login with email code')
try:
    r = requests.post(f'{API}/auth/login', json={
        'email': EMAIL, 'password': PASS, 'email_code': code
    }, timeout=10)
    d = r.json()

    if d.get('requires_2fa'):
        test('Email code accepted (2FA required)', True, 'requires_2fa=true')
        print(f'  ℹ️  2FA is enabled — cannot complete login without TOTP code')
        print(f'  ℹ️  But email code verification WORKS correctly!')
        
        # Test that the code is still usable (not consumed) for the 2FA step
        section('Step 3b: Verify code survives 2FA flow')
        r2 = requests.post(f'{API}/auth/login', json={
            'email': EMAIL, 'password': PASS, 'email_code': code
        }, timeout=10)
        d2 = r2.json()
        test('Code still valid on retry (not prematurely consumed)', d2.get('requires_2fa') == True or 'accessToken' in d2, f'status={r2.status_code}')
    elif 'accessToken' in d:
        test('Login successful!', True)
        token = d['accessToken']
        
        # Test profile
        section('Step 4: Profile check')
        headers = {'Authorization': f'Bearer {token}'}
        r2 = requests.get(f'{API}/users/me', headers=headers, timeout=10)
        d2 = r2.json()
        test('Get profile', r2.status_code == 200)
        test('Has theme field', 'theme' in d2, d2.get('theme', 'missing'))
        test('Has locale field', 'locale' in d2, d2.get('locale', 'missing'))
        test('Has role field', 'role' in d2, d2.get('role', 'missing'))
        
        # Test theme update
        section('Step 5: Theme API')
        r3 = requests.put(f'{API}/users/me', headers=headers, json={'theme': 'light'}, timeout=10)
        test('Set theme to light', r3.status_code == 200)
        r4 = requests.get(f'{API}/users/me', headers=headers, timeout=10)
        test('Theme persisted', r4.json().get('theme') == 'light')
        r5 = requests.put(f'{API}/users/me', headers=headers, json={'theme': 'dark'}, timeout=10)
        test('Restore theme to dark', r5.status_code == 200)
        
        # Test sessions
        section('Step 6: Sessions')
        r6 = requests.get(f'{API}/users/sessions', headers=headers, timeout=10)
        test('Sessions list', r6.status_code == 200)
        
        # Test activity
        r7 = requests.get(f'{API}/users/activity', headers=headers, timeout=10)
        test('Activity log', r7.status_code == 200)
        
        # Admin endpoints
        if d2.get('role') == 'admin':
            section('Step 7: Admin')
            r8 = requests.get(f'{API}/admin/users?limit=5', headers=headers, timeout=10)
            test('Admin users', r8.status_code == 200, f'{len(r8.json().get("users",[]))} users')
            r9 = requests.get(f'{API}/admin/system', headers=headers, timeout=10)
            test('Admin system', r9.status_code == 200)
    else:
        test('Login with code', False, f'{r.status_code}: {json.dumps(d)[:200]}')
except Exception as e:
    test('Login with code', False, str(e))

# ===== STEP: Test code with spaces (bug fix verification) =====
section('Bug Fix: Code with spaces')
# Trigger a new code
try:
    requests.post(f'{API}/auth/login', json={'email': EMAIL, 'password': PASS}, timeout=10)
    time.sleep(1)
    code2 = get_code_from_db()
    if code2:
        spaced = code2[:3] + ' ' + code2[3:]
        r = requests.post(f'{API}/auth/login', json={
            'email': EMAIL, 'password': PASS, 'email_code': spaced
        }, timeout=10)
        d = r.json()
        accepted = d.get('requires_2fa') == True or 'accessToken' in d
        test(f'Code with space "{spaced}" accepted', accepted, f'status={r.status_code}')
    else:
        test('Get code for space test', False, 'no code')
except Exception as e:
    test('Space test', False, str(e))

# ===== SUMMARY =====
passed = sum(results)
total = len(results)
failed = total - passed
print(f'\n\033[1m{"="*40}\033[0m')
print(f'\033[1mResults: {passed}/{total} passed' + (f', {failed} FAILED' if failed else ' — ALL PASSED ✅') + '\033[0m')
sys.exit(0 if failed == 0 else 1)
