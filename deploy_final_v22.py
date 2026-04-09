#!/usr/bin/env python3
"""Final deploy: updated docs.html with sanitized placeholders."""
import paramiko, os

BASE = os.path.dirname(os.path.abspath(__file__))
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("5.23.54.205", username="root", password="vE^6t-zFS3dpNT", timeout=15)
sftp = ssh.open_sftp()

local = os.path.join(BASE, "frontend", "docs.html")
print(f"Upload docs.html ({os.path.getsize(local):,} bytes)")
sftp.put(local, "/tmp/docs.html")
sftp.close()

cmds = [
    "cp /tmp/docs.html /root/tokenpay-id/frontend/docs.html",
    "docker exec tokenpay-id-nginx nginx -s reload",
    # Verify no realistic-looking secret keys
    "grep -c '7f3a9b2ce4d18' /root/tokenpay-id/frontend/docs.html && echo 'FAIL: old placeholder found' || echo 'OK: no realistic keys'",
    # Verify docs served correctly
    "curl -skL 'https://tokenpay.space/docs' 2>/dev/null | grep -o 'API Reference v[0-9.]*'",
    "curl -skL 'https://tokenpay.space/docs' 2>/dev/null | grep -o 'PKCE обязателен'",
    # Health check
    "docker ps --format '{{.Names}} {{.Status}}' | grep -E 'api|nginx'",
]

for cmd in cmds:
    print(f"$ {cmd[:80]}{'...' if len(cmd)>80 else ''}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=15)
    out = stdout.read().decode().strip()
    if out:
        for line in out.split('\n')[:5]:
            print(f"  {line}")
    print()

ssh.close()
print("=== FINAL DEPLOY DONE ===")
