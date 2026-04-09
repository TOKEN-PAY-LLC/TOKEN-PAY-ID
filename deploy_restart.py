#!/usr/bin/env python3
"""Restart tokenpay and verify discovery endpoint."""
import paramiko
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("5.23.54.205", username="root", password="vE^6t-zFS3dpNT", timeout=15)

cmds = [
    "cd /var/www/backend && pm2 restart tokenpay --update-env",
    "sleep 3",
    "pm2 logs tokenpay --lines 10 --nostream 2>&1",
    "curl -s http://localhost:8080/.well-known/openid-configuration 2>/dev/null | python3 -c \"import sys,json; d=json.load(sys.stdin); print('pkce_required:', d.get('pkce_required')); print('registration_endpoint:', d.get('registration_endpoint')); print('code_challenge_methods:', d.get('code_challenge_methods_supported')); print('client_info_endpoint:', d.get('client_info_endpoint'))\"",
    "curl -s https://tokenpay.space/.well-known/openid-configuration 2>/dev/null | python3 -c \"import sys,json; d=json.load(sys.stdin); print('PROD pkce_required:', d.get('pkce_required')); print('PROD registration:', d.get('registration_endpoint')); print('PROD ccm:', d.get('code_challenge_methods_supported'))\"",
    "pm2 status",
]

for cmd in cmds:
    print(f"$ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=20)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out:
        for line in out.split('\n')[:20]:
            print(f"  {line}")
    if err:
        for line in err.split('\n')[:10]:
            if line.strip():
                print(f"  [err] {line}")
    print()

ssh.close()
print("=== Verification complete ===")
