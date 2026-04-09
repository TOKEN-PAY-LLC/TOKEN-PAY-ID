#!/usr/bin/env python3
"""Fix: install missing deps, check .env, restart properly."""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("5.23.54.205", username="root", password="vE^6t-zFS3dpNT", timeout=15)

cmds = [
    # Install missing dependency
    "cd /var/www/backend && npm install cookie-parser --save 2>&1 | tail -5",
    # Check .env for DB config
    "cat /var/www/backend/.env 2>/dev/null || echo 'NO .env FILE'",
    # Check if package.json exists
    "cat /var/www/backend/package.json 2>/dev/null | head -20",
    # List node_modules to see what's installed
    "ls /var/www/backend/node_modules/ 2>/dev/null | head -20",
    # Check env vars from PM2
    "pm2 env 0 2>/dev/null | grep -E 'DB_|JWT_|PORT|NODE_ENV' | head -10",
]

for cmd in cmds:
    print(f"$ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out:
        for line in out.split('\n')[:20]:
            print(f"  {line}")
    if err and "warn" not in err.lower():
        for line in err.split('\n')[:5]:
            print(f"  [err] {line}")
    print()

ssh.close()
print("Done checking.")
