#!/usr/bin/env python3
"""Fix Docker nginx proxy (3000→8080), restart backend with .env"""
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
            for line in out.split('\n')[:30]: print("  " + line)
        if err:
            for line in err.split('\n')[:10]: print("  ERR: " + line)
    return out, err, code

client = connect()
print("Connected.\n")

# --- 1. Check Docker containers ---
print("=== DOCKER CONTAINERS ===")
run(client, "docker ps --format 'table {{.Names}}\t{{.Ports}}\t{{.Status}}' 2>/dev/null || echo 'docker not available'")

# --- 2. Find which container has nginx ---
print("\n=== NGINX IN DOCKER ===")
out, _, _ = run(client, "docker ps -q 2>/dev/null", show=False)
containers = [c.strip() for c in out.split('\n') if c.strip()]

if containers:
    for cid in containers[:5]:
        out2, _, _ = run(client, f"docker exec {cid} nginx -v 2>/dev/null && echo 'nginx in {cid}'", show=False)
        if 'nginx' in out2.lower():
            print(f"  Nginx found in container: {cid}")
            # Show its config
            run(client, f"docker exec {cid} cat /etc/nginx/sites-enabled/tokenpay 2>/dev/null || docker exec {cid} cat /etc/nginx/conf.d/default.conf 2>/dev/null || docker exec {cid} nginx -T 2>/dev/null | head -60")

# --- 3. Fix nginx config: change proxy from 3000 to 8080 ---
print("\n=== FIX NGINX CONFIG (3000 → 8080) ===")
nginx_fix = r"""
# Fix the nginx config to point to our backend on 8080
CONF="/etc/nginx/sites-available/tokenpay"
if [ -f "$CONF" ]; then
  echo "Before:"
  grep proxy_pass "$CONF"
  
  # Replace port 3000 with 8080
  sed -i 's|proxy_pass http://127.0.0.1:3000|proxy_pass http://127.0.0.1:8080|g' "$CONF"
  sed -i 's|proxy_pass http://localhost:3000|proxy_pass http://localhost:8080|g' "$CONF"
  
  echo "After:"
  grep proxy_pass "$CONF"
  echo "Config updated"
else
  echo "No tokenpay config found at $CONF"
fi

# Also check sites-enabled
CONF2="/etc/nginx/sites-enabled/tokenpay"
if [ -f "$CONF2" ]; then
  sed -i 's|proxy_pass http://127.0.0.1:3000|proxy_pass http://127.0.0.1:8080|g' "$CONF2"
  sed -i 's|proxy_pass http://localhost:3000|proxy_pass http://localhost:8080|g' "$CONF2"
  echo "sites-enabled/tokenpay updated"
fi
"""
run(client, nginx_fix)

# --- 4. Reload nginx (inside Docker or host) ---
print("\n=== RELOAD NGINX ===")
reload_cmd = r"""
# Try to reload nginx (various methods)
NGINX_PID=$(pgrep -x nginx | head -1 2>/dev/null)
if [ -n "$NGINX_PID" ]; then
  kill -HUP $NGINX_PID
  echo "Sent HUP to nginx PID $NGINX_PID"
fi

# If running in Docker, exec into containers
for CID in $(docker ps -q 2>/dev/null); do
  if docker exec "$CID" which nginx >/dev/null 2>&1; then
    # Update config inside Docker container too
    docker exec "$CID" sh -c "sed -i 's|proxy_pass http://127.0.0.1:3000|proxy_pass http://127.0.0.1:8080|g' /etc/nginx/sites-available/tokenpay 2>/dev/null; sed -i 's|proxy_pass http://127.0.0.1:3000|proxy_pass http://127.0.0.1:8080|g' /etc/nginx/sites-enabled/tokenpay 2>/dev/null; nginx -t && nginx -s reload && echo 'nginx reloaded in Docker' || nginx -t" 2>&1
  fi
done
"""
run(client, reload_cmd)

# --- 5. Fix backend: kill old process and restart with .env ---
print("\n=== RESTART BACKEND WITH PROPER ENV ===")
backend_restart = r"""
cd /var/www/backend

# Check current DB_PASSWORD in .env
grep -c "DB_PASSWORD" .env 2>/dev/null

# Verify .env is complete
cat .env | grep -v SECRET | grep -v PASSWORD

# Kill the old process that doesn't have .env loaded
OLD_PID=$(lsof -ti:8080 2>/dev/null | head -1)
if [ -n "$OLD_PID" ]; then
  echo "Killing old process on 8080: PID $OLD_PID"
  kill $OLD_PID 2>/dev/null
  sleep 2
fi

# Add dotenv loader to server.js if not present
head -3 server.js
grep -n "dotenv" server.js | head -3

# Ensure dotenv is at top
if ! head -1 server.js | grep -q "dotenv"; then
  sed -i "1s/^/require('dotenv').config();\n/" server.js
  echo "Added dotenv.config() to server.js"
fi

# Start with node directly (no pm2 issues with env)
nohup node server.js > /var/log/tokenpay-api.log 2>&1 &
NEW_PID=$!
echo "Started backend PID: $NEW_PID"
sleep 3

# Health check
curl -s http://localhost:8080/health 2>/dev/null || echo "Still starting..."
sleep 2
curl -s http://localhost:8080/health 2>/dev/null
"""
run(client, backend_restart)

time.sleep(3)

# --- 6. Full verification ---
print("\n=== VERIFICATION ===")
run(client, "curl -s http://localhost:8080/health")
run(client, "curl -s http://localhost:8080/api/v1/health 2>/dev/null || curl -s http://localhost/api/v1/health 2>/dev/null")

# Show nginx config
print("\n=== NGINX ACTIVE CONFIG ===")
run(client, "cat /etc/nginx/sites-available/tokenpay 2>/dev/null | grep -A2 'location\\|proxy_pass\\|server_name'")

# Check backend log
print("\n=== BACKEND LOG ===")
run(client, "tail -20 /var/log/tokenpay-api.log 2>/dev/null || echo 'No log file'")

client.close()
print("\nDone.")
