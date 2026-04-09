#!/usr/bin/env python3
"""Compare response bodies from nginx 443 vs direct 8080."""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("5.23.54.205", username="root", password="vE^6t-zFS3dpNT", timeout=15)

cmds = [
    # Full body from nginx 443
    "curl -sk -H 'Host: tokenpay.space' https://127.0.0.1:443/.well-known/openid-configuration 2>/dev/null",
    # Full body from backend 8080
    "curl -s http://127.0.0.1:8080/.well-known/openid-configuration 2>/dev/null",
    # PM2 process info — is it still running?
    "pm2 pid tokenpay",
    "pm2 list --no-color 2>/dev/null | grep tokenpay",
    # Check if the file on disk matches our expectations
    "grep -c 'registration_endpoint' /var/www/backend/server.js",
    "grep -c 'pkce_required' /var/www/backend/server.js",
    # Kill all nginx workers and restart
    "kill -QUIT $(pgrep -o nginx) 2>/dev/null; sleep 1; nginx -g 'daemon off;' &disown; sleep 2; echo 'nginx restarted'",
    # Try again
    "curl -sk -H 'Host: tokenpay.space' https://127.0.0.1:443/.well-known/openid-configuration 2>/dev/null | python3 -c \"import sys,json; d=json.load(sys.stdin); print('AFTER RESTART - pkce:', d.get('pkce_required'), 'reg:', d.get('registration_endpoint'))\" 2>/dev/null || echo 'nginx 443 test failed'",
]

for cmd in cmds:
    print(f"\n$ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=20)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out:
        for line in out.split('\n')[:20]:
            print(f"  {line}")
    if err:
        for line in err.split('\n')[:3]:
            if line.strip():
                print(f"  [err] {line}")

ssh.close()
