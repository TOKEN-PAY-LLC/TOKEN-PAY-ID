#!/usr/bin/env python3
"""Check docs from correct URL and via localhost."""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("5.23.54.205", username="root", password="vE^6t-zFS3dpNT", timeout=15)

cmds = [
    # Follow redirects
    "curl -skL 'https://tokenpay.space/docs' 2>/dev/null | grep -o 'API Reference v[0-9.]*'",
    # Check nginx config for .html rewrite
    "docker exec tokenpay-id-nginx cat /etc/nginx/conf.d/default.conf | grep -A2 -E 'html|rewrite|try_files'",
    # Direct curl to localhost on port 443 
    "curl -sk 'https://localhost/docs.html' 2>/dev/null | grep -o 'API Reference v[0-9.]*'",
    "curl -sk 'https://localhost/docs' 2>/dev/null | grep -o 'API Reference v[0-9.]*'",
    # Check if PKCE callout appears in served docs
    "curl -skL 'https://tokenpay.space/docs' 2>/dev/null | grep -o 'PKCE обязателен'",
    # Verify QR login endpoint works correctly
    "curl -sk -X POST 'https://tokenpay.space/api/v1/auth/qr/login-init' -H 'Content-Type: application/json' 2>/dev/null",
]

for cmd in cmds:
    print(f"$ {cmd[:90]}{'...' if len(cmd)>90 else ''}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=15)
    out = stdout.read().decode().strip()
    if out:
        for line in out.split('\n')[:8]:
            print(f"  {line}")
    print()

ssh.close()
