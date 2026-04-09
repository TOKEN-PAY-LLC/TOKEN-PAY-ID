#!/usr/bin/env python3
import paramiko, json

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("5.23.54.205", username="root", password="vE^6t-zFS3dpNT",
          timeout=30, banner_timeout=30, auth_timeout=30,
          allow_agent=False, look_for_keys=False)

def run(cmd):
    i, o, e = c.exec_command(cmd, timeout=60)
    return o.read().decode("utf-8", "replace").strip()

print("=== 1. login-init endpoint ===")
raw = run('curl -sk -X POST https://tokenpay.space/api/v1/auth/qr/login-init -H "Content-Type: application/json"')
print("RAW:", raw[:400])
try:
    d = json.loads(raw)
    print("keys:", list(d.keys()))
    print("sessionId:", str(d.get("sessionId", "MISSING"))[:40])
    print("qrUrl:", d.get("qrUrl", "MISSING"))
    print("ttl:", d.get("ttl", "MISSING"))
except Exception as ex:
    print("JSON parse error:", ex)

print("\n=== 2. qrcode-min.js served? ===")
r2 = run("curl -sk https://tokenpay.space/qrcode-min.js -o /dev/null -w '%{http_code}'")
print("HTTP status:", r2)

print("\n=== 3. login.html checks ===")
html = run("curl -sk https://tokenpay.space/login")
checks = {
    "qrLoginBtn": "qrLoginBtn" in html,
    "startQrLogin fn": "function startQrLogin" in html or "async function startQrLogin" in html,
    "onclick=startQrLogin": "startQrLogin()" in html,
    "QRCode.generate": "QRCode.generate" in html,
    "qrcode-min.js include": "qrcode-min.js" in html,
    "login-init in JS": "login-init" in html,
    "login-poll in JS": "login-poll" in html,
    "window.startQrLogin": "window.startQrLogin" in html,
}
for k, v in checks.items():
    print(f"  {k}: {'OK' if v else 'FAIL'}")

print("\n=== 4. API logs (last 20 lines) ===")
logs = run("cd /root/tokenpay-id && docker-compose logs --tail=20 api 2>&1")
for line in logs.split("\n")[-15:]:
    print(" ", line.strip()[:120])

print("\n=== 5. Check backend server.js has login-init route ===")
r5 = run("grep -n 'login-init' /root/tokenpay-id/backend/server.js")
print(r5 if r5 else "NOT FOUND!")

print("\n=== 6. Check backend server.js has login-poll route ===")
r6 = run("grep -n 'login-poll' /root/tokenpay-id/backend/server.js")
print(r6 if r6 else "NOT FOUND!")

print("\n=== 7. Test login-poll with session ===")
try:
    d2 = json.loads(raw)
    sid = d2.get("sessionId", "")
    if sid:
        poll = run(f"curl -sk https://tokenpay.space/api/v1/auth/qr/login-poll/{sid}")
        print("poll response:", poll[:200])
except:
    print("skipped")

print("\n=== 8. Nginx config for /qr-login ===")
r8 = run("docker exec tokenpay-id-nginx cat /etc/nginx/conf.d/default.conf 2>/dev/null | grep -A2 qr-login")
print(r8 if r8 else "No qr-login route in nginx!")

print("\n=== 9. Check if script.js conflicts ===")
# script.js defines DOMContentLoaded which might error and block subsequent scripts
r9 = run("curl -sk https://tokenpay.space/login | grep -o 'script.js[^\"]*'")
print("script.js ref:", r9 if r9 else "NOT included")

c.close()
print("\n=== DONE ===")
