#!/usr/bin/env python3
"""Fix: add .well-known location to nginx config inside Docker."""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("5.23.54.205", username="root", password="vE^6t-zFS3dpNT", timeout=15)

cmds = [
    # Read the current nginx config on host
    "cat /root/tokenpay-id/nginx/nginx.conf",
]

print("=== Reading nginx config ===")
for cmd in cmds:
    print(f"$ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=15)
    out = stdout.read().decode().strip()
    if out:
        for line in out.split('\n'):
            print(f"  {line}")
    print()

ssh.close()
