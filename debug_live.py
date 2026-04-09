#!/usr/bin/env python3
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

def run(client, cmd):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=60)
    return stdout.read().decode('utf-8', errors='replace').strip()

client = connect()

# Check what CSS is actually served
css = run(client, "curl -sk 'https://tokenpay.space/styles.css' 2>/dev/null | grep -o 'tpid-btn[^}]*}' | head -10")
print("=== CSS .tpid-btn rules ===")
print(css)

# Check nav-auth HTML
print("\n=== NAV AUTH HTML ===")
idx = run(client, "curl -sk 'https://tokenpay.space/' 2>/dev/null | grep -o '<div class=\"nav-auth[^<]*\\(<[^<]*\\)*</div>' | head -1")
print(idx[:500] if idx else "NOT FOUND")

# Simpler: grep for tpid-btn in index
print("\n=== tpid-btn in index.html ===")
r = run(client, "curl -sk 'https://tokenpay.space/' 2>/dev/null | grep -o 'tpid-btn[^\"]*' | sort -u")
print(r)

# Check CSS version
print("\n=== styles.css version param ===")
r = run(client, "curl -sk 'https://tokenpay.space/' 2>/dev/null | grep -o 'styles\\.css[^\"]*'")
print(r)

# Check if tpid-btn is in the actual served CSS
print("\n=== .tpid-btn exists in served CSS? ===")
r = run(client, "curl -sk 'https://tokenpay.space/styles.css' 2>/dev/null | grep -c 'tpid-btn'")
print(f"  Occurrences: {r}")

# Check file on disk
print("\n=== .tpid-btn in file on disk ===")
r = run(client, "grep -c 'tpid-btn' /root/tokenpay-id/frontend/styles.css")
print(f"  On disk: {r}")

# Check cache headers
print("\n=== Cache headers for styles.css ===")
r = run(client, "curl -skI 'https://tokenpay.space/styles.css' 2>/dev/null | grep -i 'cache\\|etag\\|last-mod'")
print(r)

client.close()
