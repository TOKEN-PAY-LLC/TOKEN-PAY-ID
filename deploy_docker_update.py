#!/usr/bin/env python3
"""Copy updated files into Docker containers and restart."""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("5.23.54.205", username="root", password="vE^6t-zFS3dpNT", timeout=15)

cmds = [
    # 1. Find where the backend code lives inside the API container
    "docker exec tokenpay-id-api find / -name 'server.js' -maxdepth 4 2>/dev/null | head -5",
    "docker exec tokenpay-id-api ls /app/ 2>/dev/null || docker exec tokenpay-id-api ls /usr/src/app/ 2>/dev/null || echo 'checking other paths'",
    "docker exec tokenpay-id-api pwd 2>/dev/null",
    "docker exec tokenpay-id-api cat /app/package.json 2>/dev/null | head -5 || docker exec tokenpay-id-api cat /usr/src/app/package.json 2>/dev/null | head -5",

    # 2. Check nginx config inside the nginx container
    "docker exec tokenpay-id-nginx cat /etc/nginx/conf.d/default.conf 2>/dev/null",

    # 3. Check what frontend files the nginx container serves
    "docker exec tokenpay-id-nginx ls /usr/share/nginx/html/ 2>/dev/null | head -20",

    # 4. Check the source dir on host that's mounted
    "ls /root/tokenpay-id/ 2>/dev/null",
    "ls /root/tokenpay-id/frontend/ 2>/dev/null | head -10",
]

for cmd in cmds:
    print(f"$ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=15)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out:
        for line in out.split('\n')[:25]:
            print(f"  {line}")
    if err:
        for line in err.split('\n')[:3]:
            if line.strip():
                print(f"  [err] {line}")
    print()

ssh.close()
