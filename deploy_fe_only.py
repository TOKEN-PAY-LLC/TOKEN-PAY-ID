#!/usr/bin/env python3
import paramiko, tarfile, os, io

SERVER = "5.23.54.205"
USER = "root"
PASSWORD = "vE^6t-zFS3dpNT"
FRONTEND = r"c:\Users\user\Desktop\TokenPay-Website\frontend"

def new_client():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(SERVER, port=22, username=USER, password=PASSWORD,
              timeout=120, banner_timeout=60, auth_timeout=60,
              allow_agent=False, look_for_keys=False)
    t = c.get_transport()
    t.set_keepalive(30)
    t.window_size = 4 * 1024 * 1024
    t.packetizer.REKEY_BYTES = pow(2, 40)
    t.packetizer.REKEY_PACKETS = pow(2, 40)
    return c

def run(c, cmd, show=True):
    _, stdout, stderr = c.exec_command(cmd, timeout=120)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    if show and out:
        for line in out.split('\n')[:30]: print("  " + line)
    if show and err:
        for line in err.split('\n')[:3]: print("  ERR:", line)
    return out

def make_tar(d):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='w:gz', compresslevel=6) as tar:
        for root, dirs, files in os.walk(d):
            dirs[:] = [x for x in dirs if x not in {'.git','node_modules','__pycache__'}]
            for fn in files:
                if fn.endswith(('.map','.log','.bak')): continue
                fp = os.path.join(root, fn)
                tar.add(fp, arcname=os.path.relpath(fp, d))
    buf.seek(0)
    return buf.read()

print("Building frontend tarball...")
fe = make_tar(FRONTEND)
print(f"  Size: {len(fe)//1024}KB")

c = new_client()
sftp = c.open_sftp()
sftp.putfo(io.BytesIO(fe), '/tmp/fe2.tar.gz')
sftp.close()
print("  Uploaded")

run(c, "tar -xzf /tmp/fe2.tar.gz -C /root/tokenpay-id/frontend/ && rm /tmp/fe2.tar.gz && echo OK")
run(c, "docker exec tokenpay-id-nginx nginx -s reload 2>&1")
ver = run(c, "curl -sk https://tokenpay.space/ | grep -o 'styles.css?v=[0-9]*'", show=False)
print(f"  CSS version on tokenpay.space: {ver}")
c.close()
print("Frontend deployed.")
