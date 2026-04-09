#!/usr/bin/env python3
"""Trace: check if CF or nginx is caching, and bypass."""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("5.23.54.205", username="root", password="vE^6t-zFS3dpNT", timeout=15)

cmds = [
    # Check what port 80 returns (no CF, no SSL)
    "curl -sH 'Host: tokenpay.space' http://127.0.0.1:80/.well-known/openid-configuration | python3 -c \"import sys,json; d=json.load(sys.stdin); print('NGINX(80) pkce:', d.get('pkce_required'), 'reg:', bool(d.get('registration_endpoint')))\"",
    # Check what port 443 returns (self-signed, no CF)
    "curl -skH 'Host: tokenpay.space' https://127.0.0.1:443/.well-known/openid-configuration | python3 -c \"import sys,json; d=json.load(sys.stdin); print('NGINX(443) pkce:', d.get('pkce_required'), 'reg:', bool(d.get('registration_endpoint')))\"",
    # Check full response headers from port 80 for caching
    "curl -sI -H 'Host: tokenpay.space' http://127.0.0.1:80/.well-known/openid-configuration",
    # Check what DNS resolves to from server
    "dig +short tokenpay.space A 2>/dev/null || nslookup tokenpay.space 2>/dev/null | grep Address | tail -1",
    # Direct via port 8080 (backend) - response headers
    "curl -sI http://127.0.0.1:8080/.well-known/openid-configuration",
]

for cmd in cmds:
    print(f"$ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=15)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out:
        for line in out.split('\n')[:15]:
            print(f"  {line}")
    if err:
        for line in err.split('\n')[:3]:
            if line.strip():
                print(f"  [err] {line}")
    print()

ssh.close()
