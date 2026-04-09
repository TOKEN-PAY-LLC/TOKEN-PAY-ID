#!/usr/bin/env python3
"""Deploy updated login.html with goqr.me QR code fix + verify."""
import paramiko, os

BASE = os.path.dirname(os.path.abspath(__file__))
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("5.23.54.205", username="root", password="vE^6t-zFS3dpNT", timeout=15)
sftp = ssh.open_sftp()

local = os.path.join(BASE, "frontend", "login.html")
print(f"Upload login.html ({os.path.getsize(local):,} bytes)")
sftp.put(local, "/tmp/login.html")
sftp.close()

cmds = [
    "cp /tmp/login.html /root/tokenpay-id/frontend/login.html",
    "docker exec tokenpay-id-nginx nginx -s reload",
    # Verify goqr.me reference is in the served file
    "curl -skL 'https://tokenpay.space/login' 2>/dev/null | grep -o 'api.qrserver.com' | head -1",
    # Verify QR login-init still works
    "curl -sk -X POST 'https://tokenpay.space/api/v1/auth/qr/login-init' -H 'Content-Type: application/json' 2>/dev/null",
    # Verify container health
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
print("=== QR FIX DEPLOYED ===")
