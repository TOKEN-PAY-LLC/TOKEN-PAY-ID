#!/usr/bin/env python3
"""Read nginx configs and purge Cloudflare cache."""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("5.23.54.205", username="root", password="vE^6t-zFS3dpNT", timeout=15)

cmds = [
    "cat /etc/nginx/sites-enabled/tokenpay",
    "cat /etc/nginx/conf.d/tokenpay-api.conf",
    # Reload nginx to be sure
    "nginx -t && systemctl reload nginx",
    # Wait and re-check
    "sleep 2 && curl -sH 'Cache-Control: no-cache' https://tokenpay.space/.well-known/openid-configuration 2>/dev/null | python3 -c \"import sys,json; d=json.load(sys.stdin); print('pkce_required:', d.get('pkce_required')); print('registration:', d.get('registration_endpoint')); print('ccm:', d.get('code_challenge_methods_supported'))\"",
]

for cmd in cmds:
    print(f"$ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=15)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out:
        for line in out.split('\n'):
            print(f"  {line}")
    if err:
        for line in err.split('\n')[:5]:
            if line.strip():
                print(f"  [err] {line}")
    print()

ssh.close()
