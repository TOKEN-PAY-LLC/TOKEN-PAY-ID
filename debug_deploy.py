#!/usr/bin/env python3
"""Debug why new server.js isn't being picked up"""
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
        for line in out.split('\n')[:40]: print("  " + line)
    if err:
        for line in err.split('\n')[:5]: print("  ERR:", line)
    return out

c = new_client()

print("=== 1. What server.js is INSIDE the container? ===")
run(c, 'docker exec tokenpay-id-api head -5 /app/server.js')

print("\n=== 2. Does container server.js have enterprise/errors? ===")
run(c, 'docker exec tokenpay-id-api grep -c "enterprise/errors" /app/server.js')

print("\n=== 3. Does container server.js have getGeoByIP? ===")
run(c, 'docker exec tokenpay-id-api grep -c "getGeoByIP" /app/server.js')

print("\n=== 4. Health endpoint in container server.js ===")
run(c, "docker exec tokenpay-id-api grep -A5 \"app.get('/health'\" /app/server.js")

print("\n=== 5. What's on disk at /root/tokenpay-id/backend/server.js? ===")
run(c, 'grep -c "enterprise/errors" /root/tokenpay-id/backend/server.js')
run(c, 'grep -c "getGeoByIP" /root/tokenpay-id/backend/server.js')

print("\n=== 6. File sizes comparison ===")
run(c, 'wc -l /root/tokenpay-id/backend/server.js')
run(c, 'docker exec tokenpay-id-api wc -l /app/server.js')

print("\n=== 7. Is there a volume mount overriding the build? ===")
run(c, 'docker inspect tokenpay-id-api --format "{{json .Mounts}}" 2>/dev/null | python3 -m json.tool 2>/dev/null || docker inspect tokenpay-id-api --format "{{json .Mounts}}"')

print("\n=== 8. Docker compose config ===")
run(c, 'cat /root/tokenpay-id/docker-compose.yml')

c.close()
