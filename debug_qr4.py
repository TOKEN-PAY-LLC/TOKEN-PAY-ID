#!/usr/bin/env python3
"""Deep diagnostic: why QR login button doesn't work"""
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("5.23.54.205", username="root", password="vE^6t-zFS3dpNT",
          timeout=30, banner_timeout=30, auth_timeout=30,
          allow_agent=False, look_for_keys=False)

def run(cmd):
    i, o, e = c.exec_command(cmd, timeout=60)
    return o.read().decode("utf-8", "replace").strip()

# 1. Check deployed login.html has QR button and function
print("=== 1. Deployed login.html content check ===")
html = run("cat /root/tokenpay-id/frontend/login.html")
checks = [
    ("qrLoginBtn", 'id="qrLoginBtn"' in html),
    ("onclick=startQrLogin", 'onclick="startQrLogin()"' in html),
    ("async function startQrLogin", "async function startQrLogin" in html),
    ("window.startQrLogin", "window.startQrLogin" in html),
    ("QRCode.generate in QR", "QRCode.generate(qrUrl)" in html),
    ("login-init fetch", "auth/qr/login-init" in html),
    ("login-poll fetch", "auth/qr/login-poll" in html),
    ("showQrModal", "showQrModal" in html),
    ("completeLogin(data", "completeLogin(data" in html),
    ("qrcode-min.js", "qrcode-min.js" in html),
    ("script.js", "script.js" in html),
]
for name, ok in checks:
    print(f"  {name}: {'OK' if ok else 'MISSING!'}")

# 2. Check deployed via HTTPS (what browser actually gets)
print("\n=== 2. HTTPS response check ===")
https_html = run("curl -sk https://tokenpay.space/login")
https_checks = [
    ("qrLoginBtn in HTTPS", 'id="qrLoginBtn"' in https_html),
    ("startQrLogin in HTTPS", "startQrLogin" in https_html),
    ("v=20260327c", "20260327c" in https_html),
]
for name, ok in https_checks:
    print(f"  {name}: {'OK' if ok else 'MISSING!'}")

# 3. Check if qrcode-min.js is valid JS (no syntax errors)
print("\n=== 3. qrcode-min.js validation ===")
r3 = run("node -e 'require(\"/root/tokenpay-id/frontend/qrcode-min.js\"); console.log(\"OK: QRCode type=\", typeof QRCode);' 2>&1")
print(f"  {r3}")

# 4. Check if login.html JS has syntax errors (parse test)
print("\n=== 4. JS syntax check on login.html inline script ===")
# Extract the inline JS and check syntax
run("sed -n '/<script>/,/<\\/script>/p' /root/tokenpay-id/frontend/login.html | sed '1d;$d' > /tmp/login_script.js")
r4 = run("node --check /tmp/login_script.js 2>&1")
print(f"  Syntax: {'OK (no errors)' if not r4 else r4}")

# 5. Check if script.js has errors
print("\n=== 5. script.js syntax ===")
r5 = run("node --check /root/tokenpay-id/frontend/script.js 2>&1")
print(f"  {r5 if r5 else 'OK'}")

# 6. Check qrcode-min.js has QRCode.generate
print("\n=== 6. QRCode.generate exists ===")
r6 = run("node -e 'require(\"/root/tokenpay-id/frontend/qrcode-min.js\"); console.log(\"generate:\", typeof QRCode.generate);' 2>&1")
print(f"  {r6}")

# 7. Check served qrcode-min.js
print("\n=== 7. Served qrcode-min.js (HTTPS) ===")
r7 = run("curl -sk https://tokenpay.space/qrcode-min.js -o /dev/null -w 'HTTP %{http_code} Size %{size_download}'")
print(f"  {r7}")

# 8. Check if there's a Content-Security-Policy blocking fetch
print("\n=== 8. CSP headers on login page ===")
r8 = run("curl -sk -I https://tokenpay.space/login | grep -i content-security")
print(f"  {r8 if r8 else 'No CSP header (OK)'}")

# 9. Check connect-src if CSP exists
print("\n=== 9. Response headers for login page ===")
r9 = run("curl -sk -I https://tokenpay.space/login | head -20")
for line in r9.split("\n"):
    print(f"  {line}")

# 10. Full end-to-end test
print("\n=== 10. E2E QR flow test ===")
import json
r10 = run('curl -sk -X POST https://tokenpay.space/api/v1/auth/qr/login-init -H "Content-Type: application/json"')
try:
    d = json.loads(r10)
    sid = d["sessionId"]
    print(f"  init OK: sid={sid[:20]}...")
    print(f"  qrUrl: {d['qrUrl']}")
    
    r_poll = run(f"curl -sk https://tokenpay.space/api/v1/auth/qr/login-poll/{sid}")
    print(f"  poll: {r_poll}")
    
    r_qr = run(f"curl -sk -o /dev/null -w 'HTTP %{{http_code}}' 'https://tokenpay.space/qr-login?sid={sid}'")
    print(f"  qr-login page: {r_qr}")
except Exception as ex:
    print(f"  ERROR: {ex}")
    print(f"  Raw: {r10[:200]}")

c.close()
print("\n=== DONE ===")
