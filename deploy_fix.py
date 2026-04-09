#!/usr/bin/env python3
"""Fix: deploy server.js to the correct path and restart the right PM2 process."""
import paramiko
import os

SERVER_IP = "5.23.54.205"
SERVER_PASS = "vE^6t-zFS3dpNT"
BASE = os.path.dirname(os.path.abspath(__file__))

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
print(f"Connecting to {SERVER_IP}...")
ssh.connect(SERVER_IP, username="root", password=SERVER_PASS, timeout=15)
sftp = ssh.open_sftp()

# Upload server.js to the CORRECT path
local = os.path.join(BASE, "backend", "server.js")
remote = "/var/www/backend/server.js"
size = os.path.getsize(local)
print(f"Uploading server.js ({size:,} bytes) -> {remote}")
sftp.put(local, remote)
sftp.close()

# Restart the correct PM2 process
cmds = [
    "pm2 restart tokenpay",
    "sleep 2",
    "pm2 status",
    "curl -s https://tokenpay.space/.well-known/openid-configuration | python3 -c \"import sys,json; d=json.load(sys.stdin); print('pkce_required:', d.get('pkce_required')); print('registration_endpoint:', d.get('registration_endpoint')); print('code_challenge_methods:', d.get('code_challenge_methods_supported'))\"",
]

print("\nRestarting tokenpay process...")
for cmd in cmds:
    print(f"$ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=15)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out:
        print(out)
    if err and "warn" not in err.lower():
        print(f"[stderr] {err}")
    print()

ssh.close()
print("=== Done! ===")
