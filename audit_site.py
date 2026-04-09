import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('5.23.54.205', username='root', password='vE^6t-zFS3dpNT', timeout=15)

checks = [
    # --- Pages load ---
    ("curl -sk -o /dev/null -w '%{http_code}' https://tokenpay.space/", "Homepage HTTP"),
    ("curl -sk -o /dev/null -w '%{http_code}' https://tokenpay.space/login", "Login HTTP"),
    ("curl -sk -o /dev/null -w '%{http_code}' https://tokenpay.space/register", "Register HTTP"),
    ("curl -sk -o /dev/null -w '%{http_code}' https://tokenpay.space/docs", "Docs HTTP"),
    ("curl -sk -o /dev/null -w '%{http_code}' https://tokenpay.space/dashboard", "Dashboard HTTP"),
    ("curl -sk -o /dev/null -w '%{http_code}' https://tokenpay.space/privacy", "Privacy HTTP"),
    ("curl -sk -o /dev/null -w '%{http_code}' https://tokenpay.space/terms", "Terms HTTP"),
    ("curl -sk -o /dev/null -w '%{http_code}' https://tokenpay.space/admin", "Admin HTTP"),

    # --- CSS version consistency ---
    ("curl -sk https://tokenpay.space/ | grep -o 'styles.css?v=[^\"]*' | head -1", "Index CSS ver"),
    ("curl -sk https://tokenpay.space/login | grep -o 'styles.css?v=[^\"]*' | head -1", "Login CSS ver"),
    ("curl -sk https://tokenpay.space/register | grep -o 'styles.css?v=[^\"]*' | head -1", "Register CSS ver"),
    ("curl -sk https://tokenpay.space/docs | grep -o 'styles.css?v=[^\"]*' | head -1", "Docs CSS ver"),
    ("curl -sk https://tokenpay.space/dashboard | grep -o 'styles.css?v=[^\"]*' | head -1", "Dashboard CSS ver"),
    ("curl -sk https://tokenpay.space/privacy | grep -o 'styles.css?v=[^\"]*' | head -1", "Privacy CSS ver"),
    ("curl -sk https://tokenpay.space/terms | grep -o 'styles.css?v=[^\"]*' | head -1", "Terms CSS ver"),

    # --- Static assets ---
    ("curl -sk -o /dev/null -w '%{http_code}' https://tokenpay.space/styles.css", "styles.css"),
    ("curl -sk -o /dev/null -w '%{http_code}' https://tokenpay.space/script.js", "script.js"),
    ("curl -sk -o /dev/null -w '%{http_code}' https://tokenpay.space/theme-init.js", "theme-init.js"),
    ("curl -sk -o /dev/null -w '%{http_code}' https://tokenpay.space/captcha.js", "captcha.js"),
    ("curl -sk -o /dev/null -w '%{http_code}' https://tokenpay.space/tokenpay-logo.png", "Logo"),
    ("curl -sk -o /dev/null -w '%{http_code}' https://tokenpay.space/tokenpay-icon.png", "Icon"),
    ("curl -sk -o /dev/null -w '%{http_code}' https://tokenpay.space/tokenpay-id-light.png", "ID logo light"),
    ("curl -sk -o /dev/null -w '%{http_code}' https://tokenpay.space/tokenpay-id-dark.png", "ID logo dark"),
    ("curl -sk -o /dev/null -w '%{http_code}' https://tokenpay.space/favicon.ico", "Favicon"),

    # --- Key content checks ---
    ("curl -sk https://tokenpay.space/ | grep -c 'animate-on-scroll'", "Scroll animations count"),
    ("curl -sk https://tokenpay.space/ | grep -c 'cloud cloud-'", "Cloud elements"),
    ("curl -sk https://tokenpay.space/ | grep -c 'hero-orb'", "Hero orbs"),
    ("curl -sk https://tokenpay.space/ | grep -o 'particles' | head -1", "Particles canvas"),
    ("curl -sk https://tokenpay.space/ | grep -c 'shimmer-btn'", "Shimmer buttons"),

    # --- Photo 1 fix: No admin name leaking ---
    ("curl -sk https://tokenpay.space/ | grep -o 'var name = label' | head -1", "Admin fix (inline)"),
    ("curl -sk https://tokenpay.space/script.js | grep -o '\\${label}' | head -1", "Admin fix (script)"),

    # --- Photo 2 fix: Terms + Privacy links ---
    ("curl -sk https://tokenpay.space/ | grep -o 'href=\"/terms\"' | head -1", "Terms link"),
    ("curl -sk https://tokenpay.space/ | grep -o 'href=\"/privacy\"' | head -1", "Privacy link"),

    # --- Photo 3 fix: Email button ---
    ("curl -sk https://tokenpay.space/docs | grep -o 'btn btn-secondary btn-sm' | head -1", "Email btn class"),
    ("curl -sk https://tokenpay.space/docs | grep -o 'color:var(--text)' | head -1", "Help h3 color"),

    # --- Photo 4 fix: Light theme ---
    ("curl -sk https://tokenpay.space/styles.css | grep -c 'body.light'", "Light theme rules count"),
    ("curl -sk https://tokenpay.space/styles.css | grep -o 'brightness(.12)' | head -1", "Icon filter fix"),
    ("curl -sk https://tokenpay.space/styles.css | grep -o 'heroGlowLight' | head -1", "Light glow anim"),
    ("curl -sk https://tokenpay.space/script.js | grep -o '_updateColors' | head -1", "Particle theme"),

    # --- API health ---
    ("curl -sk -o /dev/null -w '%{http_code}' https://tokenpay.space/api/v1/health", "API health"),
    ("curl -sk https://tokenpay.space/.well-known/openid-configuration | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d.get(\"issuer\",\"MISSING\"))' 2>/dev/null", "OIDC issuer"),

    # --- Docker status ---
    ("docker ps --format '{{.Names}}: {{.Status}}' | sort", "Docker containers"),

    # --- Security headers ---
    ("curl -skI https://tokenpay.space/ | grep -i x-frame-options | head -1", "X-Frame-Options"),
    ("curl -skI https://tokenpay.space/ | grep -i x-content-type | head -1", "X-Content-Type"),
    ("curl -skI https://tokenpay.space/ | grep -i strict-transport | head -1", "HSTS"),
]

print('=' * 60)
print('TOKENPAY.SPACE — FULL AUDIT')
print('=' * 60)

passed = 0
failed = 0
warnings = []

for cmd, label in checks:
    _, so, se = ssh.exec_command(cmd)
    result = so.read().decode().strip() or se.read().decode().strip() or '(empty)'
    
    # Determine status
    is_ok = True
    if result in ('(empty)', '0', 'MISSING'):
        is_ok = False
    if 'HTTP' in label and result not in ('200', '301', '302'):
        is_ok = False
    
    status = '✓' if is_ok else '✗'
    if is_ok:
        passed += 1
    else:
        failed += 1
        warnings.append(f'{label}: {result}')
    
    print(f'  {status} {label}: {result}')

print(f'\n{"=" * 60}')
print(f'RESULTS: {passed} passed, {failed} failed')
if warnings:
    print(f'\nWARNINGS:')
    for w in warnings:
        print(f'  ! {w}')
print('=' * 60)

ssh.close()
