#!/usr/bin/env python3
"""Hard restart nginx: kill all processes, start fresh."""
import paramiko
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("5.23.54.205", username="root", password="vE^6t-zFS3dpNT", timeout=15)

cmds = [
    # 1. Kill ALL nginx processes
    "pkill -9 nginx; sleep 1; echo 'killed all nginx'",
    # 2. Verify nothing on 80/443
    "ss -tlnp | grep -E ':80 |:443 ' || echo 'ports free'",
    # 3. Start nginx fresh
    "nginx 2>&1 || echo 'nginx start failed'",
    # 4. Wait for startup
    "sleep 2",
    # 5. Verify nginx is running
    "ps aux | grep 'nginx' | grep -v grep | head -3",
    # 6. Test through nginx 443
    "curl -sk -H 'Host: tokenpay.space' https://127.0.0.1:443/.well-known/openid-configuration 2>/dev/null | python3 -c \"import sys,json; d=json.load(sys.stdin); print('NGINX 443 pkce_required:', d.get('pkce_required')); print('NGINX 443 registration:', d.get('registration_endpoint')); print('NGINX 443 ccm:', d.get('code_challenge_methods_supported'))\"",
    # 7. Test direct backend
    "curl -s http://127.0.0.1:8080/.well-known/openid-configuration | python3 -c \"import sys,json; d=json.load(sys.stdin); print('BACKEND pkce_required:', d.get('pkce_required')); print('BACKEND registration:', d.get('registration_endpoint'))\"",
    # 8. Test through nginx 80
    "curl -s -H 'Host: tokenpay.space' http://127.0.0.1:80/.well-known/openid-configuration 2>/dev/null | head -c 200 || echo 'port 80 returned redirect or error'",
    # 9. Test public URL
    "curl -s https://tokenpay.space/.well-known/openid-configuration 2>/dev/null | python3 -c \"import sys,json; d=json.load(sys.stdin); print('PUBLIC pkce_required:', d.get('pkce_required')); print('PUBLIC ccm:', d.get('code_challenge_methods_supported'))\" 2>/dev/null || echo 'public URL failed'",
]

for cmd in cmds:
    print(f"$ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=20)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out:
        for line in out.split('\n')[:10]:
            print(f"  {line}")
    if err:
        for line in err.split('\n')[:5]:
            if line.strip():
                print(f"  [err] {line}")
    print()

ssh.close()
print("=== Done ===")
