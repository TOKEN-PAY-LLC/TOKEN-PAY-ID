#!/usr/bin/env python3
"""Deploy: QR login + captcha fix + dashboard no purple"""
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

print("=== DEPLOY: QR LOGIN + CAPTCHA ===\n")
client = connect()
print("Connected.\n")

# 1. Frontend
print("[1/5] UPLOAD FRONTEND")
fe_data = make_tar(FRONTEND)
print(f"  Size: {len(fe_data)//1024}KB")
upload(client, fe_data, '/tmp/fe.tar.gz')
run(client, "tar -xzf /tmp/fe.tar.gz -C /root/tokenpay-id/frontend/ && rm /tmp/fe.tar.gz")

# 2. Backend
print("\n[2/5] UPLOAD BACKEND")
be_data = make_tar(BACKEND)
print(f"  Size: {len(be_data)//1024}KB")
upload(client, be_data, '/tmp/be.tar.gz')
run(client, "tar -xzf /tmp/be.tar.gz -C /root/tokenpay-id/backend/ && rm /tmp/be.tar.gz")

# 3. Rebuild API
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
print(f"  Health: {'OK' if '\"status\":\"ok\"' in h else 'FAIL - ' + h[:100]}")

# QR login-init
r = run(client, "curl -sk -X POST 'https://tokenpay.space/api/v1/auth/qr/login-init' -H 'Content-Type: application/json' 2>/dev/null", show=False)
has_sid = 'sessionId' in r
print(f"  QR login-init: {'OK - ' + r[:80] if has_sid else 'FAIL - ' + r[:100]}")

# Extract sessionId for poll test
if has_sid:
    import json
    d = json.loads(r)
    sid = d['sessionId']
    r2 = run(client, f"curl -sk 'https://tokenpay.space/api/v1/auth/qr/login-poll/{sid}' 2>/dev/null", show=False)
    print(f"  QR login-poll: {r2[:80]}")

# Captcha
r = run(client, "curl -sk 'https://tokenpay.space/api/v1/captcha/config' 2>/dev/null", show=False)
print(f"  Captcha config: {r[:80]}")
r = run(client, "curl -sk 'https://tokenpay.space/api/v1/captcha/challenge' 2>/dev/null", show=False)
print(f"  Captcha challenge: {'OK' if 'nonce' in r else 'FAIL - ' + r[:80]}")

# Login page has QR button
login = run(client, "curl -sk 'https://tokenpay.space/login' 2>/dev/null", show=False)
print(f"  login.html QR button: {'OK' if 'qrLoginBtn' in login else 'FAIL'}")
print(f"  login.html qrcode-min.js: {'OK' if 'qrcode-min.js' in login else 'FAIL'}")
print(f"  login.html cache bust 20260327b: {'OK' if '20260327b' in login else 'FAIL'}")

# qr-login.html exists
qrl = run(client, "curl -sk 'https://tokenpay.space/qr-login' 2>/dev/null", show=False)
print(f"  qr-login.html: {'OK' if 'login-confirm' in qrl else 'FAIL'}")

# Dashboard no purple
dash = run(client, "curl -sk 'https://tokenpay.space/dashboard' 2>/dev/null", show=False)
print(f"  dashboard no purple: {'CLEAN' if '6c63ff' not in dash and '108,99,255' not in dash else 'STILL HAS PURPLE'}")

# Docker status
print("\n=== DOCKER ===")
run(client, "docker ps --format 'table {{.Names}}\t{{.Status}}' 2>/dev/null")

# Check for errors
logs = run(client, "cd /root/tokenpay-id && docker-compose logs --tail=5 api 2>&1", show=False)
if 'Error' in logs and ('ReferenceError' in logs or 'SyntaxError' in logs):
    print("\n  !! API ERROR:")
    for line in logs.split('\n'):
        if 'Error' in line: print(f"  {line.strip()}")
else:
    print("  API logs: clean")

client.close()
print("\n=== DONE ===")
