#!/usr/bin/env python3
"""Deploy: upload backend, rebuild Docker, verify all endpoints"""
import paramiko, tarfile, os, io, time

SERVER = "5.23.54.205"
USER = "root"
PASSWORD = "vE^6t-zFS3dpNT"
BACKEND = r"c:\Users\user\Desktop\TokenPay-Website\backend"
FRONTEND = r"c:\Users\user\Desktop\TokenPay-Website\frontend"

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

def make_tar(source_dir):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='w:gz') as tar:
        for root, dirs, files in os.walk(source_dir):
            dirs[:] = [d for d in dirs if d not in ['node_modules', '.git', '__pycache__']]
            for fn in files:
                fp = os.path.join(root, fn)
                arcname = os.path.relpath(fp, source_dir)
                tar.add(fp, arcname=arcname)
    buf.seek(0)
    return buf.read()

def upload(client, data, remote_path):
    sftp = client.open_sftp()
    with sftp.open(remote_path, 'wb') as f:
        f.write(data)
    sftp.close()

print("=== DEPLOY V4: BACKEND REBUILD + FRONTEND ===\n")
client = connect()
print("Connected.\n")

# 1. Upload backend
print("[1/7] UPLOAD BACKEND")
be_data = make_tar(BACKEND)
print(f"  Size: {len(be_data)//1024}KB")
upload(client, be_data, '/tmp/be.tar.gz')
run(client, "rm -rf /root/tokenpay-id/backend/server.js /root/tokenpay-id/backend/email-service.js /root/tokenpay-id/backend/test-templates.js")
run(client, "tar -xzf /tmp/be.tar.gz -C /root/tokenpay-id/backend/ && rm /tmp/be.tar.gz")
# Verify new code is there
r = run(client, "grep -c 'check-username' /root/tokenpay-id/backend/server.js", show=False)
print(f"  check-username in server.js: {r}")
r = run(client, "grep -c 'authMiddleware' /root/tokenpay-id/backend/server.js", show=False)
print(f"  authMiddleware refs: {r}")

# 2. Upload frontend
print("\n[2/7] UPLOAD FRONTEND")
fe_data = make_tar(FRONTEND)
print(f"  Size: {len(fe_data)//1024}KB")
upload(client, fe_data, '/tmp/fe.tar.gz')
run(client, "tar -xzf /tmp/fe.tar.gz -C /root/tokenpay-id/frontend/ && rm /tmp/fe.tar.gz")
r = run(client, "grep -c 'regUsername' /root/tokenpay-id/frontend/register.html", show=False)
print(f"  regUsername in register.html: {r}")

# 3. Rebuild Docker API
print("\n[3/7] REBUILD DOCKER API")
run(client, "cd /root/tokenpay-id && docker-compose build --no-cache api 2>&1 | tail -10", timeout=300)

# 4. Recreate container
print("\n[4/7] RECREATE API CONTAINER")
run(client, "cd /root/tokenpay-id && docker-compose up -d api 2>&1 | tail -5")
print("  Waiting 10s for startup...")
time.sleep(10)

# 5. Check logs for errors
print("\n[5/7] API LOGS")
logs = run(client, "cd /root/tokenpay-id && docker-compose logs --tail=15 api 2>&1", show=False)
if 'Error' in logs or 'error' in logs.lower().split('smtp')[0]:
    print("  ⚠ Possible errors in logs:")
    for line in logs.split('\n'):
        if 'error' in line.lower() or 'Error' in line:
            print(f"  {line.strip()}")
else:
    print("  ✓ No errors in logs")
# Print last few lines
for line in logs.split('\n')[-5:]:
    print(f"  {line.strip()}")

# 6. Reload nginx
print("\n[6/7] RELOAD NGINX")
run(client, "docker exec tokenpay-id-nginx nginx -s reload 2>&1")
time.sleep(2)

# 7. Verify all endpoints
print("\n[7/7] VERIFY ENDPOINTS")

# Health
h = run(client, "curl -sk https://tokenpay.space/health 2>/dev/null", show=False)
ok = '"status":"ok"' in h
print(f"  Health: {'✓ OK' if ok else '✗ FAIL — ' + h[:100]}")

# Check-username
r = run(client, "curl -sk 'https://tokenpay.space/api/v1/auth/check-username?username=test_user_123' 2>/dev/null", show=False)
print(f"  check-username: {r[:120]}")

# Client preferences
r = run(client, "curl -sk 'https://tokenpay.space/api/v1/client/preferences' -H 'Accept-Language: en' 2>/dev/null", show=False)
print(f"  client/preferences: {r[:120]}")

# Register validation (missing code → expect error, not crash)
r = run(client, """curl -sk -X POST 'https://tokenpay.space/api/v1/auth/register' -H 'Content-Type: application/json' -d '{"email":"x@x.com","password":"Test12345","username":"demo_usr"}' 2>/dev/null""", show=False)
print(f"  register validation: {r[:150]}")

# Stars fix
for f in ['script.js']:
    r = run(client, f"curl -sk 'https://tokenpay.space/{f}' 2>/dev/null | grep -c '160,150,220'", show=False)
    print(f"  stars fix ({f}): {'✓' if r.strip() != '0' else '✗'}")

# Register page
r = run(client, "curl -sk 'https://tokenpay.space/register' 2>/dev/null | grep -c 'regUsername'", show=False)
print(f"  register page (username field): {'✓' if r.strip() != '0' else '✗'}")

# Docker status
print("\n=== DOCKER STATUS ===")
run(client, "docker ps --format 'table {{.Names}}\t{{.Status}}' 2>/dev/null")

client.close()
print("\n=== DEPLOY COMPLETE ===")
