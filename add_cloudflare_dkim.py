"""
Add DKIM record to Cloudflare DNS for tokenpay.space.
Run this with your Cloudflare API token.
Usage: python add_cloudflare_dkim.py <CF_API_TOKEN>
"""
import sys, json, urllib.request, urllib.error

if len(sys.argv) < 2:
    print("Usage: python add_cloudflare_dkim.py <CLOUDFLARE_API_TOKEN>")
    print("\nGet your token: Cloudflare Dashboard → My Profile → API Tokens → Create Token")
    print("Permissions needed: Zone > DNS > Edit")
    sys.exit(1)

TOKEN = sys.argv[1]
DOMAIN = "tokenpay.space"

DKIM_RECORD = {
    "type": "TXT",
    "name": "dkim._domainkey",
    "content": "k=rsa;p=MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAz2WECPeWoZalnjADWVPYww+qobNGVp3BTd54s2NKmJB1IIqRgYjUZM+fu3umhwR7ulCaGQt5v6m9OABe9LHs/CAhuSlo+gd3aB06F1b4umz8QVGu8Mj6s/VkqpU5gWOKoSJaAioGiL7ykoX4T8+5nDxf0v7GYgfseSoKY5BwyQkrczsfyUR4ZI+vQUjBSyCdmkjBZtXum6JiXvxIho1sJieDstMMULe5tw7sn+xcRkEMnpha1SoLKcVyLLDau6Mmt67huq66bSC1/jkCxaU0aHE6JF2Tf0b4lG6iCCXhHA8rGKXSwU5jiTHjpxZtdsfZ5wDiSK6VN4iz2ZfQZZb4LQIDAQAB",
    "ttl": 3600,
    "comment": "Timeweb DKIM key for email delivery"
}

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

def cf_request(method, path, data=None):
    url = f"https://api.cloudflare.com/client/v4{path}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=HEADERS, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return json.loads(e.read())

print(f"Looking up zone for {DOMAIN}...")
zones = cf_request("GET", f"/zones?name={DOMAIN}&status=active")
if not zones.get("result"):
    print("ERROR: Zone not found. Check your API token permissions.")
    sys.exit(1)

zone_id = zones["result"][0]["id"]
print(f"Zone ID: {zone_id}")

# Check if DKIM record already exists
existing = cf_request("GET", f"/zones/{zone_id}/dns_records?type=TXT&name=dkim._domainkey.{DOMAIN}")
if existing.get("result"):
    print(f"DKIM record already exists: {existing['result'][0]['id']}")
    print("Updating existing record...")
    rec_id = existing["result"][0]["id"]
    result = cf_request("PUT", f"/zones/{zone_id}/dns_records/{rec_id}", {**DKIM_RECORD, "name": f"dkim._domainkey.{DOMAIN}"})
else:
    print("Creating new DKIM record...")
    result = cf_request("POST", f"/zones/{zone_id}/dns_records", {**DKIM_RECORD, "name": f"dkim._domainkey.{DOMAIN}"})

if result.get("success"):
    print(f"\n✓ DKIM record {'updated' if existing.get('result') else 'created'} successfully!")
    rec = result["result"]
    print(f"  Name: {rec['name']}")
    print(f"  Type: {rec['type']}")
    print(f"  Content: {rec['content'][:80]}...")
    print(f"\nDNS propagation takes 1-15 minutes.")
    print("After that, run: dig +short TXT dkim._domainkey.tokenpay.space @8.8.8.8")
else:
    print(f"\nERROR: {json.dumps(result.get('errors', result), indent=2)}")
