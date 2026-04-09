#!/usr/bin/env python3
"""Purge Cloudflare cache and redeploy nginx config"""
import paramiko
import urllib.request
import urllib.error
import json
import ssl

CF_ZONE_ID = "210a25c077c2bfdc43a853762ccb358d"
CF_API_KEY = "5a4a5eddcb5882e068e0c407b670df0ef65ac"

SERVER = "5.23.54.205"
USER = "root"
PASSWORD = "vE^6t-zFS3dpNT"

def purge_cloudflare():
    print("[1/2] Purging Cloudflare cache...")
    url = f"https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/purge_cache"
    data = json.dumps({"purge_everything": True}).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Authorization", f"Bearer {CF_API_KEY}")
    req.add_header("Content-Type", "application/json")
    ctx = ssl.create_default_context()
    try:
        resp = urllib.request.urlopen(req, context=ctx)
        result = json.loads(resp.read())
        if result.get("success"):
            print("    Cache purged!")
        else:
            print(f"    Errors: {result.get('errors')}")
    except Exception as e:
        print(f"    Error: {e}")

def deploy_nginx():
    print("[2/2] Deploying fixed nginx config...")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(SERVER, port=22, username=USER, password=PASSWORD,
              timeout=120, banner_timeout=120, auth_timeout=120,
              allow_agent=False, look_for_keys=False)
    sftp = c.open_sftp()
    sftp.put("nginx/nginx.conf", "/root/tokenpay-id/nginx/nginx.conf")
    sftp.close()
    stdin, stdout, stderr = c.exec_command("docker restart tokenpay-id-nginx")
    stdout.channel.recv_exit_status()
    print(f"    Container restarted: {stdout.read().decode().strip()}")
    stdin, stdout, stderr = c.exec_command("docker exec tokenpay-id-nginx nginx -t 2>&1")
    stdout.channel.recv_exit_status()
    print(f"    Config test: {stdout.read().decode().strip()}")
    c.close()

if __name__ == "__main__":
    purge_cloudflare()
    deploy_nginx()
    print("\nDone!")
