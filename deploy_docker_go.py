#!/usr/bin/env python3
"""Deploy into Docker containers: copy server.js + frontend files, restart API."""
import paramiko
import os

SERVER_IP = "5.23.54.205"
SERVER_PASS = "vE^6t-zFS3dpNT"
BASE = os.path.dirname(os.path.abspath(__file__))

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
print(f"Connecting to {SERVER_IP}...")
ssh.connect(SERVER_IP, username="root", password=SERVER_PASS, timeout=15)
sftp = ssh.open_sftp()

# Step 1: Upload server.js to host (staging area)
local_server = os.path.join(BASE, "backend", "server.js")
staging = "/tmp/server.js"
print(f"\n[1] Uploading server.js ({os.path.getsize(local_server):,} bytes) to staging...")
sftp.put(local_server, staging)

# Step 2: Upload frontend files to /root/tokenpay-id/frontend/
frontend_files = [
    ("frontend/oauth-consent.html", "/root/tokenpay-id/frontend/oauth-consent.html"),
]
print("[2] Uploading frontend files...")
for local_rel, remote in frontend_files:
    local_path = os.path.join(BASE, local_rel.replace("/", os.sep))
    if os.path.exists(local_path):
        print(f"    {local_rel} -> {remote}")
        sftp.put(local_path, remote)

# Create .well-known dir and upload security.txt
security_local = os.path.join(BASE, "frontend", ".well-known", "security.txt")
if os.path.exists(security_local):
    print("    .well-known/security.txt -> /root/tokenpay-id/frontend/.well-known/security.txt")
    ssh.exec_command("mkdir -p /root/tokenpay-id/frontend/.well-known")[1].read()
    sftp.put(security_local, "/root/tokenpay-id/frontend/.well-known/security.txt")

sftp.close()

# Step 3: Copy server.js into Docker API container + install deps + restart
print("\n[3] Updating Docker API container...")
cmds = [
    # Copy server.js into container
    "docker cp /tmp/server.js tokenpay-id-api:/app/server.js",
    # Install cookie-parser inside container
    "docker exec tokenpay-id-api npm install cookie-parser --save 2>&1 | tail -3",
    # Also copy to the host backend dir for docker-compose rebuild
    "cp /tmp/server.js /root/tokenpay-id/backend/server.js",
    # Restart the API container
    "docker restart tokenpay-id-api",
    # Wait for healthy
    "sleep 5",
    # Check health
    "docker ps --format '{{.Names}} {{.Status}}' | grep api",
    # Verify inside container
    "docker exec tokenpay-id-api grep -c 'pkce_required' /app/server.js",
    "docker exec tokenpay-id-api grep -c 'registration_endpoint' /app/server.js",
]

for cmd in cmds:
    print(f"  $ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out:
        for line in out.split('\n')[:10]:
            print(f"    {line}")
    if err:
        for line in err.split('\n')[:3]:
            if line.strip():
                print(f"    [err] {line}")

# Step 4: Restart nginx container to pick up new frontend files
print("\n[4] Restarting nginx container...")
cmds2 = [
    "docker restart tokenpay-id-nginx",
    "sleep 3",
    "docker ps --format '{{.Names}} {{.Status}}'",
]
for cmd in cmds2:
    print(f"  $ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=20)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out:
        for line in out.split('\n')[:5]:
            print(f"    {line}")

# Step 5: Verify through HTTPS
print("\n[5] Verifying production endpoints...")
verify_cmds = [
    "curl -sk https://tokenpay.space/.well-known/openid-configuration 2>/dev/null | python3 -c \"import sys,json; d=json.load(sys.stdin); print('pkce_required:', d.get('pkce_required')); print('registration_endpoint:', d.get('registration_endpoint')); print('code_challenge_methods:', d.get('code_challenge_methods_supported')); print('client_info_endpoint:', d.get('client_info_endpoint'))\"",
    "curl -sk https://tokenpay.space/.well-known/security.txt 2>/dev/null | head -3",
    "curl -sk -o /dev/null -w '%{http_code}' https://tokenpay.space/api/v1/oauth/client-info/test 2>/dev/null",
]
for cmd in verify_cmds:
    print(f"  $ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=15)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out:
        for line in out.split('\n')[:10]:
            print(f"    {line}")

ssh.close()
print("\n=== Deployment to Docker complete! ===")
