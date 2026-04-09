#!/usr/bin/env python3
"""Check Cloudflare DNS and settings for tokenpay.space"""
import requests, json

ZONE = '210a25c077c2bfdc43a853762ccb358d'
HEADERS = {
    'X-Auth-Email': 'ichernykh08@gmail.com',
    'X-Auth-Key': '5a4a5eddcb5882e068e0c407b670df0ef65ac',
    'Content-Type': 'application/json'
}
BASE = f'https://api.cloudflare.com/client/v4/zones/{ZONE}'

# 1. DNS Records
print("=== DNS RECORDS ===")
r = requests.get(f'{BASE}/dns_records?per_page=100', headers=HEADERS)
d = r.json()
if not d.get('success'):
    print("ERROR:", d)
else:
    for rec in d['result']:
        prx = '🟠' if rec.get('proxied') else '⚪'
        print(f"  {prx} {rec['type']:6} {rec['name']:45} -> {rec['content'][:60]}")

# 2. Firewall rules
print("\n=== FIREWALL RULES ===")
r = requests.get(f'{BASE}/firewall/rules?per_page=50', headers=HEADERS)
d = r.json()
if d.get('success') and d.get('result'):
    for rule in d['result']:
        print(f"  [{rule.get('action','')}] {rule.get('description','no desc')} | filter: {rule.get('filter',{}).get('expression','')[:100]}")
else:
    print("  No firewall rules or error:", d.get('errors',''))

# 3. Access rules (IP blocks)
print("\n=== ACCESS RULES (IP blocks) ===")
r = requests.get(f'{BASE}/firewall/access_rules/rules?per_page=50', headers=HEADERS)
d = r.json()
if d.get('success') and d.get('result'):
    for rule in d['result']:
        cfg = rule.get('configuration', {})
        print(f"  [{rule.get('mode','')}] {cfg.get('target','')}: {cfg.get('value','')} | {rule.get('notes','')}")
else:
    print("  No access rules")

# 4. Check if there's a block on RU
print("\n=== CHECKING FOR COUNTRY BLOCKS ===")
r = requests.get(f'https://api.cloudflare.com/client/v4/accounts/7b3dcd325574c3ca17e376b49d2875a9/firewall/access_rules/rules?per_page=50', headers=HEADERS)
d = r.json()
if d.get('success') and d.get('result'):
    for rule in d['result']:
        cfg = rule.get('configuration', {})
        print(f"  [{rule.get('mode','')}] {cfg.get('target','')}: {cfg.get('value','')} | {rule.get('notes','')}")
else:
    print("  No account-level access rules")

# 5. SSL/TLS mode
print("\n=== SSL/TLS MODE ===")
r = requests.get(f'{BASE}/settings/ssl', headers=HEADERS)
d = r.json()
if d.get('success'):
    print(f"  SSL mode: {d['result']['value']}")

# 6. Check rulesets (WAF managed rules)
print("\n=== WAF RULESETS ===")
r = requests.get(f'{BASE}/rulesets', headers=HEADERS)
d = r.json()
if d.get('success') and d.get('result'):
    for rs in d['result']:
        print(f"  {rs.get('phase',''):30} {rs.get('name',''):40} (rules: {len(rs.get('rules',[]))})")
else:
    print("  No rulesets or error")

print("\nDone!")
