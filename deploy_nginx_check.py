#!/usr/bin/env python3
"""Check nginx proxy config to find why HTTPS returns old data."""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("5.23.54.205", username="root", password="vE^6t-zFS3dpNT", timeout=15)

cmds = [
    # Find all nginx proxy_pass directives
    "grep -rn 'proxy_pass' /etc/nginx/ 2>/dev/null",
    # Find tokenpay.space server block
    "grep -rn 'server_name.*tokenpay' /etc/nginx/ 2>/dev/null",
    # Check which config files exist
    "ls -la /etc/nginx/sites-enabled/ 2>/dev/null || ls -la /etc/nginx/conf.d/ 2>/dev/null",
    # Show the main tokenpay config
    "cat /etc/nginx/sites-enabled/tokenpay.space 2>/dev/null || cat /etc/nginx/conf.d/tokenpay.conf 2>/dev/null || echo 'NOT FOUND - checking all configs'",
    # Check if there's a second backend
    "ss -tlnp | grep -E '8080|3000|5000'",
    # Check if Cloudflare is caching
    "curl -sI https://tokenpay.space/.well-known/openid-configuration 2>/dev/null | grep -iE 'cf-|cache|server|x-proxy'",
]

for cmd in cmds:
    print(f"$ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=15)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out:
        for line in out.split('\n')[:30]:
            print(f"  {line}")
    if err:
        for line in err.split('\n')[:5]:
            if line.strip():
                print(f"  [err] {line}")
    print()

ssh.close()
