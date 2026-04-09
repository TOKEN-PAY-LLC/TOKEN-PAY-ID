#!/usr/bin/env python3
"""Find real nginx config, fix proxy_pass, fix PM2 env loading"""
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
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    code = stdout.channel.recv_exit_status()
    if show:
        if out:
            for line in out.split('\n')[:40]:
                print("  " + line)
        if err:
            for line in err.split('\n')[:10]:
                print("  ERR: " + line)
    return out, err, code

client = connect()
print("Connected.\n")

# --- 1. Find REAL nginx config with server blocks ---
print("=== FINDING NGINX SERVER BLOCKS ===")
run(client, "grep -r 'server_name' /etc/nginx/ 2>/dev/null | grep -v '#'")
run(client, "grep -r 'tokenpay' /etc/nginx/ 2>/dev/null | head -20")

print("\n=== FULL NGINX CONF ===")
out, _, _ = run(client, "cat /etc/nginx/nginx.conf", show=False)
# Find include lines
for line in out.split('\n'):
    if 'include' in line or 'server' in line.lower():
        print("  " + line)

print("\n=== ALL CONF FILES ===")
run(client, "find /etc/nginx -name '*.conf' -o -name '*.cfg' 2>/dev/null | sort")

print("\n=== NGINX PROCESS ===")
run(client, "ps aux | grep nginx | grep -v grep")
run(client, "which nginx && nginx -v 2>&1")

# --- 2. Check what's actually serving the site ---
print("\n=== WHAT IS SERVING PORT 80/443 ===")
run(client, "ss -tlnp | grep -E '80|443|8080'")

# --- 3. Read the actual full nginx config to find server blocks ---
print("\n=== ALL SERVER BLOCKS ===")
run(client, r"grep -r 'server_name\|listen\|proxy_pass\|root\|location' /etc/nginx/ 2>/dev/null | grep -v '#' | head -50")

# --- 4. Fix: Use correct nginx service name ---
print("\n=== NGINX SERVICE STATUS ===")
run(client, "service nginx status 2>&1 | head -5 || systemctl status nginx 2>&1 | head -5")
run(client, "service --status-all 2>&1 | grep nginx || echo 'nginx service name check done'")

# --- 5. Fix PM2 to properly load .env ---
print("\n=== FIX PM2 ENV LOADING ===")
pm2_fix = r"""
cd /var/www/backend

# Kill everything first
pkill -f "node server.js" 2>/dev/null; sleep 1

# Make sure dotenv is available
[ -f node_modules/.bin/dotenv ] || npm install dotenv --save 2>/dev/null

# Use ecosystem file for PM2 to properly load .env
cat > ecosystem.config.js << 'ECOEOF'
require('dotenv').config();
module.exports = {
  apps: [{
    name: 'tokenpay',
    script: 'server.js',
    instances: 1,
    autorestart: true,
    watch: false,
    max_memory_restart: '512M',
    env: {
      NODE_ENV: 'production',
      ...require('dotenv').parse(require('fs').readFileSync('.env', 'utf8'))
    }
  }]
};
ECOEOF

# Also add dotenv require at top of server.js if not there
grep -q "require('dotenv')" server.js || sed -i "1s/^/require('dotenv').config();\n/" server.js
echo "dotenv check done"

# Restart with ecosystem
pm2 delete tokenpay 2>/dev/null; pm2 delete tpid 2>/dev/null; sleep 1
pm2 start ecosystem.config.js
pm2 save

echo "PM2 started"
pm2 list
"""
run(client, pm2_fix)

time.sleep(4)

# --- 6. Verify backend is up with DB ---
print("\n=== BACKEND HEALTH ===")
run(client, "curl -s http://localhost:8080/health 2>/dev/null")

# --- 7. Find and fix nginx proxy config ---
print("\n=== ADD PROXY TO NGINX ===")
nginx_proxy = r"""
# Find real config file
CONF=$(grep -rl 'tokenpay\|server_name' /etc/nginx/ 2>/dev/null | head -1)
[ -z "$CONF" ] && CONF=$(find /etc/nginx -name '*.conf' ! -name 'nginx.conf' ! -name 'fastcgi*' ! -name 'mime*' ! -name 'proxy*' | head -1)
[ -z "$CONF" ] && CONF="/etc/nginx/nginx.conf"
echo "Target config: $CONF"

# Check if already has proxy_pass
if grep -q "proxy_pass.*8080" "$CONF" 2>/dev/null; then
  echo "proxy_pass already exists"
else
  echo "Adding proxy_pass..."
  
  # Create separate proxy config
  cat > /etc/nginx/conf.d/tokenpay-api.conf << 'NGINXEOF'
# TOKEN PAY API proxy
server {
    listen 80;
    server_name tokenpay.space www.tokenpay.space auth.tokenpay.space id.tokenpay.space;

    # API proxy
    location /api/ {
        proxy_pass http://127.0.0.1:8080;
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
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        access_log off;
    }
}
NGINXEOF
  echo "Config created"
fi

# Test and reload
nginx -t 2>&1
nginx -s reload 2>&1 || service nginx reload 2>&1 || systemctl reload nginx 2>&1
echo "Nginx reload attempted"
"""
run(client, nginx_proxy)

time.sleep(2)

# --- 8. Final checks ---
print("\n=== FINAL HEALTH CHECKS ===")
run(client, "curl -s http://localhost:8080/health")
run(client, "curl -s http://tokenpay.space/api/v1/health 2>/dev/null || curl -s http://localhost/api/v1/health 2>/dev/null || echo 'http check done'")

client.close()
print("\nFix script done.")
