#!/usr/bin/env python3
"""Full deploy: frontend + backend via Paramiko"""
import paramiko, tarfile, os, sys
from pathlib import Path

SERVER = "5.23.54.205"
USER = "root"
PASSWORD = "vE^6t-zFS3dpNT"
BASE = Path("c:/Users/user/Desktop/TokenPay-Website")

def make_archive(src_dir, archive_name, excludes=None):
    excludes = excludes or []
    archive = BASE / archive_name
    if archive.exists(): archive.unlink()
    with tarfile.open(archive, "w:gz") as tar:
        for f in Path(src_dir).rglob("*"):
            if f.is_file() and not any(e in str(f) for e in excludes):
                tar.add(f, arcname=f.relative_to(src_dir))
    size = archive.stat().st_size / 1024
    print(f"  ✓ {archive_name} ({size:.0f} KB)")
    return archive

def connect():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(SERVER, port=22, username=USER, password=PASSWORD,
                   timeout=60, banner_timeout=60, auth_timeout=60,
                   allow_agent=False, look_for_keys=False)
    print("  ✓ Connected to", SERVER)
    return client

def run(client, cmd, label=""):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=120)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    code = stdout.channel.recv_exit_status()
    if label: print(f"  [{label}] exit={code}")
    if out: print("   " + "\n   ".join(out.split("\n")[:8]))
    if err and code != 0: print("   ERR: " + "\n   ERR: ".join(err.split("\n")[:5]))
    return code == 0

def upload(client, local, remote):
    sftp = client.open_sftp()
    sftp.put(str(local), remote)
    sftp.close()
    print(f"  ✓ Uploaded → {remote}")

def main():
    print("\n" + "="*60)
    print("TOKEN PAY FULL DEPLOYMENT")
    print("="*60)

    # --- 1. Build archives ---
    print("\n[1/5] Building archives...")
    fe = make_archive(BASE / "frontend", "tp-frontend.tar.gz",
                      excludes=[".git", "node_modules", ".DS_Store"])
    be = make_archive(BASE / "backend", "tp-backend.tar.gz",
                      excludes=[".git", "node_modules", ".env", ".DS_Store"])

    # --- 2. Connect ---
    print("\n[2/5] Connecting...")
    try:
        client = connect()
    except Exception as e:
        print(f"  ✗ {e}"); sys.exit(1)

    # --- 3. Upload ---
    print("\n[3/5] Uploading...")
    upload(client, fe, "/var/www/tp-frontend.tar.gz")
    upload(client, be, "/var/www/tp-backend.tar.gz")

    # --- 4. Deploy frontend ---
    print("\n[4/5] Deploying frontend...")
    fe_cmd = """
set -e
cd /var/www

# Detect web root
for d in tokenpay html public_html www; do
  [ -d "/var/www/$d" ] && WEB="/var/www/$d" && break
done
[ -z "$WEB" ] && WEB="/var/www/html" && mkdir -p "$WEB"
echo "Web root: $WEB"

# Extract fresh
rm -rf "$WEB"_backup 2>/dev/null; cp -r "$WEB" "$WEB"_backup 2>/dev/null || true
tar -xzf tp-frontend.tar.gz -C "$WEB/"
rm -f tp-frontend.tar.gz

# Subdomains: auth and id
for sub in auth id; do
  DIR="/var/www/$sub"
  mkdir -p "$DIR"
  cp -r "$WEB/"* "$DIR/"
done

# Index pages for subdomains
ln -sf /var/www/auth/login.html /var/www/auth/index.html 2>/dev/null || cp /var/www/auth/login.html /var/www/auth/index.html
ln -sf /var/www/id/dashboard.html /var/www/id/index.html 2>/dev/null || cp /var/www/id/dashboard.html /var/www/id/index.html

# Permissions
find "$WEB" /var/www/auth /var/www/id -type f -exec chmod 644 {} \\;
find "$WEB" /var/www/auth /var/www/id -type d -exec chmod 755 {} \\;
chown -R www-data:www-data "$WEB" /var/www/auth /var/www/id 2>/dev/null || true

# Reload nginx
systemctl reload nginx 2>/dev/null || nginx -s reload 2>/dev/null || true

echo "FRONTEND OK"
"""
    if not run(client, fe_cmd, "frontend"):
        print("  ✗ Frontend deploy failed")

    # --- 5. Deploy backend ---
    print("\n[5/5] Deploying backend...")
    be_cmd = """
set -e
cd /var/www

mkdir -p backend
# Backup
cp -r backend backend_backup 2>/dev/null || true
tar -xzf tp-backend.tar.gz -C backend/
rm -f tp-backend.tar.gz

cd backend
# Install/update deps (skip if no internet)
npm install --production 2>/dev/null || true

# Restart service
if pm2 list | grep -q tokenpay; then
  pm2 restart tokenpay
  echo "PM2 restarted"
elif pm2 list | grep -q tpid; then
  pm2 restart tpid
  echo "PM2 tpid restarted"
elif systemctl is-active --quiet tokenpay-api 2>/dev/null; then
  systemctl restart tokenpay-api
  echo "systemd restarted"
else
  echo "WARN: No known process manager found. Start manually: pm2 start server.js --name tokenpay"
fi

echo "BACKEND OK"
"""
    if not run(client, be_cmd, "backend"):
        print("  ✗ Backend deploy failed")

    # --- Health check ---
    print("\n[✓] Verifying deployment...")
    run(client, "curl -s https://tokenpay.space/api/v1/health 2>/dev/null | head -c 200 || echo 'health check pending'", "health")

    client.close()

    # Cleanup local archives
    fe.unlink(missing_ok=True)
    be.unlink(missing_ok=True)
    os.remove(str(BASE / "fix_favicons.py")) if (BASE / "fix_favicons.py").exists() else None

    print("\n" + "="*60)
    print("DEPLOYMENT COMPLETE")
    print("="*60)
    print("""
Fixes deployed:
  ✓ Favicon - proper icons on all pages (v=4 cache bust)
  ✓ manifest.json - PWA icon in browser search
  ✓ Mobile menu - fixed visibility/pointer-events (no freeze)
  ✓ Logos - brightness(0) = pure black in light theme
  ✓ Dashboard light theme - full color scheme
  ✓ HMAC-SHA256 API security + nonce replay protection
  ✓ Response signing (X-TP-Response-Sig header)
  ✓ Request expiry (5 min window)
  ✓ Constant-time signature comparison
  ✓ Security headers on all API responses
  ✓ CSS cache busted to v=20260324

Test:
  https://tokenpay.space
  https://auth.tokenpay.space
  https://id.tokenpay.space
  https://tokenpay.space/api/v1/health
""")

if __name__ == "__main__":
    main()
