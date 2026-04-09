#!/usr/bin/env python3
"""Check docs from inside nginx vs direct IP vs Cloudflare."""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("5.23.54.205", username="root", password="vE^6t-zFS3dpNT", timeout=15)

cmds = [
    # Direct from nginx container
    "docker exec tokenpay-id-nginx head -40 /usr/share/nginx/html/docs.html | grep -o 'v2\\.[0-9]'",
    # curl localhost inside server
    "curl -sk https://127.0.0.1/docs.html -H 'Host: tokenpay.space' 2>/dev/null | grep -o 'API Reference v[0-9.]*'",
    # curl without cloudflare
    "curl -sk https://5.23.54.205/docs.html -H 'Host: tokenpay.space' 2>/dev/null | grep -o 'API Reference v[0-9.]*'",
    # Check CF cache header
    "curl -sI 'https://tokenpay.space/docs.html' 2>/dev/null | grep -iE 'cf-cache|cache-control|age:'",
    # Check response from outside (full header)
    "curl -sI 'https://tokenpay.space/docs.html' 2>/dev/null | head -15",
]

for cmd in cmds:
    print(f"$ {cmd[:90]}{'...' if len(cmd)>90 else ''}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=15)
    out = stdout.read().decode().strip()
    if out:
        for line in out.split('\n')[:10]:
            print(f"  {line}")
    print()

ssh.close()
