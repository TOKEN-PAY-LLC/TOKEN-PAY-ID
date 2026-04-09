#!/usr/bin/env python3
"""Verify: check nginx mounts and that updated files are served."""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("5.23.54.205", username="root", password="vE^6t-zFS3dpNT", timeout=15)

cmds = [
    # Check nginx volume mount
    "docker inspect tokenpay-id-nginx --format '{{range .Mounts}}{{.Source}} -> {{.Destination}} ({{.Mode}}){{println}}{{end}}'",
    # Check if the docs.html on host has our changes
    "grep -o 'API Reference v[0-9.]*' /root/tokenpay-id/frontend/docs.html",
    # Check if nginx sees the updated file
    "docker exec tokenpay-id-nginx grep -o 'API Reference v[0-9.]*' /usr/share/nginx/html/docs.html 2>/dev/null || echo 'not found in container'",
    # Reload nginx to pick up file changes
    "docker exec tokenpay-id-nginx nginx -s reload 2>/dev/null && echo 'nginx reloaded' || echo 'reload failed'",
    # Test from inside nginx container
    "docker exec tokenpay-id-nginx cat /usr/share/nginx/html/docs.html 2>/dev/null | grep -o 'API Reference v[0-9.]*' || echo 'grep failed'",
    # Public check
    "curl -sk 'https://tokenpay.space/docs.html' 2>/dev/null | grep -o 'API Reference v[0-9.]*' || echo 'no match'",
    # Check QR login fix via confirm endpoint (should need auth)
    "curl -sk -X POST 'https://tokenpay.space/api/v1/auth/qr/login-confirm/fake-session' -H 'Content-Type: application/json' 2>/dev/null",
]

for cmd in cmds:
    print(f"$ {cmd[:90]}{'...' if len(cmd)>90 else ''}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=15)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out:
        for line in out.split('\n')[:5]:
            print(f"  {line}")
    if err:
        for line in err.split('\n')[:2]:
            if line.strip():
                print(f"  [err] {line}")
    print()

ssh.close()
