#!/usr/bin/env python3
"""Deploy frontend with cache-busted versions"""
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

print("=== DEPLOY: CACHE BUST v20260327a ===\n")
client = connect()
print("Connected.\n")

print("[1/2] UPLOAD FRONTEND")
fe_data = make_tar(FRONTEND)
upload(client, fe_data, '/tmp/fe.tar.gz')
run(client, "tar -xzf /tmp/fe.tar.gz -C /root/tokenpay-id/frontend/ && rm /tmp/fe.tar.gz")
run(client, "docker exec tokenpay-id-nginx nginx -s reload 2>&1")
time.sleep(2)

print("\n[2/2] VERIFY")
idx = run(client, "curl -sk 'https://tokenpay.space/' 2>/dev/null", show=False)
print(f"  CSS version: {'20260327a' if '20260327a' in idx else 'OLD - ' + (idx[idx.find('styles.css'):idx.find('styles.css')+30] if 'styles.css' in idx else 'not found')}")
print(f"  script.js version: {'20260327a' if 'script.js?v=20260327a' in idx else 'OLD'}")
print(f"  tpid-btn class present: {'OK' if 'class=\"tpid-btn\"' in idx else 'FAIL'}")
print(f"  tpid-btn-icon present: {'OK' if 'tpid-btn-icon' in idx else 'FAIL'}")
print(f"  tpid-logo-light img: {'OK' if 'tpid-logo-light' in idx else 'FAIL'}")
print(f"  tpid-logo-dark img: {'OK' if 'tpid-logo-dark' in idx else 'FAIL'}")

# Verify CSS content
css = run(client, "curl -sk 'https://tokenpay.space/styles.css?v=20260327a' 2>/dev/null", show=False)
print(f"  CSS has .tpid-btn rules: {'OK' if '.tpid-btn{' in css else 'FAIL'}")
print(f"  CSS logo height:16px: {'OK' if 'height:16px' in css else 'FAIL'}")
print(f"  CSS icon 32x32: {'OK' if 'width:32px;height:32px' in css else 'FAIL'}")

client.close()
print("\n=== DONE — tell user to Ctrl+Shift+R ===")
