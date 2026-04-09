#!/usr/bin/env python3
"""Deploy: remove all purple from dashboard, cache bust"""
import paramiko, tarfile, os, io, time

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

def run(client, cmd, show=True, timeout=120):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
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

print("=== DEPLOY: DASHBOARD NO PURPLE ===\n")
client = connect()
print("Connected.\n")

print("[1/2] UPLOAD FRONTEND")
fe_data = make_tar(FRONTEND)
upload(client, fe_data, '/tmp/fe.tar.gz')
run(client, "tar -xzf /tmp/fe.tar.gz -C /root/tokenpay-id/frontend/ && rm /tmp/fe.tar.gz")
run(client, "docker exec tokenpay-id-nginx nginx -s reload 2>&1")
time.sleep(2)

print("\n[2/2] VERIFY")

# Dashboard no purple
dash = run(client, "curl -sk 'https://tokenpay.space/dashboard' 2>/dev/null", show=False)
p1 = '6c63ff' in dash
p2 = '108,99,255' in dash
print(f"  dashboard #6c63ff: {'FAIL - STILL HAS IT' if p1 else 'CLEAN'}")
print(f"  dashboard rgba(108,99,255): {'FAIL' if p2 else 'CLEAN'}")
print(f"  dashboard cache bust v=20260327b: {'OK' if '20260327b' in dash else 'FAIL'}")

# btn-primary is now white/black not gradient
has_white_btn = 'background:#fff;color:#000' in dash or 'background:#111;color:#fff' in dash
print(f"  btn-primary black/white: {'OK' if has_white_btn else 'CHECK'}")

# Full frontend scan
for f in ['/', '/login', '/register', '/docs', '/oauth-consent']:
    page = run(client, f"curl -sk 'https://tokenpay.space{f}' 2>/dev/null", show=False)
    has_p = '6c63ff' in page or '108,99,255' in page
    print(f"  {f}: {'PURPLE FOUND!' if has_p else 'clean'}")

client.close()
print("\n=== DONE ===")
