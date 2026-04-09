#!/usr/bin/env python3
"""Deploy ALL: server.js + docs.html + oauth-consent.html to Docker containers."""
import paramiko
import os

BASE = os.path.dirname(os.path.abspath(__file__))
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("5.23.54.205", username="root", password="vE^6t-zFS3dpNT", timeout=15)
sftp = ssh.open_sftp()

# Upload files
files = {
    os.path.join(BASE, "backend", "server.js"): "/tmp/server.js",
    os.path.join(BASE, "frontend", "docs.html"): "/tmp/docs.html",
    os.path.join(BASE, "frontend", "oauth-consent.html"): "/tmp/oauth-consent.html",
    os.path.join(BASE, "frontend", "qr-login.html"): "/tmp/qr-login.html",
}

for local, remote in files.items():
    size = os.path.getsize(local)
    name = os.path.basename(local)
    print(f"  Upload {name} ({size:,} bytes)")
    sftp.put(local, remote)

sftp.close()

cmds = [
    # Backend: copy into Docker API container
    "docker cp /tmp/server.js tokenpay-id-api:/app/server.js",
    "cp /tmp/server.js /root/tokenpay-id/backend/server.js",
    # Frontend: copy into nginx container
    "docker cp /tmp/docs.html tokenpay-id-nginx:/usr/share/nginx/html/docs.html",
    "docker cp /tmp/oauth-consent.html tokenpay-id-nginx:/usr/share/nginx/html/oauth-consent.html",
    "docker cp /tmp/qr-login.html tokenpay-id-nginx:/usr/share/nginx/html/qr-login.html",
    # Also update host copies
    "cp /tmp/docs.html /root/tokenpay-id/frontend/docs.html",
    "cp /tmp/oauth-consent.html /root/tokenpay-id/frontend/oauth-consent.html",
    "cp /tmp/qr-login.html /root/tokenpay-id/frontend/qr-login.html",
    # Restart API container
    "docker restart tokenpay-id-api",
    "sleep 5",
    # Verify
    "docker ps --format '{{.Names}} {{.Status}}' | grep -E 'api|nginx'",
    # Test QR login-init
    "curl -sk -X POST https://tokenpay.space/api/v1/auth/qr/login-init -H 'Content-Type: application/json' 2>/dev/null | python3 -c \"import sys,json; d=json.load(sys.stdin); print('QR init:', 'OK sessionId=' + d.get('sessionId','?')[:8] + '...' if d.get('sessionId') else 'FAIL')\"",
    # Test TPID unlink blocked (should return 401 without auth, or 403 without admin)
    "curl -sk -X DELETE https://tokenpay.space/api/v1/users/connected-apps/test 2>/dev/null | head -1",
    # Test PKCE in discovery
    "curl -sk https://tokenpay.space/.well-known/openid-configuration 2>/dev/null | python3 -c \"import sys,json; d=json.load(sys.stdin); print('PKCE required:', d.get('pkce_required')); print('DCR:', d.get('registration_endpoint'))\"",
    # Test security.txt
    "curl -sk https://tokenpay.space/.well-known/security.txt 2>/dev/null | head -1",
    # Test docs version
    "curl -sk https://tokenpay.space/docs.html 2>/dev/null | grep -o 'API Reference v[0-9.]*'",
]

for cmd in cmds:
    print(f"$ {cmd[:80]}{'...' if len(cmd) > 80 else ''}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out:
        for line in out.split('\n')[:5]:
            print(f"  {line}")
    if err and 'warn' not in err.lower():
        for line in err.split('\n')[:2]:
            if line.strip():
                print(f"  [err] {line}")
    print()

ssh.close()
print("=== DEPLOY COMPLETE ===")
