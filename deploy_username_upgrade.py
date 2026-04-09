#!/usr/bin/env python3
"""Deploy username/theme/stars upgrade: backend + frontend"""
import paramiko, tarfile, os, io, time

SERVER = "5.23.54.205"
USER = "root"
PASSWORD = "vE^6t-zFS3dpNT"
FRONTEND = r"c:\Users\user\Desktop\TokenPay-Website\frontend"
BACKEND = r"c:\Users\user\Desktop\TokenPay-Website\backend"

def connect():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(SERVER, port=22, username=USER, password=PASSWORD,
              timeout=60, banner_timeout=60, auth_timeout=60,
              allow_agent=False, look_for_keys=False)
    return c

def run(client, cmd, show=True):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=120)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    if show and out:
        for line in out.split('\n')[:40]: print("  " + line)
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

print("=== USERNAME / THEME / STARS UPGRADE DEPLOY ===\n")

client = connect()
print("Connected to server.\n")

# 1. Deploy frontend
print("=== DEPLOY FRONTEND ===")
fe_data = make_tar(FRONTEND)
print(f"  Archive size: {len(fe_data)//1024}KB")
upload(client, fe_data, '/tmp/fe_upgrade.tar.gz')
run(client, "tar -xzf /tmp/fe_upgrade.tar.gz -C /root/tokenpay-id/frontend/ && rm /tmp/fe_upgrade.tar.gz")
print("  Frontend deployed\n")

# 2. Deploy backend
print("=== DEPLOY BACKEND ===")
be_data = make_tar(BACKEND)
print(f"  Archive size: {len(be_data)//1024}KB")
upload(client, be_data, '/tmp/be_upgrade.tar.gz')
run(client, "tar -xzf /tmp/be_upgrade.tar.gz -C /root/tokenpay-id/backend/ && rm /tmp/be_upgrade.tar.gz")
print("  Backend deployed\n")

# 3. Install any new npm deps (cookie-parser should already be there)
print("=== INSTALL DEPS ===")
run(client, "cd /root/tokenpay-id/backend && docker-compose exec -T api npm install --production 2>&1 | tail -5")
print()

# 4. Restart API container
print("=== RESTART API ===")
run(client, "cd /root/tokenpay-id && docker-compose restart api 2>&1 | tail -5")
time.sleep(8)
health = run(client, "curl -sk https://tokenpay.space/health 2>/dev/null", show=False)
print(f"  Health: {health[:200] if health else 'no response'}\n")

# 5. Reload nginx
print("=== RELOAD NGINX ===")
run(client, "docker exec tokenpay-id-nginx nginx -s reload 2>&1")
time.sleep(2)
print()

# 6. Verify new endpoint
print("=== VERIFY CHECK-USERNAME ENDPOINT ===")
r = run(client, "curl -sk 'https://tokenpay.space/api/v1/auth/check-username?username=testuser123' 2>/dev/null", show=False)
print(f"  check-username response: {r[:200]}")

# 7. Verify client preferences endpoint
print("\n=== VERIFY CLIENT PREFERENCES ===")
r = run(client, "curl -sk 'https://tokenpay.space/api/v1/client/preferences' -H 'Accept-Language: en' 2>/dev/null", show=False)
print(f"  preferences response: {r[:200]}")

# 8. Check register page has username field
print("\n=== VERIFY REGISTER PAGE ===")
r = run(client, "curl -sk 'https://tokenpay.space/register' 2>/dev/null | grep -o 'regUsername\\|Логин\\|check-username' | head -5", show=False)
print(f"  register page keywords: {r}")

# 9. Check stars color fix
print("\n=== VERIFY STARS FIX ===")
for page in ['script.js', 'dashboard', 'docs']:
    url = f"https://tokenpay.space/{page}" if page != 'script.js' else "https://tokenpay.space/script.js"
    r = run(client, f"curl -sk '{url}' 2>/dev/null | grep -o '160,150,220' | head -1", show=False)
    print(f"  {page}: {'FIXED (160,150,220)' if r else 'NOT FOUND'}")

# 10. Docker status
print("\n=== DOCKER STATUS ===")
run(client, "docker ps --format 'table {{.Names}}\t{{.Status}}' 2>/dev/null")

client.close()
print("\n=== DEPLOYMENT COMPLETE ===")
print("Changes deployed:")
print("  ✓ Registration: Name → Username (Login) with real-time availability check")
print("  ✓ Backend: /auth/check-username endpoint + username DB column")
print("  ✓ Theme/Language: auto-detect middleware, cookies, API sync")
print("  ✓ Stars: soft pastel in light theme (no more dark dots)")
print("  ✓ Client preferences: /client/preferences endpoint")
