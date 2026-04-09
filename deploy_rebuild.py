#!/usr/bin/env python3
"""Rebuild Docker API container with updated backend code"""
import paramiko, time

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

def run(client, cmd, show=True, timeout=300):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    if show and out:
        for line in out.split('\n')[:60]: print("  " + line)
    if show and err:
        for line in err.split('\n')[:10]: print("  ERR: " + line)
    return out

client = connect()
print("Connected.\n")

# 1. Check Dockerfile
print("=== DOCKERFILE ===")
run(client, "cat /root/tokenpay-id/backend/Dockerfile")

# 2. Rebuild API container
print("\n=== REBUILD API CONTAINER ===")
print("  Building (this may take a minute)...")
run(client, "cd /root/tokenpay-id && docker-compose build --no-cache api 2>&1 | tail -20", timeout=300)

# 3. Recreate API container with new image
print("\n=== RECREATE API CONTAINER ===")
run(client, "cd /root/tokenpay-id && docker-compose up -d api 2>&1 | tail -10")
time.sleep(10)

# 4. Check logs
print("\n=== API LOGS ===")
run(client, "cd /root/tokenpay-id && docker-compose logs --tail=15 api 2>&1")

# 5. Health check
print("\n=== HEALTH CHECK ===")
health = run(client, "curl -sk https://tokenpay.space/health 2>/dev/null", show=False)
print(f"  {health[:200] if health else 'no response'}")

# 6. Test check-username endpoint
print("\n=== TEST CHECK-USERNAME ===")
r = run(client, "curl -sk 'https://tokenpay.space/api/v1/auth/check-username?username=testuser123' 2>/dev/null", show=False)
print(f"  Response: {r[:300]}")

# 7. Test client preferences
print("\n=== TEST CLIENT PREFERENCES ===")
r = run(client, "curl -sk 'https://tokenpay.space/api/v1/client/preferences' -H 'Accept-Language: en' 2>/dev/null", show=False)
print(f"  Response: {r[:300]}")

# 8. Test register endpoint accepts username
print("\n=== TEST REGISTER VALIDATION ===")
r = run(client, """curl -sk -X POST 'https://tokenpay.space/api/v1/auth/register' -H 'Content-Type: application/json' -d '{"email":"test@test.com","password":"Test1234!","username":"demo_user"}' 2>/dev/null""", show=False)
print(f"  Response: {r[:300]}")

# 9. Docker status
print("\n=== DOCKER STATUS ===")
run(client, "docker ps --format 'table {{.Names}}\t{{.Status}}' 2>/dev/null")

client.close()
print("\n=== DONE ===")
