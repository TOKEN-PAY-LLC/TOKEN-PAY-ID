#!/usr/bin/env python3
import urllib.request, json, ssl

CF_ZONE_ID = "210a25c077c2bfdc43a853762ccb358d"
CF_API_KEY = "5a4a5eddcb5882e068e0c407b670df0ef65ac"

url = f"https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/purge_cache"
data = json.dumps({"purge_everything": True}).encode()

req = urllib.request.Request(url, data=data, method="POST")
req.add_header("X-Auth-Email", "info@tokenpay.space")
req.add_header("X-Auth-Key", CF_API_KEY)
req.add_header("Content-Type", "application/json")

ctx = ssl.create_default_context()
try:
    resp = urllib.request.urlopen(req, context=ctx)
    result = json.loads(resp.read())
    if result.get("success"):
        print("Cache purged successfully!")
    else:
        errors = result.get("errors", [])
        print(f"Failed: {errors}")
except urllib.error.HTTPError as e:
    body = e.read().decode()
    print(f"HTTP {e.code}: {body[:300]}")
except Exception as e:
    print(f"Error: {e}")
