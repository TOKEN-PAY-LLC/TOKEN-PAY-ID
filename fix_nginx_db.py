#!/usr/bin/env python3
"""Fix nginx proxy_pass + DB connection"""
import paramiko, time, sys

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
            for line in out.split('\n')[:30]:
                print("  " + line)
        if err and code != 0:
            for line in err.split('\n')[:10]:
                print("  ERR: " + line)
    return out, err, code

client = connect()
print("Connected.\n")

# --- Step 1: Find existing nginx config ---
print("=== NGINX SITE CONFIGS ===")
out, _, _ = run(client, "find /etc/nginx -name '*.conf' | xargs grep -l 'server_name' 2>/dev/null")
config_files = [f.strip() for f in out.split('\n') if f.strip()]
print(f"  Config files: {config_files}")

out, _, _ = run(client, "cat /etc/nginx/sites-enabled/*.conf 2>/dev/null || cat /etc/nginx/conf.d/*.conf 2>/dev/null || cat /etc/nginx/nginx.conf")

# --- Step 2: Check DB connectivity ---
print("\n=== DB CONNECTIVITY ===")
run(client, "nc -zv 5.23.55.152 5432 2>&1 | head -5 || echo 'nc not available'")
run(client, "pg_isready -h 5.23.55.152 -p 5432 -U gen_user 2>&1 || echo 'pg_isready not found'")

# Check current .env
print("\n=== CURRENT .ENV ===")
run(client, "cat /var/www/backend/.env | grep -v PASSWORD | grep -v SECRET")

# --- Step 3: Fix .env DB settings ---
print("\n=== FIXING .ENV DB SETTINGS ===")
fix_env_cmd = r"""
cd /var/www/backend

# Check if we can connect with current settings
node -e "
const {Pool} = require('pg');
const p = new Pool({
  host: process.env.DB_HOST || '5.23.55.152',
  port: process.env.DB_PORT || 5432,
  database: process.env.DB_NAME || 'default_db',
  user: process.env.DB_USER || 'gen_user',
  password: '93JJFQLAYC=Uo)',
  connectionTimeoutMillis: 5000
});
p.query('SELECT version()').then(r => {
  console.log('DB OK:', r.rows[0].version.split(' ').slice(0,2).join(' '));
  process.exit(0);
}).catch(e => {
  console.log('DB FAIL:', e.message);
  process.exit(1);
});
" 2>&1
"""
run(client, fix_env_cmd)

# --- Step 4: Patch .env with correct values ---
print("\n=== PATCHING .ENV ===")
patch_env = r"""
cd /var/www/backend

# Update DB settings in .env (use sed to avoid duplicates)
sed -i '/^DB_/d' .env
cat >> .env << 'DBEOF'
DB_HOST=5.23.55.152
DB_PORT=5432
DB_NAME=default_db
DB_USER=gen_user
DB_PASSWORD=93JJFQLAYC=Uo)
DBEOF

echo ".env DB section updated"
cat .env | grep DB_
"""
run(client, patch_env)

# --- Step 5: Fix nginx - add proxy_pass for /api/ ---
print("\n=== FIXING NGINX PROXY ===")

# First detect the config structure
out, _, _ = run(client, "ls /etc/nginx/sites-enabled/ 2>/dev/null || ls /etc/nginx/conf.d/ 2>/dev/null", show=False)

nginx_fix = r"""
# Find main nginx config file for tokenpay
CONF=""
for f in /etc/nginx/sites-enabled/*.conf /etc/nginx/conf.d/*.conf /etc/nginx/sites-enabled/default /etc/nginx/conf.d/default.conf; do
  [ -f "$f" ] && CONF="$f" && break
done

if [ -z "$CONF" ]; then
  CONF="/etc/nginx/conf.d/tokenpay.conf"
  echo "Creating new config: $CONF"
fi

echo "Using config: $CONF"

# Check if proxy_pass already exists
if grep -q "proxy_pass" "$CONF" 2>/dev/null; then
  echo "proxy_pass already configured"
  cat "$CONF"
else
  echo "Adding proxy_pass configuration..."
  # Backup
  cp "$CONF" "${CONF}.bak" 2>/dev/null || true
  
  # Check if the config has a server block
  if grep -q "server {" "$CONF" 2>/dev/null; then
    # Insert proxy location before the last closing brace
    # Add API proxy inside existing server block for tokenpay.space
    sed -i '/server_name.*tokenpay.space/,/^}/ {
      /^}/ i\    location /api/ {\n        proxy_pass http://127.0.0.1:8080;\n        proxy_http_version 1.1;\n        proxy_set_header Host $host;\n        proxy_set_header X-Real-IP $remote_addr;\n        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n        proxy_set_header X-Forwarded-Proto $scheme;\n        proxy_read_timeout 30s;\n        proxy_connect_timeout 5s;\n    }\n    location /health {\n        proxy_pass http://127.0.0.1:8080;\n        proxy_set_header Host $host;\n    }
    }' "$CONF"
  fi
  
  nginx -t 2>&1 && systemctl reload nginx && echo "Nginx reloaded with proxy" || echo "Nginx config error - check manually"
fi

echo "=== FINAL CONFIG ==="
cat "$CONF"
"""
run(client, nginx_fix)

# --- Step 6: Restart backend with dotenv ---
print("\n=== RESTART BACKEND (with .env) ===")
restart = r"""
cd /var/www/backend

# Kill old process
pkill -f "node server.js" 2>/dev/null || true
sleep 1

# Restart with PM2 loading .env
pm2 delete tokenpay 2>/dev/null || true
pm2 start server.js --name tokenpay --env production
pm2 save
pm2 list
"""
run(client, restart)

time.sleep(4)

# --- Step 7: Final health check ---
print("\n=== FINAL HEALTH CHECK ===")
run(client, "curl -s http://localhost:8080/health")
run(client, "curl -s https://tokenpay.space/api/v1/health 2>/dev/null || curl -sk https://tokenpay.space/api/v1/health 2>/dev/null || echo 'External check pending'")

client.close()
print("\nDone.")
