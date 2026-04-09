#!/usr/bin/env python3
"""Full live verification of all new features"""
import paramiko, time, json

SERVER = "5.23.54.205"
USER = "root"
PASSWORD = "vE^6t-zFS3dpNT"

def connect():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(SERVER, port=22, username=USER, password=PASSWORD,
              timeout=60, banner_timeout=60, auth_timeout=60,
              allow_agent=False, look_for_keys=False)
    return c

def run(client, cmd):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=60)
    return stdout.read().decode('utf-8', errors='replace').strip()

client = connect()
passed = 0
failed = 0
total = 0

def check(name, condition):
    global passed, failed, total
    total += 1
    if condition:
        passed += 1
        print(f"  ✓ {name}")
    else:
        failed += 1
        print(f"  ✗ {name}")

# === 1. HEALTH ===
print("=== HEALTH ===")
h = run(client, "curl -sk https://tokenpay.space/health 2>/dev/null")
try:
    d = json.loads(h)
    check("API status ok", d.get('status') == 'ok')
    check("DB connected", d.get('db') == 'connected')
except:
    check("Health parseable", False)

# === 2. CHECK-USERNAME ENDPOINT ===
print("\n=== CHECK-USERNAME ===")
# Available username
r = run(client, "curl -sk 'https://tokenpay.space/api/v1/auth/check-username?username=unique_test_xyz' 2>/dev/null")
try:
    d = json.loads(r)
    check("Available username returns available:true", d.get('available') == True)
except:
    check("Available username response", False)

# Short username
r = run(client, "curl -sk 'https://tokenpay.space/api/v1/auth/check-username?username=ab' 2>/dev/null")
try:
    d = json.loads(r)
    check("Short username returns available:false", d.get('available') == False)
    check("Short username has reason", 'reason' in d and len(d['reason']) > 0)
except:
    check("Short username response", False)

# Reserved username
r = run(client, "curl -sk 'https://tokenpay.space/api/v1/auth/check-username?username=admin' 2>/dev/null")
try:
    d = json.loads(r)
    check("Reserved 'admin' returns available:false", d.get('available') == False)
except:
    check("Reserved username response", False)

# Invalid chars
r = run(client, "curl -sk 'https://tokenpay.space/api/v1/auth/check-username?username=bad%%20name!' 2>/dev/null")
try:
    d = json.loads(r)
    check("Invalid chars returns available:false", d.get('available') == False)
except:
    check("Invalid chars response", False)

# Empty username
r = run(client, "curl -sk 'https://tokenpay.space/api/v1/auth/check-username?username=' 2>/dev/null")
try:
    d = json.loads(r)
    check("Empty username returns available:false", d.get('available') == False)
except:
    check("Empty username response", False)

# Lang=en
r = run(client, "curl -sk 'https://tokenpay.space/api/v1/auth/check-username?username=ab&lang=en' 2>/dev/null")
try:
    d = json.loads(r)
    check("English reason text", 'reason' in d and ('char' in d['reason'].lower() or 'minimum' in d['reason'].lower()))
except:
    check("English lang check-username", False)

# === 3. CLIENT PREFERENCES ===
print("\n=== CLIENT PREFERENCES ===")
r = run(client, "curl -sk 'https://tokenpay.space/api/v1/client/preferences' -H 'Accept-Language: en' 2>/dev/null")
try:
    d = json.loads(r)
    check("Preferences returns lang", 'lang' in d)
    check("Preferences returns theme", 'theme' in d)
    check("Accept-Language: en → lang=en", d.get('lang') == 'en')
except:
    check("Client preferences response", False)

r = run(client, "curl -sk 'https://tokenpay.space/api/v1/client/preferences?lang=ru&theme=light' 2>/dev/null")
try:
    d = json.loads(r)
    check("Query param lang=ru works", d.get('lang') == 'ru')
    check("Query param theme=light works", d.get('theme') == 'light')
except:
    check("Query param preferences", False)

# === 4. REGISTER ENDPOINT ===
print("\n=== REGISTER ENDPOINT ===")
# Missing username
r = run(client, """curl -sk -X POST 'https://tokenpay.space/api/v1/auth/register' -H 'Content-Type: application/json' -d '{"email":"x@x.com","password":"Test12345!"}' 2>/dev/null""")
try:
    d = json.loads(r)
    check("Missing username → error", 'error' in d)
    check("Error code missing_fields", d['error'].get('code') == 'missing_fields')
except:
    check("Missing username error", False)

# Invalid username
r = run(client, """curl -sk -X POST 'https://tokenpay.space/api/v1/auth/register' -H 'Content-Type: application/json' -d '{"email":"x@x.com","password":"Test12345!","username":"a"}' 2>/dev/null""")
try:
    d = json.loads(r)
    check("Invalid username → error", 'error' in d)
    check("Error code invalid_username", d['error'].get('code') == 'invalid_username')
except:
    check("Invalid username error", False)

# Valid but missing code
r = run(client, """curl -sk -X POST 'https://tokenpay.space/api/v1/auth/register' -H 'Content-Type: application/json' -d '{"email":"x@x.com","password":"Test12345!","username":"valid_user"}' 2>/dev/null""")
try:
    d = json.loads(r)
    check("Valid username but no code → missing_code error", d['error'].get('code') == 'missing_code')
except:
    check("Missing code error", False)

# === 5. LOGIN ENDPOINT (theme/lang pass-through) ===
print("\n=== LOGIN THEME/LANG ===")
r = run(client, """curl -sk -X POST 'https://tokenpay.space/api/v1/auth/login' -H 'Content-Type: application/json' -d '{"email":"nonexist@x.com","password":"wrong","lang":"en","theme":"light"}' 2>/dev/null""")
try:
    d = json.loads(r)
    check("Login accepts lang/theme without crash", 'error' in d)
except:
    check("Login theme/lang passthrough", False)

# === 6. FRONTEND PAGES ===
print("\n=== FRONTEND PAGES ===")

# Register page
reg = run(client, "curl -sk 'https://tokenpay.space/register' 2>/dev/null")
check("Register has regUsername input", 'regUsername' in reg)
check("Register has Логин label", 'Логин' in reg)
check("Register has check-username call", 'check-username' in reg)
check("Register has usernameOk SVG", 'usernameOk' in reg)
check("Register has usernameLoading SVG", 'usernameLoading' in reg)
check("Register has tpid-spin animation", 'tpid-spin' in reg)
check("Register has tpid-pop animation", 'tpid-pop' in reg)
check("Register has username-ok class", 'username-ok' in reg)
check("Register sends username in register body", "'username'" in reg or 'username,' in reg or 'username}' in reg)
check("Register sends theme in body", "theme:" in reg or "theme :" in reg or "_theme" in reg)
check("Register no more regName input", 'id="regName"' not in reg)
check("Register no more Имя label", 'data-ru="Имя"' not in reg)

# Login page
login = run(client, "curl -sk 'https://tokenpay.space/login' 2>/dev/null")
check("Login has _theme variable", '_theme' in login)
check("Login passes theme to API", 'theme: _theme' in login)

# === 7. STARS FIX ===
print("\n=== STARS FIX ===")
for page, url in [('script.js', 'https://tokenpay.space/script.js'), 
                   ('dashboard', 'https://tokenpay.space/dashboard'),
                   ('docs', 'https://tokenpay.space/docs')]:
    content = run(client, f"curl -sk '{url}' 2>/dev/null")
    check(f"{page}: uses soft pastel (160,150,220)", '160,150,220' in content)
    check(f"{page}: no dark stars (30,40,80)", '30,40,80' not in content)

# === 8. EXISTING FEATURES STILL WORK ===
print("\n=== EXISTING FEATURES ===")

# Magic link endpoint
r = run(client, """curl -sk -X POST 'https://tokenpay.space/api/v1/auth/magic-link/send' -H 'Content-Type: application/json' -d '{"email":"x@x.com","password":"wrong"}' 2>/dev/null""")
try:
    d = json.loads(r)
    check("Magic link endpoint responds", 'error' in d)
except:
    check("Magic link endpoint", False)

# Captcha config endpoint
r = run(client, "curl -sk 'https://tokenpay.space/api/v1/captcha/challenge' 2>/dev/null")
check("Captcha challenge responds", len(r) > 10)

# OAuth consent page
consent = run(client, "curl -sk 'https://tokenpay.space/oauth-consent' 2>/dev/null")
check("OAuth consent page loads", 'oauth' in consent.lower() or 'consent' in consent.lower() or 'authorize' in consent.lower())

# Branded nav button
idx = run(client, "curl -sk 'https://tokenpay.space/' 2>/dev/null")
check("Index has tokenpay-id branded button", 'tokenpay-id' in idx.lower() or 'tpid-logo' in idx)

client.close()

print(f"\n{'='*50}")
print(f"РЕЗУЛЬТАТ: {passed}/{total} тестов пройдено, {failed} провалено")
if failed == 0:
    print("✓ ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
else:
    print(f"✗ {failed} тестов требуют внимания")
