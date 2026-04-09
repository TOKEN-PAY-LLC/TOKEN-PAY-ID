#!/usr/bin/env python3
"""Recon: find bot code, VPN service, AI agent on the server."""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("5.23.54.205", username="root", password="vE^6t-zFS3dpNT", timeout=15)

cmds = [
    # Find all project directories
    "ls /root/",
    # Find bot-related code
    "find /root -maxdepth 3 -name '*bot*' -o -name '*telegram*' -o -name '*tg*' 2>/dev/null | head -20",
    # Find VPN-related code
    "find /root -maxdepth 3 -name '*vpn*' -o -name '*cupol*' -o -name '*stresand*' -o -name '*singbox*' -o -name '*sing-box*' -o -name '*streisand*' 2>/dev/null | head -20",
    # Find AI agent code
    "find /root -maxdepth 3 -name '*agent*' -o -name '*ai*' -o -name '*gpt*' -o -name '*llm*' 2>/dev/null | head -20",
    # Docker containers
    "docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}' 2>/dev/null",
    # PM2 processes
    "pm2 list --no-color 2>/dev/null | grep -E 'name|online|error'",
    # Check for docker-compose files
    "find /root -maxdepth 3 -name 'docker-compose*' 2>/dev/null",
    # Check systemd services
    "systemctl list-units --type=service --state=running 2>/dev/null | grep -iE 'bot|vpn|agent|cupol|tg|telegram' || echo 'no matching services'",
]

for cmd in cmds:
    print(f"$ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=15)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out:
        for line in out.split('\n')[:25]:
            print(f"  {line}")
    if err:
        for line in err.split('\n')[:3]:
            if line.strip():
                print(f"  [err] {line}")
    print()

ssh.close()
