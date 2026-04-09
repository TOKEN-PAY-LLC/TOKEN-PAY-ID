"""Verify DKIM in Cloudflare, add if missing. Uses Global API Key."""
import json, urllib.request, urllib.error, paramiko, sys

CF_KEY = "5a4a5eddcb5882e068e0c407b670df0ef65ac"
DOMAIN = "tokenpay.space"
DKIM_NAME = f"dkim._domainkey.{DOMAIN}"
DKIM_VALUE = "k=rsa;p=MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAz2WECPeWoZalnjADWVPYww+qobNGVp3BTd54s2NKmJB1IIqRgYjUZM+fu3umhwR7ulCaGQt5v6m9OABe9LHs/CAhuSlo+gd3aB06F1b4umz8QVGu8Mj6s/VkqpU5gWOKoSJaAioGiL7ykoX4T8+5nDxf0v7GYgfseSoKY5BwyQkrczsfyUR4ZI+vQUjBSyCdmkjBZtXum6JiXvxIho1sJieDstMMULe5tw7sn+xcRkEMnpha1SoLKcVyLLDau6Mmt67huq66bSC1/jkCxaU0aHE6JF2Tf0b4lG6iCCXhHA8rGKXSwU5jiTHjpxZtdsfZ5wDiSK6VN4iz2ZfQZZb4LQIDAQAB"

# Step 1: Check DNS via server
print("=== STEP 1: Check DNS propagation ===")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('5.23.54.205', username='root', password='vE^6t-zFS3dpNT', timeout=15)

for ns in ['8.8.8.8', '1.1.1.1', '9.9.9.9']:
    _, so, _ = ssh.exec_command(f"dig +short TXT dkim._domainkey.tokenpay.space @{ns} 2>/dev/null", timeout=10)
    r = so.read().decode().strip()
    status = "✓ FOUND" if r else "✗ missing"
    print(f"  DKIM @ {ns}: {status} {r[:80] if r else ''}")

_, so, _ = ssh.exec_command("dig +short TXT _dmarc.tokenpay.space @8.8.8.8 2>/dev/null", timeout=10)
r = so.read().decode().strip()
print(f"  DMARC @ 8.8.8.8: {'✓' if r else '✗'} {r}")

_, so, _ = ssh.exec_command("dig +short TXT tokenpay.space @8.8.8.8 2>/dev/null", timeout=10)
r = so.read().decode().strip()
print(f"  SPF @ 8.8.8.8: {'✓' if r else '✗'} {r}")
ssh.close()

# Step 2: Try Cloudflare API with Global Key (need email)
print("\n=== STEP 2: Cloudflare API check ===")

def cf_global(method, path, email, data=None):
    url = f"https://api.cloudflare.com/client/v4{path}"
    headers = {
        "X-Auth-Email": email,
        "X-Auth-Key": CF_KEY,
        "Content-Type": "application/json"
    }
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read()), None
    except urllib.error.HTTPError as e:
        return json.loads(e.read()), e.code

# Try common emails
emails_to_try = [
    "info@tokenpay.space",
    "ichernykh08@gmail.com",
    "grisha22822834@gmail.com",
]

zone_id = None
working_email = None
for email in emails_to_try:
    resp, err = cf_global("GET", f"/zones?name={DOMAIN}", email)
    if resp.get("success") and resp.get("result"):
        zone_id = resp["result"][0]["id"]
        working_email = email
        print(f"  ✓ Auth OK with email: {email}")
        print(f"  Zone ID: {zone_id}")
        break
    else:
        print(f"  ✗ {email}: {resp.get('errors', [{}])[0].get('message', 'failed')[:60]}")

if not zone_id:
    print("\n  Could not authenticate with Cloudflare API.")
    print("  Please provide your Cloudflare account email.")
    print(f"  API Key: {CF_KEY[:10]}...")
    sys.exit(1)

# Step 3: Check existing DNS records in Cloudflare
print("\n=== STEP 3: Current Cloudflare DNS records ===")
resp, _ = cf_global("GET", f"/zones/{zone_id}/dns_records?type=TXT&per_page=100", working_email)
txt_records = resp.get("result", [])
for r in txt_records:
    print(f"  {r['name']}: {r['content'][:80]}...")

# Step 4: Add or update DKIM
print("\n=== STEP 4: DKIM record ===")
dkim_existing = [r for r in txt_records if "dkim._domainkey" in r["name"]]
if dkim_existing:
    print(f"  DKIM already in CF: {dkim_existing[0]['content'][:80]}...")
    # Check if it matches
    if DKIM_VALUE[:50] in dkim_existing[0]['content']:
        print("  ✓ Correct value, no update needed")
    else:
        print("  Updating to correct value...")
        resp, err = cf_global("PUT", f"/zones/{zone_id}/dns_records/{dkim_existing[0]['id']}", working_email, {
            "type": "TXT", "name": DKIM_NAME, "content": DKIM_VALUE, "ttl": 3600
        })
        print(f"  {'✓ Updated' if resp.get('success') else '✗ Failed: ' + str(resp.get('errors'))}")
else:
    print("  DKIM not in Cloudflare yet — adding now...")
    resp, err = cf_global("POST", f"/zones/{zone_id}/dns_records", working_email, {
        "type": "TXT", "name": DKIM_NAME, "content": DKIM_VALUE, "ttl": 3600
    })
    if resp.get("success"):
        print(f"  ✓ DKIM added! ID: {resp['result']['id']}")
    else:
        print(f"  ✗ Failed: {resp.get('errors')}")

# Step 5: Check for conflicting DMARC
dmarc_existing = [r for r in txt_records if "_dmarc" in r["name"]]
print(f"\n=== STEP 5: DMARC records ({len(dmarc_existing)} found) ===")
for r in dmarc_existing:
    print(f"  {r['name']}: {r['content']}")

print("\n=== DONE ===")
print("Wait 1-5 min then run: dig +short TXT dkim._domainkey.tokenpay.space @8.8.8.8")
