#!/usr/bin/env python3
"""Fix backend: remove dotenv require, start with env vars exported"""
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

# --- 1. Remove dotenv require line I added (it broke the server) ---
print("=== REMOVING DOTENV REQUIRE ===")
run(client, r"""
cd /var/www/backend
# Remove the dotenv line if present
sed -i "1{/require('dotenv').config();/d}" server.js
head -3 server.js
echo "First line check done"
""")

# --- 2. Kill any broken node process ---
print("\n=== KILLING BROKEN PROCESSES ===")
run(client, """
pkill -f "node server.js" 2>/dev/null; sleep 1
pkill -f "node /var/www" 2>/dev/null; sleep 1
echo "killed"
lsof -ti:8080 2>/dev/null && echo "port 8080 still in use" || echo "port 8080 free"
""")

# --- 3. Start backend properly with env vars exported ---
print("\n=== STARTING BACKEND WITH ENV VARS ===")
start_cmd = r"""
cd /var/www/backend

# Export all env vars from .env file (skip comments and empty lines)
set -a
. /var/www/backend/.env
set +a

# Verify key vars
echo "PORT=$PORT DB_HOST=$DB_HOST DB_USER=$DB_USER DB_NAME=$DB_NAME"

# Start node with env vars in environment
nohup env $(cat /var/www/backend/.env | grep -v '^#' | grep -v '^$' | xargs) node server.js > /var/log/tokenpay-api.log 2>&1 &
echo "Started PID: $!"
"""
run(client, start_cmd)

time.sleep(4)

# --- 4. Check if it's running and connected ---
print("\n=== BACKEND HEALTH ===")
run(client, "curl -s http://localhost:8080/health")

# --- 5. Check log for any errors ---
print("\n=== BACKEND LOG ===")
run(client, "tail -15 /var/log/tokenpay-api.log 2>/dev/null")

# --- 6. Check docker API container too ---
print("\n=== DOCKER API CONTAINER ===")
run(client, """
docker ps --format '{{.Names}} {{.Status}}' 2>/dev/null
API_CID=$(docker ps -q --filter name=tokenpay-id-api 2>/dev/null)
if [ -n "$API_CID" ]; then
  echo "API container: $API_CID"
  docker exec "$API_CID" curl -s http://localhost:8080/health 2>/dev/null || \
  docker exec "$API_CID" curl -s http://localhost:3000/health 2>/dev/null || \
  echo "Cannot health check inside container"
fi
""")

# --- 7. Check nginx routing ---
print("\n=== NGINX ROUTING CHECK ===")
run(client, """
NGINX_CID=$(docker ps -q --filter name=tokenpay-id-nginx 2>/dev/null)
if [ -n "$NGINX_CID" ]; then
  echo "Nginx container: $NGINX_CID"
  docker exec "$NGINX_CID" curl -s http://localhost:8080/health 2>/dev/null && echo "nginx->8080 OK" || echo "nginx can't reach 8080"
  docker exec "$NGINX_CID" curl -s http://localhost/api/v1/health 2>/dev/null | head -100
fi
""")

# --- 8. Final external test ---
print("\n=== FINAL EXTERNAL TEST ===")
run(client, "curl -sk https://tokenpay.space/api/v1/health 2>/dev/null | head -200")

client.close()
print("\nDone.")
