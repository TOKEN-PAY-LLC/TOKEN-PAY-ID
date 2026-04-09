#!/usr/bin/env python3
"""Verify via correct paths: docker exec for API, nginx for HTTPS"""
import paramiko

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

print("=== 1. Check what's on port 8080 on host ===")
run(c, 'ss -tlnp | grep 8080')
run(c, 'lsof -i :8080 2>/dev/null | head -5 || ss -tlnp | grep 8080')

print("\n=== 2. Check docker port mapping ===")
run(c, 'docker port tokenpay-id-api 2>/dev/null || echo "no port mapping"')

print("\n=== 3. Test via docker exec (correct way to reach container API) ===")
print("\n  Health:")
run(c, 'docker exec tokenpay-id-api wget -qO- http://localhost:8080/health 2>/dev/null')

print("\n  Client preferences:")
run(c, 'docker exec tokenpay-id-api wget -qO- http://localhost:8080/api/v1/client/preferences 2>/dev/null')

print("\n  Enterprise errors POST (no auth):")
run(c, 'docker exec tokenpay-id-api wget -qO- --post-data=\'{"error_type":"test","error_message":"test"}\' --header="Content-Type: application/json" http://localhost:8080/api/v1/enterprise/errors 2>&1 | tail -5')

print("\n  Enterprise health POST (no auth):")
run(c, 'docker exec tokenpay-id-api wget -qO- --post-data=\'{"status":"ok"}\' --header="Content-Type: application/json" http://localhost:8080/api/v1/enterprise/health 2>&1 | tail -5')

print("\n=== 4. Test via nginx proxy (port 443) ===")
print("\n  Health via nginx:")
run(c, 'curl -sk https://localhost/health')

print("\n  Preferences via nginx:")
run(c, 'curl -sk https://localhost/api/v1/client/preferences')

print("\n  Enterprise errors via nginx:")
run(c, 'curl -sk -X POST https://localhost/api/v1/enterprise/errors -H "Content-Type: application/json" -d \'{"error_type":"test","error_message":"test"}\'')

print("\n  SDK version via nginx:")
run(c, 'curl -sk https://localhost/api/v1/sdk/version')

print("\n  ZH language via nginx:")
run(c, 'curl -sk -H "Accept-Language: zh-CN" https://localhost/api/v1/client/preferences')

print("\n=== 5. Also check if there's a host-level node process ===")
run(c, 'ps aux | grep "node.*server" | grep -v grep')

c.close()
print("\nDone.")
