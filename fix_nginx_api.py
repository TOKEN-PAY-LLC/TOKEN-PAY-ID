#!/usr/bin/env python3
"""Fix nginx API routing + restore SMTP + verify everything"""
import paramiko, time

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
    stdin, stdout, stderr = client.exec_command(cmd, timeout=120)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    code = stdout.channel.recv_exit_status()
    if show:
        if out:
            for line in out.split('\n')[:50]: print("  " + line)
        if err:
            for line in err.split('\n')[:10]: print("  ERR: " + line)
    return out, err, code

client = connect()
print("Connected.\n")

# --- 1. Show full nginx config ---
print("=== FULL NGINX CONFIG ===")
run(client, "cat /root/tokenpay-id/nginx/nginx.conf")

# --- 2. Fix .env SMTP (restore original SMTP settings) ---
print("\n=== FIX .ENV - RESTORE SMTP ===")
run(client, r"""
cd /root/tokenpay-id

# Remove blank SMTP lines and restore real values
sed -i '/^SMTP_HOST=$/d' .env
sed -i '/^SMTP_USER=$/d' .env
sed -i '/^SMTP_PASS=$/d' .env
sed -i '/^SMTP_FROM=noreply@tokenpay.space$/d' .env

# Add real SMTP settings
cat >> .env << 'SMTPEOF'
SMTP_HOST=smtp.timeweb.ru
SMTP_PORT=465
SMTP_USER=info@tokenpay.space
SMTP_PASS=1cgukl9kh5
SMTP_FROM=info@tokenpay.space
SMTPEOF

# Also restore ADMIN_PASSWORD if missing
if ! grep -q "^ADMIN_PASSWORD=" .env; then
    echo "ADMIN_PASSWORD=" >> .env
fi

echo ".env updated:"
grep -v SECRET .env | grep -v PASSWORD
""")

# --- 3. Check what the nginx config has for location blocks ---
print("\n=== CHECKING NGINX LOCATION BLOCKS ===")
out, _, _ = run(client, "cat /root/tokenpay-id/nginx/nginx.conf | grep -n 'location\|proxy_pass\|upstream'", show=False)
print("  Nginx locations/proxy_pass:")
for line in out.split('\n'):
    print("  " + line)

# --- 4. Fix nginx if /api/ is missing ---
print("\n=== CHECKING IF /api/ LOCATION EXISTS ===")
out, _, _ = run(client, "grep -c 'location.*api' /root/tokenpay-id/nginx/nginx.conf 2>/dev/null", show=False)
api_count = int(out.strip()) if out.strip().isdigit() else 0
print(f"  /api/ locations found: {api_count}")

if api_count == 0:
    print("  Adding /api/ proxy location to nginx config...")
    # Need to add location /api/ block inside the server block
    run(client, r"""
cd /root/tokenpay-id/nginx

# Backup
cp nginx.conf nginx.conf.bak

# Find the main server block and add /api/ location before the last closing brace
# Add location blocks for API routing
python3 << 'PYEOF'
with open('nginx.conf', 'r') as f:
    content = f.read()

api_location = '''
    # API proxy
    location /api/ {
        proxy_pass http://api:8080;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 30s;
        proxy_connect_timeout 5s;
        proxy_buffering off;
    }

    location /health {
        proxy_pass http://api:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        access_log off;
    }
'''

# Insert before the last closing brace of the SSL server block
# Find the last occurrence of "location /" and insert after its block
if 'location /api/' not in content:
    # Insert before the last } in the https server block
    # Find the location / block and add api after it
    import re
    # Add after the first 'location / {' block
    idx = content.rfind('\n}')
    if idx != -1:
        content = content[:idx] + api_location + content[idx:]
        with open('nginx.conf', 'w') as f:
            f.write(content)
        print('Added /api/ location block')
    else:
        print('Could not find insertion point')
else:
    print('/api/ already exists in config')
PYEOF
""")

# --- 5. Show updated nginx config ---
print("\n=== UPDATED NGINX CONFIG (relevant parts) ===")
run(client, "grep -n 'location\|proxy_pass\|server_name' /root/tokenpay-id/nginx/nginx.conf")

# --- 6. Reload nginx ---
print("\n=== RELOAD NGINX ===")
run(client, """
NGINX_CID=$(docker ps -q --filter name=tokenpay-id-nginx)
docker exec "$NGINX_CID" nginx -t 2>&1
docker exec "$NGINX_CID" nginx -s reload 2>&1 && echo "nginx reloaded" || echo "reload failed"
""")

# --- 7. Restart API with updated .env ---
print("\n=== RESTART API WITH UPDATED .ENV ===")
run(client, """
cd /root/tokenpay-id
docker compose up -d --force-recreate api 2>&1 | tail -5
""")

time.sleep(8)

# --- 8. Full verification ---
print("\n=== VERIFICATION ===")
run(client, "docker compose -f /root/tokenpay-id/docker-compose.yml ps 2>/dev/null")
run(client, "docker exec tokenpay-id-api wget -qO- http://localhost:8080/health 2>/dev/null")
run(client, "docker exec tokenpay-id-api wget -qO- http://localhost:8080/api/v1/health 2>/dev/null")
run(client, "curl -sk https://tokenpay.space/api/v1/health")
run(client, "curl -sk https://tokenpay.space/ | grep -o '<title>[^<]*</title>' | head -3")
run(client, "curl -sk https://auth.tokenpay.space/ | grep -o '<title>[^<]*</title>' | head -3")
run(client, "curl -sk https://id.tokenpay.space/ | grep -o '<title>[^<]*</title>' | head -3")

client.close()
print("\nDone.")
