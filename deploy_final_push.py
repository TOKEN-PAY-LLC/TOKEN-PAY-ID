#!/usr/bin/env python3
"""Final push: upload updated server.js to Docker API container and restart."""
import paramiko
import os

BASE = os.path.dirname(os.path.abspath(__file__))
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("5.23.54.205", username="root", password="vE^6t-zFS3dpNT", timeout=15)
sftp = ssh.open_sftp()

# Upload
local = os.path.join(BASE, "backend", "server.js")
print(f"Uploading server.js ({os.path.getsize(local):,} bytes)...")
sftp.put(local, "/tmp/server.js")
sftp.close()

cmds = [
    "docker cp /tmp/server.js tokenpay-id-api:/app/server.js",
    "cp /tmp/server.js /root/tokenpay-id/backend/server.js",
    "docker restart tokenpay-id-api",
    "sleep 5",
    "docker ps --format '{{.Names}} {{.Status}}' | grep api",
    # Verify all endpoints
    "curl -sk https://tokenpay.space/.well-known/security.txt 2>/dev/null | head -3",
    "curl -sk https://tokenpay.space/.well-known/openid-configuration 2>/dev/null | python3 -c \"import sys,json; d=json.load(sys.stdin); print('pkce_required:', d.get('pkce_required')); print('registration:', d.get('registration_endpoint')); print('ccm:', d.get('code_challenge_methods_supported'))\"",
]

for cmd in cmds:
    print(f"$ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out:
        for line in out.split('\n')[:10]:
            print(f"  {line}")
    if err and "warn" not in err.lower():
        for line in err.split('\n')[:3]:
            if line.strip():
                print(f"  [err] {line}")
    print()

ssh.close()
print("=== Done ===")
