#!/usr/bin/env python3
"""Diagnose why auth works but others don't"""
import paramiko

SERVER = "5.23.54.205"
USER = "root"
PASSWORD = "vE^6t-zFS3dpNT"

def connect():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(SERVER, port=22, username=USER, password=PASSWORD,
              timeout=60, banner_timeout=60, auth_timeout=60,
              allow_agent=False, look_for_keys=False)
    return c

def run(client, cmd, show=True):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=60)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    if show and out:
        for line in out.split('\n')[:60]: print("  " + line)
    if show and err:
        for line in err.split('\n')[:5]: print("  ERR: " + line)
    return out

client = connect()
print("Connected.\n")

# 1. Full nginx config
print("=== FULL NGINX.CONF ===")
run(client, "cat /root/tokenpay-id/nginx/nginx.conf")

# 2. What CSS/JS versions are actually being served
print("\n=== CSS VERSION ON EACH DOMAIN ===")
run(client, "curl -sk https://tokenpay.space/ | grep -o 'styles.css[^\"]*' | head -3")
run(client, "curl -sk https://auth.tokenpay.space/ | grep -o 'styles.css[^\"]*' | head -3")
run(client, "curl -sk https://id.tokenpay.space/ | grep -o 'styles.css[^\"]*' | head -3")

# 3. CSS caching headers
print("\n=== CSS CACHE HEADERS ===")
run(client, "curl -skI https://tokenpay.space/styles.css 2>/dev/null | grep -E 'Cache|Etag|Last|Content'")

# 4. Check what file each subdomain serves as index
print("\n=== INDEX ROUTING ===")
run(client, """
cat /root/tokenpay-id/nginx/nginx.conf | grep -A30 'server_name.*auth\|location.*auth\|server_name tokenpay'
""")

# 5. Logo src in each page
print("\n=== LOGO IMG SRC IN EACH PAGE ===")
run(client, "curl -sk https://tokenpay.space/ | grep -o 'src=\"[^\"]*tokenpay[^\"]*\"' | head -5")
run(client, "curl -sk https://auth.tokenpay.space/ | grep -o 'src=\"[^\"]*tokenpay[^\"]*\"' | head -5")
run(client, "curl -sk https://id.tokenpay.space/ | grep -o 'src=\"[^\"]*tokenpay[^\"]*\"' | head -5")

# 6. Mobile nav structure comparison
print("\n=== NAV STRUCTURE auth.tokenpay.space ===")
run(client, "curl -sk https://auth.tokenpay.space/ | grep -o 'nav-links\|nav-overlay\|navLinks\|navOverlay' | sort | uniq")

print("\n=== NAV STRUCTURE tokenpay.space ===")
run(client, "curl -sk https://tokenpay.space/ | grep -o 'nav-links\|nav-overlay\|navLinks\|navOverlay' | sort | uniq")

client.close()
print("\nDone.")
