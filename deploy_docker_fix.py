#!/usr/bin/env python3
"""Fix: Docker containers hold ports 80/443 with old code. Update them."""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("5.23.54.205", username="root", password="vE^6t-zFS3dpNT", timeout=15)

cmds = [
    # 1. List Docker containers
    "docker ps --format 'table {{.ID}}\t{{.Names}}\t{{.Image}}\t{{.Ports}}\t{{.Status}}'",
    # 2. Find which container uses ports 80/443
    "docker ps --format '{{.ID}} {{.Names}} {{.Ports}}' | grep -E '80|443'",
    # 3. Check container volumes/mounts
    "docker inspect $(docker ps -q) 2>/dev/null | python3 -c \"import sys,json; cs=json.load(sys.stdin); [print(c['Name'], [m['Source']+'->'+m['Destination'] for m in c.get('Mounts',[])]) for c in cs]\"",
    # 4. Check if /var/www/backend is mounted into Docker
    "docker inspect $(docker ps -q) 2>/dev/null | grep -A2 'Source.*backend'",
    # 5. Check the backend code inside Docker
    "docker exec $(docker ps -q | head -1) grep -c 'pkce_required' /var/www/backend/server.js 2>/dev/null || echo 'grep inside docker failed'",
    "docker exec $(docker ps -q | head -1) grep -c 'registration_endpoint' /var/www/backend/server.js 2>/dev/null || echo 'not found'",
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
        for line in err.split('\n')[:5]:
            if line.strip():
                print(f"  [err] {line}")
    print()

ssh.close()
