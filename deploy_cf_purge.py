#!/usr/bin/env python3
"""Purge Cloudflare cache with correct auth + reload nginx."""
import paramiko
import urllib.request
import json
import time

CF_ZONE_ID = "210a25c077c2bfdc43a853762ccb358d"
CF_API_KEY = "5a4a5eddcb5882e068e0c407b670df0ef65ac"
CF_ACCOUNT_ID = "7b3dcd325574c3ca17e376b49d2875a9"

SERVER_IP = "5.23.54.205"
SERVER_PASS = "vE^6t-zFS3dpNT"

# Step 1: Reload nginx on server (send HUP signal to master)
print("=== Step 1: Reload nginx via signal ===")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(SERVER_IP, username="root", password=SERVER_PASS, timeout=15)

cmds = [
    # Reload nginx via HUP signal (since it runs with daemon off)
    "kill -HUP $(cat /var/run/nginx.pid 2>/dev/null || pgrep -o nginx) 2>/dev/null && echo 'nginx reloaded' || echo 'nginx HUP failed'",
    "sleep 1",
    # Verify local still works
    "curl -s http://127.0.0.1:8080/.well-known/openid-configuration | python3 -c \"import sys,json; d=json.load(sys.stdin); print('LOCAL pkce_required:', d.get('pkce_required'), 'reg:', bool(d.get('registration_endpoint')))\"",
]
for cmd in cmds:
    print(f"  $ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=15)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out: print(f"    {out}")
    if err and "warn" not in err.lower(): print(f"    [err] {err}")
ssh.close()

# Step 2: Try CF cache purge with multiple auth methods
print("\n=== Step 2: Purge Cloudflare cache ===")
url = f"https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/purge_cache"
body = json.dumps({"purge_everything": True}).encode()

# Try as Bearer token first, then as X-Auth-Key
auth_methods = [
    ("Bearer Token", {"Authorization": f"Bearer {CF_API_KEY}", "Content-Type": "application/json"}),
    ("Global API Key", {"X-Auth-Email": "info@tokenpay.space", "X-Auth-Key": CF_API_KEY, "Content-Type": "application/json"}),
]

for name, headers in auth_methods:
    print(f"  Trying {name}...")
    req = urllib.request.Request(url, data=body, method="POST", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            print(f"    Status: {resp.status}, Success: {data.get('success')}")
            if data.get("success"):
                print("    Cache purged!")
                break
    except Exception as e:
        err_msg = ""
        try:
            err_msg = e.read().decode()[:200] if hasattr(e, 'read') else str(e)
        except:
            err_msg = str(e)
        print(f"    Failed: {err_msg}")

# Step 3: Purge specific URLs as fallback
print("\n=== Step 3: Purge specific URLs ===")
purge_urls = [
    "https://tokenpay.space/.well-known/openid-configuration",
    "https://tokenpay.space/.well-known/security.txt",
    "https://tokenpay.space/oauth-consent.html",
]
body2 = json.dumps({"files": purge_urls}).encode()
for name, headers in auth_methods:
    req = urllib.request.Request(url, data=body2, method="POST", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            if data.get("success"):
                print(f"  URL purge success via {name}")
                break
    except:
        pass

# Step 4: Wait and verify
print("\n=== Step 4: Verify (waiting 5s for CF propagation) ===")
time.sleep(5)
try:
    req = urllib.request.Request(
        "https://tokenpay.space/.well-known/openid-configuration",
        headers={"Cache-Control": "no-cache", "Pragma": "no-cache"}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        d = json.loads(resp.read())
        print(f"  pkce_required: {d.get('pkce_required')}")
        print(f"  registration_endpoint: {d.get('registration_endpoint')}")
        print(f"  code_challenge_methods: {d.get('code_challenge_methods_supported')}")
        print(f"  client_info_endpoint: {d.get('client_info_endpoint')}")
        
        if d.get('pkce_required') == True:
            print("\n  >>> ALL GOOD! Production is up to date!")
        else:
            print("\n  >>> Still cached. CF cache may take a few minutes to propagate.")
            print("  >>> You can manually purge at: https://dash.cloudflare.com -> Caching -> Purge Everything")
except Exception as e:
    print(f"  Error: {e}")

print("\n=== Done ===")
