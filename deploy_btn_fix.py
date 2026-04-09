#!/usr/bin/env python3
"""Deploy: new TOKEN PAY ID brand buttons"""
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

print("=== DEPLOY: BRAND BUTTONS ===\n")
client = connect()
print("Connected.\n")

# 1. Frontend
print("[1/3] UPLOAD FRONTEND")
fe_data = make_tar(FRONTEND)
print(f"  Size: {len(fe_data)//1024}KB")
upload(client, fe_data, '/tmp/fe.tar.gz')
run(client, "tar -xzf /tmp/fe.tar.gz -C /root/tokenpay-id/frontend/ && rm /tmp/fe.tar.gz")

# 2. Reload nginx
print("\n[2/3] RELOAD NGINX")
run(client, "docker exec tokenpay-id-nginx nginx -s reload 2>&1")
time.sleep(2)

# 3. Verify
print("\n[3/3] VERIFY")

# Check CSS has .tpid-btn
css = run(client, "curl -sk 'https://tokenpay.space/styles.css' 2>/dev/null", show=False)
print(f"  .tpid-btn in CSS: {'OK' if '.tpid-btn{' in css or '.tpid-btn ' in css else 'FAIL'}")
print(f"  .tpid-btn-icon in CSS: {'OK' if '.tpid-btn-icon{' in css or '.tpid-btn-icon ' in css else 'FAIL'}")
print(f"  pill border-radius:50px: {'OK' if 'border-radius:50px' in css else 'FAIL'}")
print(f"  light theme .tpid-btn: {'OK' if 'body.light .tpid-btn' in css else 'FAIL'}")

# Check index.html uses new buttons
idx = run(client, "curl -sk 'https://tokenpay.space/' 2>/dev/null", show=False)
print(f"  index: tpid-btn class: {'OK' if 'class=\"tpid-btn\"' in idx else 'FAIL'}")
print(f"  index: tpid-btn-icon class: {'OK' if 'tpid-btn-icon' in idx else 'FAIL'}")
print(f"  index: tokenpay-icon.png: {'OK' if 'tokenpay-icon.png' in idx else 'FAIL'}")
print(f"  index: no purple gradient: {'OK' if 'linear-gradient(135deg,#6c63ff' not in idx else 'FAIL'}")

# Check script.js uses new buttons
sjs = run(client, "curl -sk 'https://tokenpay.space/script.js' 2>/dev/null", show=False)
print(f"  script.js: tpid-btn class: {'OK' if 'tpid-btn' in sjs else 'FAIL'}")
print(f"  script.js: no purple: {'OK' if '6c63ff' not in sjs else 'FAIL'}")

client.close()
print("\n=== DONE ===")
