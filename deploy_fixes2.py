#!/usr/bin/env python3
"""Deploy: QR fix + dashboard prod mode + magic link button restyle"""
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

print("=== DEPLOY FIXES v2 ===\n")
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
import json
r = run(client, "curl -sk -X POST 'https://tokenpay.space/api/v1/auth/qr/login-init' -H 'Content-Type: application/json' 2>/dev/null", show=False)
has_sid = 'sessionId' in r
print(f"  QR login-init: {'OK' if has_sid else 'FAIL - ' + r[:100]}")
if has_sid:
    d = json.loads(r)
    sid = d['sessionId']
    print(f"    qrUrl: {d.get('qrUrl','')[:60]}")
    r2 = run(client, "curl -sk 'https://tokenpay.space/api/v1/auth/qr/login-poll/" + sid + "' 2>/dev/null", show=False)
    print(f"    poll: {r2[:60]}")

# Login page checks
login = run(client, "curl -sk 'https://tokenpay.space/login' 2>/dev/null", show=False)
print(f"  login.html QR button: {'OK' if 'qrLoginBtn' in login else 'FAIL'}")
print(f"  login.html QRCode.generate: {'OK' if 'QRCode.generate' in login else 'FAIL'}")
print(f"  login.html magic link compact: {'OK' if 'inline-flex' in login and 'Войти по ссылке' in login else 'NEEDS CHECK'}")
print(f"  login.html cache v=20260327c: {'OK' if '20260327c' in login else 'FAIL'}")

# Dashboard checks
dash = run(client, "curl -sk 'https://tokenpay.space/dashboard' 2>/dev/null", show=False)
print(f"  dashboard no random chart: {'OK (no Math.random)' if 'Math.random()*800' not in dash else 'STILL HAS RANDOM'}")
print(f"  dashboard no hardcoded uptime: {'OK' if '99.9%' not in dash else 'STILL HAS 99.9%'}")
print(f"  dashboard login-init endpoint: {'OK' if 'login-init' in dash else 'FAIL'}")
print(f"  dashboard login-poll endpoint: {'OK' if 'login-poll' in dash else 'FAIL'}")
print(f"  dashboard cache v=20260327c: {'OK' if '20260327c' in dash else 'FAIL'}")

# qr-login.html
qrl = run(client, "curl -sk 'https://tokenpay.space/qr-login?sid=test' 2>/dev/null", show=False)
print(f"  qr-login.html: {'OK' if 'login-confirm' in qrl else 'FAIL'}")

# API error check
logs = run(client, "cd /root/tokenpay-id && docker-compose logs --tail=8 api 2>&1", show=False)
has_err = 'ReferenceError' in logs or 'SyntaxError' in logs or 'TypeError' in logs
if has_err:
    print("\n  !! API ERRORS:")
    for line in logs.split('\n'):
        if 'Error' in line: print(f"  {line.strip()}")
else:
    print("  API logs: clean")

print("\n=== DOCKER ===")
run(client, "docker ps --format 'table {{.Names}}\t{{.Status}}' 2>/dev/null")

client.close()
print("\n=== DONE ===")
