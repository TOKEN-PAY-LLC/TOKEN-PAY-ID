#!/usr/bin/env python3
"""Deploy feature updates: enterprise error logging, ZH language, SDK v3, IP geolocation"""
import paramiko, tarfile, os, io, time

SERVER = "5.23.54.205"
USER = "root"
PASSWORD = "vE^6t-zFS3dpNT"

BACKEND = r"c:\Users\user\Desktop\TokenPay-Website\backend"
FRONTEND = r"c:\Users\user\Desktop\TokenPay-Website\frontend"
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
        print(f"  {out[:500]}")
    if show and err and 'warning' not in err.lower():
        print(f"  STDERR: {err[:300]}")
    return out

def make_tar(paths, arcname_map):
    """Create in-memory tar.gz from files/dirs"""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='w:gz') as tar:
        for src, dst in arcname_map.items():
            tar.add(src, arcname=dst)
    buf.seek(0)
    return buf

def main():
    print("=" * 60)
    print("  DEPLOY: Enterprise Errors + ZH Language + SDK v3 + Geo")
    print("=" * 60)

    # 1. Create backend tarball
    print("\n[1/6] Creating backend tarball...")
    backend_tar = make_tar({}, {
        os.path.join(BACKEND, 'server.js'): 'backend/server.js',
        os.path.join(BACKEND, 'email-service.js'): 'backend/email-service.js',
        os.path.join(BACKEND, 'package.json'): 'backend/package.json',
    })
    print("  Backend tar created")

    # 2. Create frontend SDK tarball
    print("\n[2/6] Creating frontend tarball...")
    frontend_tar_buf = io.BytesIO()
    with tarfile.open(fileobj=frontend_tar_buf, mode='w:gz') as tar:
        tar.add(os.path.join(FRONTEND, 'sdk', 'tokenpay-auth.js'), arcname='frontend/sdk/tokenpay-auth.js')
        tar.add(os.path.join(FRONTEND, 'script.js'), arcname='frontend/script.js')
    frontend_tar_buf.seek(0)
    print("  Frontend tar created")

    # 3. Upload backend
    print("\n[3/6] Uploading backend...")
    c = new_client()
    sftp = c.open_sftp()
    sftp.putfo(backend_tar, '/root/tokenpay-backend-update.tar.gz')
    print("  Uploaded backend tarball")

    # Extract backend into server dir
    run(c, 'cd /root/tokenpay-id && tar xzf /root/tokenpay-backend-update.tar.gz --overwrite')
    print("  Backend extracted")
    sftp.close()
    c.close()

    # 4. Upload frontend
    print("\n[4/6] Uploading frontend...")
    c = new_client()
    sftp = c.open_sftp()
    sftp.putfo(frontend_tar_buf, '/root/tokenpay-frontend-update.tar.gz')
    print("  Uploaded frontend tarball")

    # Extract frontend
    run(c, 'cd /root/tokenpay-id && tar xzf /root/tokenpay-frontend-update.tar.gz --overwrite')
    print("  Frontend extracted")
    sftp.close()
    c.close()

    # 5. Rebuild backend container
    print("\n[5/6] Rebuilding backend container...")
    c = new_client()
    run(c, 'cd /root/tokenpay-id && docker-compose up -d --build api 2>&1 | tail -20')
    time.sleep(8)

    # Check container health
    out = run(c, 'docker ps --filter name=tokenpay-id-api --format "{{.Status}}"')
    print(f"  API container: {out}")
    c.close()

    # Reload nginx to pick up new frontend files
    print("\n[6/6] Reloading nginx...")
    c = new_client()
    run(c, 'docker exec tokenpay-id-nginx nginx -s reload 2>/dev/null || docker-compose -f /root/tokenpay-id/docker-compose.yml restart nginx')
    time.sleep(3)
    out = run(c, 'docker ps --filter name=tokenpay-id-nginx --format "{{.Status}}"')
    print(f"  Nginx container: {out}")
    c.close()

    # 7. Verify
    print("\n" + "=" * 60)
    print("  VERIFICATION")
    print("=" * 60)
    c = new_client()

    # Test preferences endpoint
    print("\n  Testing /client/preferences...")
    out = run(c, 'curl -s http://localhost:8080/api/v1/client/preferences')
    print(f"  Preferences: {out[:200]}")

    # Test enterprise errors endpoint (should require auth)
    print("\n  Testing /enterprise/errors (no auth)...")
    out = run(c, 'curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/api/v1/enterprise/errors')
    print(f"  Status: {out} (expect 401)")

    # Test health
    print("\n  Testing /health...")
    out = run(c, 'curl -s http://localhost:8080/health')
    print(f"  Health: {out}")

    # Check SDK version
    print("\n  Testing /sdk/version...")
    out = run(c, 'curl -s http://localhost:8080/api/v1/sdk/version')
    print(f"  SDK version: {out[:200]}")

    c.close()

    print("\n" + "=" * 60)
    print("  DEPLOYMENT COMPLETE")
    print("=" * 60)
    print("""
  Changes deployed:
  1. Enterprise error logging system (POST /enterprise/errors, /enterprise/health)
  2. Chinese (ZH) language support (backend + frontend + email templates)
  3. IP geolocation for auto language detection (/client/preferences)
  4. SDK v3.0 button redesign (5 variants: default/filled/outline/minimal/icon)
  5. Frontend 3-way language toggle (RU → EN → 中文)
  6. Enterprise error email alerts to info@tokenpay.space
    """)

if __name__ == '__main__':
    main()
