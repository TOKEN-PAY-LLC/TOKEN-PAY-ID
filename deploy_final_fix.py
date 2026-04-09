#!/usr/bin/env python3
"""Fix nginx + purge Cloudflare cache."""
import paramiko
import urllib.request
import json

SERVER_IP = "5.23.54.205"
SERVER_PASS = "vE^6t-zFS3dpNT"
CF_ZONE_ID = "210a25c077c2bfdc43a853762ccb358d"
CF_API_KEY = "5a4a5eddcb5882e068e0c407b670df0ef65ac"

# Step 1: Fix nginx on server
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(SERVER_IP, username="root", password=SERVER_PASS, timeout=15)

cmds = [
    # Check nginx process
    "ps aux | grep nginx | grep -v grep",
    # Try to start nginx properly
    "systemctl start nginx 2>&1 || nginx 2>&1",
    "sleep 1",
    "ps aux | grep nginx | grep -v grep | head -3",
    # Direct localhost check (bypasses CF)
    "curl -s http://127.0.0.1:8080/.well-known/openid-configuration | python3 -c \"import sys,json; d=json.load(sys.stdin); print('LOCAL:', 'pkce_required=' + str(d.get('pkce_required')), 'reg=' + str(bool(d.get('registration_endpoint'))))\"",
]

print("=== Step 1: Fix nginx ===")
for cmd in cmds:
    print(f"$ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=15)
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

# Step 2: Purge Cloudflare cache
print("=== Step 2: Purge Cloudflare cache ===")
url = f"https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/purge_cache"
body = json.dumps({"purge_everything": True}).encode()
req = urllib.request.Request(url, data=body, method="POST")
req.add_header("Authorization", f"Bearer {CF_API_KEY}")
req.add_header("Content-Type", "application/json")

try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
        print(f"  Status: {resp.status}")
        print(f"  Success: {data.get('success')}")
        if data.get('errors'):
            print(f"  Errors: {data['errors']}")
except Exception as e:
    print(f"  CF purge error: {e}")
    try:
        err_body = e.read().decode() if hasattr(e, 'read') else str(e)
        print(f"  Details: {err_body[:300]}")
    except:
        pass

# Step 3: Verify via public URL (after CF purge)
print("\n=== Step 3: Verify public URL (after CF purge) ===")
import time
time.sleep(3)

try:
    req2 = urllib.request.Request(
        "https://tokenpay.space/.well-known/openid-configuration",
        headers={"Cache-Control": "no-cache"}
    )
    with urllib.request.urlopen(req2, timeout=15) as resp:
        d = json.loads(resp.read())
        print(f"  pkce_required: {d.get('pkce_required')}")
        print(f"  registration_endpoint: {d.get('registration_endpoint')}")
        print(f"  code_challenge_methods: {d.get('code_challenge_methods_supported')}")
        print(f"  client_info_endpoint: {d.get('client_info_endpoint')}")
except Exception as e:
    print(f"  Error: {e}")

print("\n=== Done ===")
