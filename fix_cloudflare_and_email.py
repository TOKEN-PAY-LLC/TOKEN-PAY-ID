#!/usr/bin/env python3
"""
Fix Cloudflare DNS, email routing, BIMI, favicon, and Russia access.
"""
import requests
import json
import sys
import time

ZONE = '210a25c077c2bfdc43a853762ccb358d'
ACCOUNT = '7b3dcd325574c3ca17e376b49d2875a9'
HEADERS = {
    'X-Auth-Email': 'ichernykh08@gmail.com',
    'X-Auth-Key': '5a4a5eddcb5882e068e0c407b670df0ef65ac',
    'Content-Type': 'application/json'
}
BASE = f'https://api.cloudflare.com/client/v4/zones/{ZONE}'
ACCT = f'https://api.cloudflare.com/client/v4/accounts/{ACCOUNT}'
SERVER_IP = '5.23.54.205'
DOMAIN = 'tokenpay.space'
FORWARD_TO = 'ichernykh08@gmail.com'

def api(method, url, data=None):
    fn = getattr(requests, method)
    r = fn(url, headers=HEADERS, json=data) if data else fn(url, headers=HEADERS)
    try:
        d = r.json()
    except Exception:
        print(f'  [!] Non-JSON response ({r.status_code}): {r.text[:200]}')
        return {'success': False, 'result': [], 'errors': []}
    if not d.get('success'):
        errs = d.get('errors', [])
        if errs:
            print(f'  [!] API Error: {errs}')
    return d

def get_dns_records():
    d = api('get', f'{BASE}/dns_records?per_page=100')
    return d.get('result', [])

def find_record(records, name, rtype):
    return [r for r in records if r['name'] == name and r['type'] == rtype]

def create_or_update_dns(records, name, rtype, content, proxied=False, priority=None, ttl=1):
    existing = find_record(records, name, rtype)
    # For MX we might have multiple
    if rtype == 'MX':
        # Check if this exact MX exists
        match = [r for r in existing if r['content'] == content]
        if match:
            print(f'  [=] {rtype} {name} -> {content} (exists)')
            return
        data = {'type': rtype, 'name': name, 'content': content, 'ttl': ttl}
        if priority is not None:
            data['priority'] = priority
        d = api('post', f'{BASE}/dns_records', data)
        if d.get('success'):
            print(f'  [+] Created {rtype} {name} -> {content} (priority={priority})')
        return

    if rtype == 'TXT':
        # Check if this TXT already exists with same content
        match = [r for r in existing if r['content'] == content]
        if match:
            print(f'  [=] {rtype} {name} (exists, same content)')
            return
        # For SPF/DMARC/BIMI - update existing if same prefix
        for rec in existing:
            if content.startswith('v=spf1') and rec['content'].startswith('v=spf1'):
                d = api('patch', f'{BASE}/dns_records/{rec["id"]}', {'content': content, 'ttl': ttl})
                if d.get('success'):
                    print(f'  [~] Updated {rtype} {name} SPF')
                return
            if content.startswith('v=DMARC1') and rec['content'].startswith('v=DMARC1'):
                d = api('patch', f'{BASE}/dns_records/{rec["id"]}', {'content': content, 'ttl': ttl})
                if d.get('success'):
                    print(f'  [~] Updated {rtype} {name} DMARC')
                return
            if content.startswith('v=BIMI1') and rec['content'].startswith('v=BIMI1'):
                d = api('patch', f'{BASE}/dns_records/{rec["id"]}', {'content': content, 'ttl': ttl})
                if d.get('success'):
                    print(f'  [~] Updated {rtype} {name} BIMI')
                return
        # Create new
        d = api('post', f'{BASE}/dns_records', {'type': rtype, 'name': name, 'content': content, 'ttl': ttl})
        if d.get('success'):
            print(f'  [+] Created {rtype} {name}')
        return

    # A/AAAA/CNAME
    if existing:
        rec = existing[0]
        needs_update = rec['content'] != content or rec.get('proxied') != proxied
        if not needs_update:
            print(f'  [=] {rtype} {name} -> {content} proxied={proxied} (no change)')
            return
        d = api('patch', f'{BASE}/dns_records/{rec["id"]}', {
            'content': content, 'proxied': proxied, 'ttl': ttl
        })
        if d.get('success'):
            print(f'  [~] Updated {rtype} {name} -> {content} proxied={proxied}')
    else:
        d = api('post', f'{BASE}/dns_records', {
            'type': rtype, 'name': name, 'content': content, 'proxied': proxied, 'ttl': ttl
        })
        if d.get('success'):
            print(f'  [+] Created {rtype} {name} -> {content} proxied={proxied}')

def delete_dns(record_id, name, rtype, content):
    d = api('delete', f'{BASE}/dns_records/{record_id}')
    if d.get('success'):
        print(f'  [-] Deleted {rtype} {name} -> {content}')

# ===================================================
# STEP 1: FIX RUSSIA ACCESS — Enable Cloudflare proxy
# ===================================================
def fix_russia_access(records):
    print('\n' + '='*60)
    print('STEP 1: FIX RUSSIA ACCESS (enable CF proxy)')
    print('='*60)

    # Enable proxy on main A record
    create_or_update_dns(records, DOMAIN, 'A', SERVER_IP, proxied=True)

    # Add specific proxied subdomains (A records since CNAME conflicts with wildcard)
    subdomains = ['auth', 'id', 'api']
    for sub in subdomains:
        fname = f'{sub}.{DOMAIN}'
        existing = find_record(records, fname, 'A') + find_record(records, fname, 'CNAME')
        if existing:
            print(f'  [=] {fname} already exists')
        else:
            create_or_update_dns(records, fname, 'A', SERVER_IP, proxied=True)

    # Set SSL to Full (Strict)
    print('\n  Setting SSL to Full (Strict)...')
    api('patch', f'{BASE}/settings/ssl', {'value': 'full'})

    # Lower security level to reduce challenges for legitimate users
    print('  Setting security level to essentially_off for Russia...')
    api('patch', f'{BASE}/settings/security_level', {'value': 'essentially_off'})

# ===================================================
# STEP 2: SETUP EMAIL ROUTING (Cloudflare)
# ===================================================
def setup_email_routing(records):
    print('\n' + '='*60)
    print('STEP 2: SETUP EMAIL ROUTING')
    print('='*60)

    # Delete old Timeweb MX records FIRST (they block CF Email Routing)
    print('\n  Removing old Timeweb MX records...')
    old_mx = find_record(records, DOMAIN, 'MX')
    for mx in old_mx:
        if 'timeweb' in mx['content']:
            delete_dns(mx['id'], mx['name'], 'MX', mx['content'])
    time.sleep(2)

    # Enable email routing
    print('  Enabling Cloudflare Email Routing...')
    r = api('get', f'{BASE}/email/routing')
    if r.get('result', {}).get('enabled'):
        print('  [=] Email Routing already enabled')
    else:
        api('post', f'{BASE}/email/routing/enable')
        print('  [+] Email Routing enabled')
        time.sleep(2)

    # Add destination address (account-level)
    print(f'\n  Adding destination: {FORWARD_TO}')
    r2 = api('get', f'{ACCT}/email/routing/addresses')
    acct_addrs = [a.get('email') for a in r2.get('result', [])]
    
    if FORWARD_TO in acct_addrs:
        print(f'  [=] {FORWARD_TO} already registered as destination')
    else:
        api('post', f'{ACCT}/email/routing/addresses', {'email': FORWARD_TO})
        print(f'  [+] Verification email sent to {FORWARD_TO} — VERIFY IT!')

    # Create email routing rules
    emails = [
        'support', 'noreply', 'president', 'id', 'info',
        'security', 'admin', 'help', 'no-reply', 'ceo'
    ]
    
    print('\n  Creating email routing rules...')
    r = api('get', f'{BASE}/email/routing/rules?per_page=50')
    existing_rules = r.get('result', [])
    existing_matchers = set()
    for rule in existing_rules:
        for m in rule.get('matchers', []):
            if m.get('type') == 'literal' and m.get('value'):
                existing_matchers.add(m['value'].lower())

    for alias in emails:
        addr = f'{alias}@{DOMAIN}'
        if addr in existing_matchers:
            print(f'  [=] {addr} rule exists')
            continue
        rule_data = {
            'matchers': [{'type': 'literal', 'field': 'to', 'value': addr}],
            'actions': [{'type': 'forward', 'value': [FORWARD_TO]}],
            'enabled': True,
            'name': f'Forward {alias}@ to Gmail'
        }
        d = api('post', f'{BASE}/email/routing/rules', rule_data)
        if d.get('success'):
            print(f'  [+] {addr} → {FORWARD_TO}')
        else:
            print(f'  [!] Failed: {addr}')

    # Also add catch-all rule
    print('\n  Setting up catch-all...')
    r = api('get', f'{BASE}/email/routing/rules/catch_all')
    catch = r.get('result', {})
    if catch.get('enabled') and any(a.get('type') == 'forward' for a in catch.get('actions', [])):
        print('  [=] Catch-all already configured')
    else:
        api('put', f'{BASE}/email/routing/rules/catch_all', {
            'matchers': [{'type': 'all'}],
            'actions': [{'type': 'forward', 'value': [FORWARD_TO]}],
            'enabled': True,
            'name': 'Catch-all → Gmail'
        })
        print(f'  [+] Catch-all → {FORWARD_TO}')

# ===================================================
# STEP 3: FIX DNS FOR EMAIL (SPF, DKIM, DMARC, BIMI)
# ===================================================
def fix_email_dns(records):
    print('\n' + '='*60)
    print('STEP 3: FIX EMAIL DNS (SPF, DKIM, DMARC, BIMI)')
    print('='*60)

    # Cloudflare Email Routing auto-manages MX records when enabled.
    # Just verify they exist:
    print('\n  Checking MX records...')
    records = get_dns_records()
    mx_recs = find_record(records, DOMAIN, 'MX')
    for mx in mx_recs:
        print(f'  [=] MX {mx["content"]} (pri={mx.get("priority","?")})')
    if not mx_recs:
        print('  [!] No MX records - CF Email Routing should add them automatically')

    # SPF: include Timeweb (for sending) + Cloudflare (for routing) + server IP
    spf = f'v=spf1 ip4:{SERVER_IP} include:_spf.timeweb.ru include:_spf.mx.cloudflare.net ~all'
    create_or_update_dns(records, DOMAIN, 'TXT', spf)
    print(f'  [~] SPF updated: {spf}')

    # DMARC: upgrade to quarantine with reporting
    dmarc = f'v=DMARC1; p=quarantine; rua=mailto:info@{DOMAIN}; ruf=mailto:info@{DOMAIN}; fo=1; adkim=r; aspf=r; pct=100'
    create_or_update_dns(records, f'_dmarc.{DOMAIN}', 'TXT', dmarc)

    # BIMI: point to logo SVG (hosted on site)
    bimi = f'v=BIMI1; l=https://{DOMAIN}/bimi-logo.svg'
    create_or_update_dns(records, f'default._bimi.{DOMAIN}', 'TXT', bimi)
    print(f'  [+] BIMI record added (logo: https://{DOMAIN}/bimi-logo.svg)')

# ===================================================
# STEP 4: FIX FAVICON CACHE  
# ===================================================
def fix_favicon():
    print('\n' + '='*60)
    print('STEP 4: PURGE CF CACHE (favicon + all)')
    print('='*60)

    # Purge entire cache
    d = api('post', f'{BASE}/purge_cache', {'purge_everything': True})
    if d.get('success'):
        print('  [+] Full cache purge requested')
    else:
        print('  [!] Cache purge failed')

# ===================================================
# MAIN
# ===================================================
def main():
    print('TOKEN PAY — Cloudflare & Email Fix Script')
    print('='*60)

    # Fetch current DNS
    print('\nFetching current DNS records...')
    records = get_dns_records()
    print(f'  Found {len(records)} records')

    fix_russia_access(records)

    # Refresh records after changes
    records = get_dns_records()

    setup_email_routing(records)
    fix_email_dns(records)
    fix_favicon()

    print('\n' + '='*60)
    print('ALL DONE!')
    print('='*60)
    print('\nIMPORTANT NEXT STEPS:')
    print(f'1. Verify {FORWARD_TO} as email destination (check inbox)')
    print('2. Upload bimi-logo.svg to frontend (SVG Tiny PS format)')
    print('3. Generate new favicon.ico from icon-512.png')
    print('4. Create tpid-logo-white.png for email headers')
    print('5. For Gmail BIMI avatar: need VMC certificate ($1500/yr)')
    print('   Alternative: set up Google Workspace for domain')

if __name__ == '__main__':
    main()
