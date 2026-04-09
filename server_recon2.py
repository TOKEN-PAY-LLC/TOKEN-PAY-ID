#!/usr/bin/env python3
"""Deep recon: find ALL Python/JS projects, Telegram bots, VPN panels on server."""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("5.23.54.205", username="root", password="vE^6t-zFS3dpNT", timeout=15)

cmds = [
    "find / -maxdepth 4 -name '*.py' -not -path '*/site-packages/*' -not -path '*/lib/*' -not -path '*/node_modules/*' 2>/dev/null | head -30",
    "find / -maxdepth 4 -name 'package.json' -not -path '*/node_modules/*' 2>/dev/null | head -20",
    "find / -maxdepth 4 -name '*.env' -not -path '*/node_modules/*' 2>/dev/null | head -20",
    "docker images --format '{{.Repository}}:{{.Tag}} {{.Size}}'",
    "cat /root/tokenpay-id/docker-compose.yml",
    # Look for any cron jobs that might run bots
    "crontab -l 2>/dev/null || echo 'no crontab'",
    # Look for screen/tmux sessions
    "screen -ls 2>/dev/null || echo 'no screen'",
    "tmux ls 2>/dev/null || echo 'no tmux'",
    # Check if there are other servers/VPSes referenced
    "grep -r 'cupol' /root/tokenpay-id/backend/server.js 2>/dev/null | head -5",
    # Look for Telegram bot tokens
    "grep -r 'BOT_TOKEN\\|TELEGRAM_TOKEN\\|telegram.*bot' /root/ --include='*.env' --include='*.js' --include='*.py' --include='*.yml' 2>/dev/null | grep -v node_modules | head -10",
]

for cmd in cmds:
    print(f"$ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=15)
    out = stdout.read().decode().strip()
    if out:
        for line in out.split('\n')[:30]:
            print(f"  {line}")
    print()

ssh.close()
