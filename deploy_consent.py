#!/usr/bin/env python3
"""Deploy: OAuth consent page redesign"""
import paramiko, os, io

SERVER = "5.23.54.205"
USER = "root"
PASSWORD = "vE^6t-zFS3dpNT"
FRONTEND = r"c:\Users\user\Desktop\TokenPay-Website\frontend"

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
        for line in out.split('\n')[:30]: print("  " + line)
    if show and err:
        for line in err.split('\n')[:5]: print("  ERR: " + line)
    return out

def upload_file(client, local_path, remote_path):
    sftp = client.open_sftp()
    with open(local_path, 'rb') as f:
        data = f.read()
    with sftp.open(remote_path, 'wb') as f:
        f.write(data)
    sftp.close()
    return len(data)

print("=== DEPLOY OAUTH CONSENT ===\n")
client = connect()
print("Connected.\n")

# Upload oauth-consent.html
local = os.path.join(FRONTEND, "oauth-consent.html")
sz = upload_file(client, local, "/root/tokenpay-id/frontend/oauth-consent.html")
print(f"[1/3] Uploaded oauth-consent.html ({sz} bytes)")

# Reload nginx
import time
run(client, "docker exec tokenpay-id-nginx nginx -s reload 2>&1")
print("\n[2/3] Nginx reloaded")
time.sleep(2)

# Verify
print("\n[3/3] VERIFY")
page = run(client, "curl -sk 'https://tokenpay.space/oauth-consent' 2>/dev/null", show=False)
print(f"  Has styles.css: {'OK' if 'styles.css' in page else 'FAIL'}")
print(f"  Has auth-page: {'OK' if 'auth-page' in page else 'FAIL'}")
print(f"  Has auth-card: {'OK' if 'auth-card' in page else 'FAIL'}")
print(f"  Has particles canvas: {'OK' if 'id=\"particles\"' in page else 'FAIL'}")
print(f"  Has script.js: {'OK' if 'script.js' in page else 'FAIL'}")
print(f"  No #4ecdc4 teal: {'OK' if '#4ecdc4' not in page else 'STILL HAS TEAL'}")
print(f"  No consent-header: {'OK' if 'consent-header' not in page else 'STILL HAS OLD HEADER'}")
print(f"  Allow btn white: {'OK' if 'consent-btn-allow' in page and 'background:#fff' in page else 'CHECK'}")
print(f"  Cache v=20260327c: {'OK' if '20260327c' in page else 'FAIL'}")

client.close()
print("\n=== DONE ===")
