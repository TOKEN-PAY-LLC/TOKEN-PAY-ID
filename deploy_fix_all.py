#!/usr/bin/env python3
"""Deploy: fix purple, oauth-consent, state persistence"""
import paramiko, tarfile, os, io, time, json

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
        for line in out.split('\n')[:50]: print("  " + line)
    if show and err:
        for line in err.split('\n')[:5]: print("  ERR: " + line)
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

print("=== DEPLOY: FIX PURPLE + OAUTH + STATE PERSISTENCE ===\n")
client = connect()
print("Connected.\n")

# 1. Frontend
print("[1/5] UPLOAD FRONTEND")
fe_data = make_tar(FRONTEND)
print(f"  Size: {len(fe_data)//1024}KB")
upload(client, fe_data, '/tmp/fe.tar.gz')
run(client, "tar -xzf /tmp/fe.tar.gz -C /root/tokenpay-id/frontend/ && rm /tmp/fe.tar.gz")

# 2. Backend (authMiddleware fix)
print("\n[2/5] UPLOAD BACKEND")
be_data = make_tar(BACKEND)
print(f"  Size: {len(be_data)//1024}KB")
upload(client, be_data, '/tmp/be.tar.gz')
run(client, "tar -xzf /tmp/be.tar.gz -C /root/tokenpay-id/backend/ && rm /tmp/be.tar.gz")

# 3. Rebuild + restart API
print("\n[3/5] REBUILD & RESTART API")
run(client, "cd /root/tokenpay-id && docker-compose build --no-cache api 2>&1 | tail -5", timeout=300)
run(client, "cd /root/tokenpay-id && docker-compose up -d api 2>&1 | tail -5")
print("  Waiting 10s...")
time.sleep(10)

# 4. Reload nginx
print("\n[4/5] RELOAD NGINX")
run(client, "docker exec tokenpay-id-nginx nginx -s reload 2>&1")
time.sleep(2)

# 5. Verify
print("\n[5/5] VERIFY")

# Health
h = run(client, "curl -sk https://tokenpay.space/health 2>/dev/null", show=False)
ok = '"status":"ok"' in h
print(f"  Health: {'OK' if ok else 'FAIL - ' + h[:100]}")

# No purple in index.html
idx = run(client, "curl -sk 'https://tokenpay.space/' 2>/dev/null", show=False)
has_purple = '#6c63ff' in idx or '6c63ff' in idx
print(f"  index.html no purple (#6c63ff): {'FAIL - still has purple!' if has_purple else 'OK'}")
has_gradient = 'linear-gradient(135deg,#6c63ff' in idx
print(f"  index.html no purple gradient: {'FAIL' if has_gradient else 'OK'}")

# OAuth consent no purple header
consent = run(client, "curl -sk 'https://tokenpay.space/oauth-consent' 2>/dev/null", show=False)
has_purple_consent = '#2d2b5e' in consent or '#1e1d40' in consent or 'linear-gradient(145deg' in consent
print(f"  oauth-consent no purple header: {'FAIL' if has_purple_consent else 'OK'}")
has_6c63 = '6c63ff' in consent
print(f"  oauth-consent no #6c63ff: {'FAIL' if has_6c63 else 'OK'}")
has_teal_btn = '#4ecdc4' in consent and 'consent-btn-allow' in consent
print(f"  oauth-consent teal allow button: {'OK' if has_teal_btn else 'FAIL'}")

# Register state persistence
reg = run(client, "curl -sk 'https://tokenpay.space/register' 2>/dev/null", show=False)
has_reg_state = 'tpid_reg_state' in reg
print(f"  register.html state persistence: {'OK' if has_reg_state else 'FAIL'}")

# Login state persistence
login = run(client, "curl -sk 'https://tokenpay.space/login' 2>/dev/null", show=False)
has_login_state = 'tpid_login_state' in login
print(f"  login.html state persistence: {'OK' if has_login_state else 'FAIL'}")

# script.js no purple
sjs = run(client, "curl -sk 'https://tokenpay.space/script.js' 2>/dev/null", show=False)
has_purple_sjs = '6c63ff' in sjs
print(f"  script.js no purple: {'FAIL' if has_purple_sjs else 'OK'}")

# Check-username still works
r = run(client, "curl -sk 'https://tokenpay.space/api/v1/auth/check-username?username=test_ok_123' 2>/dev/null", show=False)
print(f"  check-username API: {r[:80]}")

# Docker
print("\n=== DOCKER STATUS ===")
run(client, "docker ps --format 'table {{.Names}}\t{{.Status}}' 2>/dev/null")

# Check API logs for errors
logs = run(client, "cd /root/tokenpay-id && docker-compose logs --tail=5 api 2>&1", show=False)
if 'ReferenceError' in logs or 'SyntaxError' in logs:
    print("\n  !! API ERROR IN LOGS:")
    for line in logs.split('\n'):
        if 'Error' in line: print(f"  {line.strip()}")
else:
    print("  API logs: no errors")

client.close()
print("\n=== DEPLOY COMPLETE ===")
