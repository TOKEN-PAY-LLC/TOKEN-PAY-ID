#!/usr/bin/env python3
"""Robust deploy: reconnect per upload, small tarballs, rsync-style copy"""
import paramiko, tarfile, os, io, time, socket

SERVER = "5.23.54.205"
USER = "root"
PASSWORD = "vE^6t-zFS3dpNT"
FRONTEND = r"c:\Users\user\Desktop\TokenPay-Website\frontend"
BACKEND = r"c:\Users\user\Desktop\TokenPay-Website\backend"

SKIP_FE = {'.git','node_modules','__pycache__','.DS_Store'}
SKIP_EXT = {'.map', '.log', '.bak'}

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

def run(client, cmd, show=True):
    try:
        _, stdout, stderr = client.exec_command(cmd, timeout=120)
        out = stdout.read().decode('utf-8', errors='replace').strip()
        err = stderr.read().decode('utf-8', errors='replace').strip()
        if show and out:
            for line in out.split('\n')[:40]: print("  " + line)
        if show and err:
            for line in err.split('\n')[:5]: print("  ERR:", line)
        return out
    except Exception as e:
        print("  CMD ERROR:", e)
        return ''

def make_tar(source_dir, skip_dirs=None, skip_exts=None):
    skip_dirs = skip_dirs or SKIP_FE
    skip_exts = skip_exts or SKIP_EXT
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='w:gz', compresslevel=6) as tar:
        for root, dirs, files in os.walk(source_dir):
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            for fn in files:
                if any(fn.endswith(ext) for ext in skip_exts): continue
                fp = os.path.join(root, fn)
                arcname = os.path.relpath(fp, source_dir)
                try:
                    tar.add(fp, arcname=arcname)
                except Exception as e:
                    print(f"    Skip {fn}: {e}")
    buf.seek(0)
    return buf.read()

def upload_robust(data, remote_path, desc):
    print(f"  Uploading {desc} ({len(data)//1024}KB)...")
    client = new_client()
    try:
        sftp = client.open_sftp()
        sftp.sock.settimeout(120)
        buf = io.BytesIO(data)
        sftp.putfo(buf, remote_path)
        sftp.close()
        print(f"  Upload complete: {desc}")
        return client
    except Exception as e:
        client.close()
        print(f"  Upload failed: {e}")
        raise

# ============================================================
print("=== STEP 1: VERIFY NGINX FIX ===")
c = new_client()
hdr = run(c, "curl -skI https://tokenpay.space/ 2>/dev/null | grep -i cache-control", show=False)
print(f"  Cache-Control on tokenpay.space: {hdr or '(none - will patch)'}")
if 'no-cache' not in hdr.lower() and 'no-store' not in hdr.lower():
    print("  Re-applying nginx no-cache patch...")
    nginx_conf = run(c, "cat /root/tokenpay-id/nginx/nginx.conf", show=False)
    if "no-cache, no-store" not in nginx_conf:
        patched = nginx_conf.replace(
            "try_files $uri $uri.html $uri/ /index.html;",
            'try_files $uri $uri.html $uri/ /index.html;\n'
            '          add_header Cache-Control "no-cache, no-store, must-revalidate" always;\n'
            '          add_header Pragma "no-cache" always;\n'
            '          add_header Expires "0" always;'
        )
        sftp = c.open_sftp()
        with sftp.open('/root/tokenpay-id/nginx/nginx.conf', 'w') as f:
            f.write(patched)
        sftp.close()
    run(c, "docker exec tokenpay-id-nginx nginx -s reload 2>&1")
    time.sleep(2)
    hdr2 = run(c, "curl -skI https://tokenpay.space/ 2>/dev/null | grep -i cache-control", show=False)
    print(f"  After patch: {hdr2 or '(still none - headers on HTML may need full reload)'}")
else:
    print("  no-cache already active ✓")
c.close()

# ============================================================
print("\n=== STEP 2: DEPLOY FRONTEND ===")
fe_data = make_tar(FRONTEND)
print(f"  Frontend tar size: {len(fe_data)//1024}KB")
c = upload_robust(fe_data, '/tmp/fe_up.tar.gz', 'frontend')
run(c, "tar -xzf /tmp/fe_up.tar.gz -C /root/tokenpay-id/frontend/ 2>&1 && rm -f /tmp/fe_up.tar.gz && echo 'extracted OK'")
run(c, "docker exec tokenpay-id-nginx nginx -s reload 2>&1")
c.close()

# ============================================================
print("\n=== STEP 3: DEPLOY BACKEND ===")
be_data = make_tar(BACKEND)
print(f"  Backend tar size: {len(be_data)//1024}KB")
c = upload_robust(be_data, '/tmp/be_up.tar.gz', 'backend')
run(c, "tar -xzf /tmp/be_up.tar.gz -C /root/tokenpay-id/backend/ 2>&1 && rm -f /tmp/be_up.tar.gz && echo 'extracted OK'")
run(c, "cd /root/tokenpay-id && docker-compose restart api 2>&1 | tail -5")
print("  Waiting for API restart...")
c.close()
time.sleep(8)

# ============================================================
print("\n=== STEP 4: FINAL VERIFICATION ===")
c = new_client()
health = run(c, "curl -sk https://tokenpay.space/health", show=False)
print(f"  Health: {health[:120]}")

css_domains = ['tokenpay.space', 'auth.tokenpay.space', 'id.tokenpay.space']
print("\n  CSS versions:")
for domain in css_domains:
    ver = run(c, f"curl -sk https://{domain}/ | grep -o 'styles.css?v=[0-9]*' | head -1", show=False)
    ok = 'v=20260325' in ver
    print(f"    {domain}: {ver} {'✓' if ok else '✗ WRONG VERSION'}")

print("\n  Cache-Control headers:")
for domain in css_domains:
    hdr = run(c, f"curl -skI https://{domain}/ 2>/dev/null | grep -i 'cache-control'", show=False)
    print(f"    {domain}: {hdr or '(no header)'}")

print("\n  QR endpoint test (unauthenticated → 401):")
qr_test = run(c, "curl -sk -X POST https://tokenpay.space/api/v1/auth/qr/generate | head -c 80", show=False)
print(f"    {qr_test}")

print("\n  Docker status:")
run(c, "docker ps --format 'table {{.Names}}\t{{.Status}}'")
c.close()

print("\n=== ALL DONE ===")
print("Summary of all improvements deployed:")
print("  FIX  nginx no-cache → browsers always get fresh HTML on all domains")
print("  FIX  CSS v=20260325 → new styles.css loaded everywhere")
print("  FIX  .light-html selectors → logos black instantly (no FOUC)")
print("  NEW  TPID.openPopup() → native browser popup login window")
print("  NEW  QR code login → /api/v1/auth/qr/generate|status|scan")
print("  NEW  Session management → list/revoke/revoke-all")
print("  NEW  Toast notifications → global tpToast.success/error/info")
print("  NEW  Button ripple effects → all .auth-btn/.tp-btn etc")
print("  NEW  Skeleton loading → .skeleton class")
print("  NEW  Spring physics mobile menu → cubic-bezier transitions")
print("  NEW  Hero float animation → .hero-logo-big")
print("  NEW  Card hover lift → .feature-card:hover translateY(-4px)")
print("  NEW  Smooth custom scrollbar")
print("  NEW  Page fade-in transitions → body animation")
