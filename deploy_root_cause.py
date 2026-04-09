#!/usr/bin/env python3
"""Find root cause: static file or nginx cache overriding backend."""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("5.23.54.205", username="root", password="vE^6t-zFS3dpNT", timeout=15)

cmds = [
    # Check if static .well-known files exist
    "find /var/www -name 'openid-configuration' 2>/dev/null",
    "find /var/www -path '*/.well-known/*' 2>/dev/null",
    # Check main nginx.conf for includes, caching, root directives
    "cat /etc/nginx/nginx.conf",
    # Verbose nginx 443 test — show full response with headers
    "curl -vsk -H 'Host: tokenpay.space' https://127.0.0.1:443/.well-known/openid-configuration 2>&1 | head -30",
    # Check if there's a try_files or root directive
    "grep -rn 'root\\|try_files\\|proxy_cache' /etc/nginx/ 2>/dev/null | grep -v '#'",
]

for cmd in cmds:
    print(f"$ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=15)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out:
        for line in out.split('\n')[:40]:
            print(f"  {line}")
    if err:
        for line in err.split('\n')[:5]:
            if line.strip():
                print(f"  [err] {line}")
    print()

ssh.close()
