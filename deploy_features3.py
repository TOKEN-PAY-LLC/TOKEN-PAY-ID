#!/usr/bin/env python3
"""Deploy v3: force no-cache rebuild to ensure new server.js is picked up"""
import paramiko, os, time

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

def run(c, cmd, show=True, timeout=180):
    _, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    if show and out:
        for line in out.split('\n')[:30]: print("  " + line)
    if show and err and 'warning' not in err.lower():
        for line in err.split('\n')[:5]: print("  ERR:", line)
    return out

def main():
    print("=" * 60)
    print("  DEPLOY v3: Force no-cache rebuild")
    print("=" * 60)

    # 1. Verify our new files are on disk
    print("\n[1/5] Verify new code is on disk...")
    c = new_client()
    print("  Checking enterprise/errors route in server.js:")
    run(c, 'grep -c "enterprise/errors" /root/tokenpay-id/backend/server.js')
    print("  Checking IP geolocation in server.js:")
    run(c, 'grep -c "getGeoByIP" /root/tokenpay-id/backend/server.js')
    print("  Checking zh in email-service.js:")
    run(c, 'grep -c "zh:" /root/tokenpay-id/backend/email-service.js')
    print("  Checking health endpoint format:")
    run(c, "grep -A2 \"app.get('/health'\" /root/tokenpay-id/backend/server.js | head -5")
    c.close()

    # 2. Force rebuild with --no-cache
    print("\n[2/5] Force rebuild (--no-cache)...")
    c = new_client()
    run(c, 'cd /root/tokenpay-id && docker-compose build --no-cache api 2>&1 | tail -20', timeout=300)
    c.close()

    # 3. Restart container
    print("\n[3/5] Restarting api container...")
    c = new_client()
    run(c, 'cd /root/tokenpay-id && docker-compose up -d api 2>&1 | tail -10')
    c.close()

    print("  Waiting 15s for container to start...")
    time.sleep(15)

    # 4. Reload nginx
    print("\n[4/5] Reloading nginx...")
    c = new_client()
    run(c, 'docker exec tokenpay-id-nginx nginx -s reload 2>&1')
    c.close()
    time.sleep(2)

    # 5. Verify
    print("\n[5/5] Verifying...")
    c = new_client()

    print("\n  Container status:")
    run(c, 'docker ps --filter name=tokenpay --format "table {{.Names}}\t{{.Status}}"')

    print("\n  /health:")
    run(c, 'curl -s http://localhost:8080/health')

    print("\n  /client/preferences:")
    run(c, 'curl -s http://localhost:8080/api/v1/client/preferences')

    print("\n  /enterprise/errors POST (no auth):")
    run(c, 'curl -s -X POST http://localhost:8080/api/v1/enterprise/errors -H "Content-Type: application/json" -d \'{"error_type":"test","error_message":"test"}\'')

    print("\n  /enterprise/health POST (no auth):")
    run(c, 'curl -s -X POST http://localhost:8080/api/v1/enterprise/health -H "Content-Type: application/json" -d \'{"status":"ok"}\'')

    print("\n  SDK via nginx:")
    run(c, 'curl -s https://tokenpay.space/sdk/tokenpay-auth.js 2>/dev/null | head -5')

    print("\n  Docker logs (last 10):")
    run(c, 'docker logs tokenpay-id-api --tail 10 2>&1')

    c.close()

    print("\n" + "=" * 60)
    print("  DONE")
    print("=" * 60)

if __name__ == '__main__':
    main()
