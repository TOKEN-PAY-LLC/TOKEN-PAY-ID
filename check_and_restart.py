#!/usr/bin/env python3
"""Diagnose backend + fix npm vulnerability + restart"""
import paramiko, sys

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
    if show and out:
        for line in out.split('\n')[:20]:
            print("  " + line)
    if show and err and code != 0:
        for line in err.split('\n')[:10]:
            print("  ERR: " + line)
    return out, err, code

client = connect()
print("Connected.\n")

print("=== PM2 STATUS ===")
run(client, "pm2 list 2>/dev/null || echo 'PM2 not found'")

print("\n=== NODE PROCESSES ===")
run(client, "ps aux | grep node | grep -v grep || echo 'No node processes'")

print("\n=== NGINX CONFIG ===")
run(client, "cat /etc/nginx/sites-enabled/*.conf 2>/dev/null | head -60 || cat /etc/nginx/conf.d/*.conf 2>/dev/null | head -60 || echo 'No nginx config found'")

print("\n=== BACKEND DIR ===")
run(client, "ls -la /var/www/backend/ 2>/dev/null | head -20")

print("\n=== .ENV FILE ===")
run(client, "[ -f /var/www/backend/.env ] && echo 'EXISTS' || echo 'MISSING - need to create!'")

print("\n=== FIX NPM VULNERABILITY ===")
out, err, code = run(client, "cd /var/www/backend && npm audit --json 2>/dev/null | python3 -c \"import json,sys; d=json.load(sys.stdin); print('Vulnerabilities:', d.get('metadata',{}).get('vulnerabilities',{}))\" 2>/dev/null || npm audit 2>&1 | head -20")

print("\n=== FIX: npm audit fix ===")
run(client, "cd /var/www/backend && npm audit fix --force 2>&1 | tail -5")

print("\n=== START/RESTART BACKEND ===")
restart_cmd = """
cd /var/www/backend

# Create .env if not exists
if [ ! -f .env ]; then
cat > .env << 'ENVEOF'
PORT=8080
DB_HOST=5.23.55.152
DB_PORT=5432
DB_NAME=default_db
DB_USER=gen_user
DB_PASSWORD=93JJFQLAYC=Uo)
ADMIN_EMAIL=info@tokenpay.space
CORS_ORIGIN=https://tokenpay.space,https://www.tokenpay.space,https://auth.tokenpay.space,https://id.tokenpay.space
ENVEOF
echo ".env created"
fi

# Generate JWT secrets if not set
if ! grep -q "JWT_SECRET=" .env || grep -q "JWT_SECRET=$" .env; then
  JWT_S=$(openssl rand -base64 32)
  JWT_R=$(openssl rand -base64 32)
  echo "JWT_SECRET=$JWT_S" >> .env
  echo "JWT_REFRESH_SECRET=$JWT_R" >> .env
  echo "JWT secrets generated"
fi

# Start/restart with PM2
if command -v pm2 >/dev/null 2>&1; then
  pm2 describe tokenpay >/dev/null 2>&1 && pm2 restart tokenpay || pm2 describe tpid >/dev/null 2>&1 && pm2 restart tpid || pm2 start server.js --name tokenpay --env production
  pm2 save
  echo "PM2 status:"
  pm2 list
else
  echo "Installing PM2..."
  npm install -g pm2
  pm2 start server.js --name tokenpay --env production
  pm2 save
  pm2 startup
fi
"""
run(client, restart_cmd)

print("\n=== HEALTH CHECK ===")
import time
time.sleep(3)
run(client, "curl -s http://localhost:8080/health 2>/dev/null || curl -s http://localhost:3000/health 2>/dev/null || echo 'Backend not responding on 8080/3000'")

print("\n=== NGINX PROXY CHECK ===")
run(client, """
nginx -t 2>&1
echo "---"
grep -r "proxy_pass" /etc/nginx/sites-enabled/ 2>/dev/null || grep -r "proxy_pass" /etc/nginx/conf.d/ 2>/dev/null || echo "No proxy_pass found in nginx config"
""")

client.close()
print("\nDone.")
