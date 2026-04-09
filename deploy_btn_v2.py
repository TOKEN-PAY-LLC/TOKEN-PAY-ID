#!/usr/bin/env python3
"""Deploy: proper brand buttons with logo images"""
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

print("=== DEPLOY: BRAND BUTTONS V2 ===\n")
client = connect()
print("Connected.\n")

print("[1/2] UPLOAD FRONTEND")
fe_data = make_tar(FRONTEND)
upload(client, fe_data, '/tmp/fe.tar.gz')
run(client, "tar -xzf /tmp/fe.tar.gz -C /root/tokenpay-id/frontend/ && rm /tmp/fe.tar.gz")
run(client, "docker exec tokenpay-id-nginx nginx -s reload 2>&1")
time.sleep(2)

print("\n[2/2] VERIFY")
# CSS checks
css = run(client, "curl -sk 'https://tokenpay.space/styles.css' 2>/dev/null", show=False)
print(f"  .tpid-btn with border-radius:50px: {'OK' if 'border-radius:50px' in css else 'FAIL'}")
print(f"  .tpid-btn img height:14px: {'OK' if '.tpid-btn img{height:14px' in css else 'FAIL'}")
print(f"  .tpid-btn-icon 32x32: {'OK' if 'width:32px;height:32px' in css else 'FAIL'}")
print(f"  .tpid-btn-icon img 20x20: {'OK' if 'width:20px;height:20px;max-width:20px' in css else 'FAIL'}")
print(f"  tpid-logo-light/dark switching: {'OK' if 'tpid-logo-dark{display:none' in css or '.tpid-logo-dark{display:none}' in css else 'FAIL'}")
print(f"  body.light tpid-btn dark border: {'OK' if 'body.light .tpid-btn{border-color:rgba(0,0,0' in css else 'FAIL'}")
print(f"  icon button dark-only bg:#111: {'OK' if '.tpid-btn-icon{' in css and 'background:#111' in css else 'FAIL'}")

# HTML checks
idx = run(client, "curl -sk 'https://tokenpay.space/' 2>/dev/null", show=False)
print(f"  index: tpid-btn with logo imgs: {'OK' if 'tpid-logo-light' in idx and 'tpid-logo-dark' in idx else 'FAIL'}")
print(f"  index: tpid-btn-icon with icon: {'OK' if 'tpid-btn-icon' in idx and 'tokenpay-icon.png' in idx else 'FAIL'}")
print(f"  index: both buttons present: {'OK' if idx.count('class=\"tpid-btn\"') >= 1 and 'tpid-btn-icon' in idx else 'FAIL'}")

# script.js checks
sjs = run(client, "curl -sk 'https://tokenpay.space/script.js' 2>/dev/null", show=False)
print(f"  script.js: logo images in buttons: {'OK' if 'tpid-logo-light' in sjs and 'tpid-logo-dark' in sjs else 'FAIL'}")

client.close()
print("\n=== DONE ===")
