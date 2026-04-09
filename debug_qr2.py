#!/usr/bin/env python3
import paramiko, json

SERVER = "5.23.54.205"
USER = "root"
PASSWORD = "vE^6t-zFS3dpNT"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(SERVER, port=22, username=USER, password=PASSWORD,
          timeout=60, banner_timeout=60, auth_timeout=60,
          allow_agent=False, look_for_keys=False)

def run(cmd):
    i,o,e = c.exec_command(cmd, timeout=60)
    return o.read().decode('utf-8','replace').strip()

print("=== QR LOGIN DEBUG ===")
r = run("curl -sk -X POST 'https://tokenpay.space/api/v1/auth/qr/login-init' -H 'Content-Type: application/json' 2>/dev/null")
print("login-init:", r[:200])

d = json.loads(r)
sid = d.get('sessionId','')
print("sessionId:", sid)
print("qrUrl:", d.get('qrUrl',''))

r2 = run("curl -sk 'https://tokenpay.space/api/v1/auth/qr/login-poll/" + sid + "' 2>/dev/null")
print("poll:", r2)

print("\n=== NGINX qr-login route ===")
r3 = run("docker exec tokenpay-id-nginx cat /etc/nginx/conf.d/default.conf 2>/dev/null | grep -A5 qr-login")
print(r3 if r3 else "NO qr-login route found")

r4 = run("curl -sk -o /dev/null -w '%{http_code}' 'https://tokenpay.space/qr-login?sid=test' 2>/dev/null")
print("qr-login HTTP status:", r4)

r5 = run("curl -sk 'https://tokenpay.space/qr-login?sid=test' 2>/dev/null")
print("qr-login first 300 chars:", r5[:300])

print("\n=== FILE CHECK ===")
r6 = run("ls -la /root/tokenpay-id/frontend/qr-login.html 2>/dev/null")
print("qr-login.html:", r6 if r6 else "NOT FOUND")

print("\n=== NGINX full config (locations) ===")
r7 = run("docker exec tokenpay-id-nginx cat /etc/nginx/conf.d/default.conf 2>/dev/null | grep 'location'")
print(r7)

print("\n=== API LOGS ===")
logs = run("cd /root/tokenpay-id && docker-compose logs --tail=10 api 2>&1")
for line in logs.split('\n')[-8:]:
    print(line.strip())

# Check magic link button in login.html
print("\n=== MAGIC LINK BUTTON ===")
ml = run("grep -n 'magicLink' /root/tokenpay-id/frontend/login.html | head -5")
print(ml)

c.close()
