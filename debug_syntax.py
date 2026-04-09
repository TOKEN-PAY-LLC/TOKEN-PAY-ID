#!/usr/bin/env python3
import paramiko

SERVER = "5.23.54.205"
USER = "root"
PASSWORD = "vE^6t-zFS3dpNT"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(SERVER, port=22, username=USER, password=PASSWORD,
          timeout=120, banner_timeout=60, auth_timeout=60,
          allow_agent=False, look_for_keys=False)
t = c.get_transport()
t.set_keepalive(30)
t.window_size = 4 * 1024 * 1024
t.packetizer.REKEY_BYTES = pow(2, 40)
t.packetizer.REKEY_PACKETS = pow(2, 40)

def run(cmd):
    _, stdout, stderr = c.exec_command(cmd, timeout=120)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    if out: print(out)
    if err: print("STDERR:", err[:500])
    return out

print("=== 1. Syntax check server.js ===")
run('docker exec tokenpay-id-api node --check /app/server.js 2>&1')

print("\n=== 2. Syntax check email-service.js ===")
run('docker exec tokenpay-id-api node --check /app/email-service.js 2>&1')

print("\n=== 3. Check line count around enterprise routes ===")
run('docker exec tokenpay-id-api grep -n "enterprise" /app/server.js')

print("\n=== 4. Check if app.listen is reached ===")
run('docker exec tokenpay-id-api grep -n "app.listen" /app/server.js')

print("\n=== 5. Check what line the health endpoint is on ===")
run("docker exec tokenpay-id-api grep -n \"app.get.*health\" /app/server.js")

print("\n=== 6. Check email-service exports ===")
run("docker exec tokenpay-id-api grep -n 'module.exports' /app/email-service.js")

print("\n=== 7. Check for syntax errors in email-service around zh block ===")
run("docker exec tokenpay-id-api sed -n '125,180p' /app/email-service.js")

c.close()
