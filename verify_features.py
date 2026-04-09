#!/usr/bin/env python3
"""Verify all new features are working on production"""
import paramiko, time

SERVER = "5.23.54.205"
USER = "root"
PASSWORD = "vE^6t-zFS3dpNT"

def new_client():
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
    return c

def run(c, cmd):
    _, stdout, stderr = c.exec_command(cmd, timeout=120)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    if out:
        for line in out.split('\n')[:30]: print("  " + line)
    if err and 'warning' not in err.lower():
        for line in err.split('\n')[:5]: print("  ERR:", line)
    return out

c = new_client()

print("=== Container Status ===")
run(c, 'docker ps --filter name=tokenpay --format "table {{.Names}}\t{{.Status}}"')

print("\n=== 1. Health endpoint ===")
run(c, 'curl -s http://localhost:8080/health')

print("\n=== 2. Client preferences ===")
run(c, 'curl -s http://localhost:8080/api/v1/client/preferences')

print("\n=== 3. Enterprise errors POST (no auth → expect 401) ===")
out = run(c, 'curl -s -w "\\nHTTP_CODE:%{http_code}" -X POST http://localhost:8080/api/v1/enterprise/errors -H "Content-Type: application/json" -d \'{"error_type":"test","error_message":"test msg"}\'')

print("\n=== 4. Enterprise errors GET (no auth → expect 401) ===")
out = run(c, 'curl -s -w "\\nHTTP_CODE:%{http_code}" http://localhost:8080/api/v1/enterprise/errors')

print("\n=== 5. Enterprise health POST (no auth → expect 401) ===")
out = run(c, 'curl -s -w "\\nHTTP_CODE:%{http_code}" -X POST http://localhost:8080/api/v1/enterprise/health -H "Content-Type: application/json" -d \'{"status":"ok"}\'')

print("\n=== 6. SDK via HTTPS ===")
run(c, 'curl -sk https://tokenpay.space/sdk/tokenpay-auth.js 2>/dev/null | head -3')

print("\n=== 7. Language ZH in Accept-Language ===")
run(c, 'curl -s -H "Accept-Language: zh-CN" http://localhost:8080/api/v1/client/preferences')

print("\n=== 8. Language EN in Accept-Language ===")
run(c, 'curl -s -H "Accept-Language: en-US" http://localhost:8080/api/v1/client/preferences')

print("\n=== 9. Express routes listing (enterprise) ===")
run(c, 'docker exec tokenpay-id-api node -e "const app=require(\\"/app/server.js\\"); console.log(\\"loaded\\")" 2>&1 | head -5')

print("\n=== 10. Docker logs (last 20 lines) ===")
run(c, 'docker logs tokenpay-id-api --tail 20 2>&1')

c.close()
print("\nDone.")
