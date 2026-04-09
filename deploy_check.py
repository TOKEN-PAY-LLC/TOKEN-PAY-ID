#!/usr/bin/env python3
"""Check which PM2 process serves the API and fix deployment."""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("5.23.54.205", username="root", password="vE^6t-zFS3dpNT", timeout=15)

cmds = [
    "pm2 list",
    "pm2 show tokenpay 2>/dev/null | grep -E 'script path|cwd|exec'",
    "pm2 show server 2>/dev/null | grep -E 'script path|cwd|exec'",
    "ls -la /root/tokenpay-backend/server.js",
    "find /root -name 'server.js' -maxdepth 3 2>/dev/null",
    "cat /root/tokenpay-backend/package.json 2>/dev/null | head -5",
]

for cmd in cmds:
    print(f"$ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=10)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out:
        print(out)
    if err:
        print(f"[err] {err}")
    print()

ssh.close()
