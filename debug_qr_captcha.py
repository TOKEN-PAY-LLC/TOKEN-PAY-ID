#!/usr/bin/env python3
import paramiko, json

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

print("=== CAPTCHA ===")
r = run(client, "curl -sk 'https://tokenpay.space/api/v1/captcha/config' 2>/dev/null")
print(f"  /captcha/config: {r}")

r = run(client, "curl -sk 'https://tokenpay.space/api/v1/captcha/challenge' 2>/dev/null")
print(f"  /captcha/challenge: {r[:200]}")

print("\n=== QR ===")
r = run(client, "curl -sk 'https://tokenpay.space/api/v1/auth/qr/generate' -X POST -H 'Content-Type: application/json' 2>/dev/null")
print(f"  /qr/generate (no auth): {r[:200]}")

print("\n=== QR ENDPOINTS IN SERVER.JS ===")
r = run(client, "grep -n 'qr/' /root/tokenpay-id/backend/server.js")
print(f"  {r}")

print("\n=== API HEALTH ===")
r = run(client, "curl -sk 'https://tokenpay.space/health' 2>/dev/null")
print(f"  {r}")

print("\n=== API LOGS (last 10) ===")
r = run(client, "cd /root/tokenpay-id && docker-compose logs --tail=10 api 2>&1")
for line in r.split('\n')[-10:]:
    print(f"  {line.strip()}")

client.close()
