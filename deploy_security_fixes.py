#!/usr/bin/env python3
"""Deploy security fixes from pentest: backend (server.js), nginx config, docker-compose"""
import paramiko, tarfile, os, io, time

SERVER = "5.23.54.205"
USER = "root"
PASSWORD = "vE^6t-zFS3dpNT"

BACKEND = r"c:\Users\user\Desktop\TokenPay-Website\backend"
NGINX = r"c:\Users\user\Desktop\TokenPay-Website\nginx"
COMPOSE = r"c:\Users\user\Desktop\TokenPay-Website\docker-compose.yml"

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
        for line in err.split('\n')[:5]: print("  ERR:", line)
    return out

def make_tar(d):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='w:gz', compresslevel=6) as tar:
        for root, dirs, files in os.walk(d):
            dirs[:] = [x for x in dirs if x not in {'.git','node_modules','__pycache__','.wrangler'}]
            for fn in files:
                if fn.endswith(('.map','.log','.bak')): continue
                fp = os.path.join(root, fn)
                tar.add(fp, arcname=os.path.relpath(fp, d))
    buf.seek(0)
    return buf.read()

print("=" * 60)
print("  DEPLOYING SECURITY FIXES (pentest remediation)")
print("=" * 60)

# 1. Build backend tarball
print("\n[1/6] Building backend tarball...")
be = make_tar(BACKEND)
print(f"  Size: {len(be)//1024}KB")

# 2. Build nginx tarball
print("[2/6] Building nginx tarball...")
ng = make_tar(NGINX)
print(f"  Size: {len(ng)//1024}KB")

# 3. Upload files
print("[3/6] Uploading to server...")
c = new_client()
sftp = c.open_sftp()
sftp.putfo(io.BytesIO(be), '/tmp/backend_fix.tar.gz')
sftp.putfo(io.BytesIO(ng), '/tmp/nginx_fix.tar.gz')
# Upload docker-compose.yml
with open(COMPOSE, 'rb') as f:
    sftp.putfo(f, '/tmp/docker-compose-fix.yml')
sftp.close()
print("  All files uploaded")

# 4. Deploy backend
print("[4/6] Deploying backend (server.js)...")
run(c, "cd /root/tokenpay-id && tar -xzf /tmp/backend_fix.tar.gz -C backend/ && rm /tmp/backend_fix.tar.gz && echo 'Backend extracted OK'")

# 5. Deploy nginx config
print("[5/6] Deploying nginx config...")
run(c, "cd /root/tokenpay-id && tar -xzf /tmp/nginx_fix.tar.gz -C nginx/ && rm /tmp/nginx_fix.tar.gz && echo 'Nginx extracted OK'")

# Deploy docker-compose
run(c, "cp /tmp/docker-compose-fix.yml /root/tokenpay-id/docker-compose.yml && rm /tmp/docker-compose-fix.yml && echo 'docker-compose updated'")

# 6. Rebuild and restart
print("[6/6] Rebuilding and restarting containers...")
run(c, "cd /root/tokenpay-id && docker-compose up -d --build 2>&1 | tail -20")
time.sleep(5)

# Verify
print("\n" + "=" * 60)
print("  VERIFICATION")
print("=" * 60)

# Check containers
print("\nContainer status:")
run(c, "docker ps --format 'table {{.Names}}\t{{.Status}}' | grep tokenpay")

# Check health
print("\nHealth check:")
run(c, "curl -sk https://tokenpay.space/health 2>&1")

# Check version headers removed
print("\nVersion header check (should be empty):")
run(c, "curl -sk -o /dev/null -D - https://tokenpay.space/api/v1/auth/verify -X POST -H 'Content-Type: application/json' -d '{\"token\":\"x\"}' 2>&1 | grep -i 'x-api-version\\|x-tpid-sdk'")

# Check X-Frame-Options
print("\nX-Frame-Options check:")
run(c, "curl -sk -o /dev/null -D - https://tokenpay.space/ 2>&1 | grep -i 'x-frame-options'")

# Check Cache-Control on dashboard
print("\nCache-Control on dashboard:")
run(c, "curl -sk -o /dev/null -D - https://tokenpay.space/dashboard 2>&1 | grep -i 'cache-control'")

# Check JSON parse error handling
print("\nJSON parse error handling:")
run(c, "curl -sk https://tokenpay.space/api/v1/auth/login -H 'Content-Type: application/json' -d '{bad json' 2>&1")

c.close()
print("\n" + "=" * 60)
print("  SECURITY FIXES DEPLOYED SUCCESSFULLY")
print("=" * 60)
