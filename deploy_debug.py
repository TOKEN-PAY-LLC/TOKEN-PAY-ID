#!/usr/bin/env python3
"""Debug: check actual file content and PM2 logs on server."""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("5.23.54.205", username="root", password="vE^6t-zFS3dpNT", timeout=15)

cmds = [
    # Check file timestamp and size
    "ls -la /var/www/backend/server.js",
    # Search for our new code in the deployed file
    "grep -n 'registration_endpoint' /var/www/backend/server.js | head -5",
    "grep -n 'pkce_required' /var/www/backend/server.js | head -5",
    "grep -n 'incrementSessionVersion' /var/www/backend/server.js | head -3",
    "grep -n 'oauth/register' /var/www/backend/server.js | head -5",
    # Check PM2 logs for errors
    "pm2 logs tokenpay --lines 20 --nostream 2>&1",
    # Check what port the tokenpay process listens on
    "grep -n 'listen\\|PORT' /var/www/backend/server.js | head -5",
    # Check nginx config for proxying
    "grep -rn 'proxy_pass.*3000\\|proxy_pass.*3001\\|proxy_pass.*5000' /etc/nginx/ 2>/dev/null | head -5",
]

for cmd in cmds:
    print(f"$ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=10)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out:
        for line in out.split('\n')[:15]:
            print(f"  {line}")
    if err and "warn" not in err.lower():
        for line in err.split('\n')[:5]:
            print(f"  [err] {line}")
    print()

ssh.close()
